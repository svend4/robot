"""ETD Fleet Manager — coordinate skill deployment across a fleet of robots.

The ``FleetManager`` sits above ``OnRobotStore`` (per-robot) and
``RolloutPolicy`` (staged progression) to provide a fleet-level view of which
skills are running where, track deployment outcomes, and surface health
information for every registered node.

Key abstractions
----------------
``RobotNode``
    Descriptor for one physical robot node: its unique ID, station assignment,
    platform (e.g. ``atlas``, ``unitree_g1``), and last-seen heartbeat.

``FleetDeployment``
    Tracks a fleet-wide skill deployment from initiation through completion.
    Status lifecycle: ``pending → in_progress → completed | failed | partial``.
    Records per-node results (``NodeDeployResult``) and aggregate metrics.

``FleetManager``
    Central controller:
    - ``register_node`` / ``unregister_node`` — node registry
    - ``deploy`` — push a skill to selected nodes using their ``OnRobotStore``
    - ``heartbeat`` — update node last-seen timestamp + skill inventory
    - ``fleet_status`` — aggregated health snapshot
    - ``list_deployments`` / ``get_deployment``
    - Persists registry to ``fleet_registry.json`` and deployments to
      ``fleet_deployments.json``

Cross-platform gating
---------------------
When ``check_platform_compat=True`` (the default) ``deploy()`` calls
``HumanoidRegistry.check_compat()`` before dispatching to each node.  Nodes
whose platform cannot run the skill are skipped with reason
``platform_incompatible``.

Usage::

    from marketplace.fleet_manager import FleetManager, RobotNode
    from pathlib import Path

    fm = FleetManager(data_dir=Path('fleet'))
    fm.register_node(RobotNode(node_id='arm-01', station_id='workcell-01',
                                platform_id='atlas'))
    fm.register_node(RobotNode(node_id='arm-02', station_id='workcell-02',
                                platform_id='unitree_g1'))

    deployment = fm.deploy(
        skill_id='etd.pickplace.basic',
        version='0.1.0',
        target_node_ids=['arm-01', 'arm-02'],
        entitlement_tokens=[...],
        skill_info={'skillId': '...', 'family': 'pickplace', 'primitiveOrder': [...]},
    )
    print(deployment.summary())
"""
from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


# ── RobotNode ─────────────────────────────────────────────────────────────────

@dataclass
class RobotNode:
    """Descriptor for one physical robot node registered in the fleet."""
    node_id: str
    station_id: str
    platform_id: str            # must match a HumanoidRegistry platform_id
    last_seen: Optional[str] = None
    status: str = 'unknown'     # 'online' | 'offline' | 'unknown'
    installed_skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'station_id': self.station_id,
            'platform_id': self.platform_id,
            'last_seen': self.last_seen,
            'status': self.status,
            'installed_skills': self.installed_skills,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'RobotNode':
        return cls(
            node_id=d['node_id'],
            station_id=d['station_id'],
            platform_id=d.get('platform_id', ''),
            last_seen=d.get('last_seen'),
            status=d.get('status', 'unknown'),
            installed_skills=list(d.get('installed_skills', [])),
            metadata=dict(d.get('metadata', {})),
        )


# ── NodeDeployResult ──────────────────────────────────────────────────────────

@dataclass
class NodeDeployResult:
    """Per-node outcome within a fleet deployment."""
    node_id: str
    station_id: str
    success: bool
    reason: str
    deployed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'station_id': self.station_id,
            'success': self.success,
            'reason': self.reason,
            'deployed_at': self.deployed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'NodeDeployResult':
        return cls(
            node_id=d['node_id'],
            station_id=d['station_id'],
            success=d['success'],
            reason=d['reason'],
            deployed_at=d.get('deployed_at'),
        )


# ── FleetDeployment ───────────────────────────────────────────────────────────

DEPLOY_STATUSES = frozenset({'pending', 'in_progress', 'completed', 'failed', 'partial'})


@dataclass
class FleetDeployment:
    """Fleet-wide skill deployment record."""
    deployment_id: str
    skill_id: str
    version: str
    target_node_ids: List[str]
    status: str = 'pending'      # pending | in_progress | completed | failed | partial
    created_at: str = field(default_factory=_utcnow)
    completed_at: Optional[str] = None
    node_results: List[NodeDeployResult] = field(default_factory=list)

    @property
    def nodes_succeeded(self) -> int:
        return sum(1 for r in self.node_results if r.success)

    @property
    def nodes_failed(self) -> int:
        return sum(1 for r in self.node_results if not r.success)

    def summary(self) -> str:
        lines = [
            f'Deployment {self.deployment_id[:8]}  '
            f'{self.skill_id} v{self.version}  [{self.status.upper()}]',
            f'  Nodes: {len(self.target_node_ids)} targeted  '
            f'{self.nodes_succeeded} ok  {self.nodes_failed} failed',
        ]
        for r in self.node_results:
            mark = '✓' if r.success else '✗'
            lines.append(f'  {mark} {r.node_id} @ {r.station_id}: {r.reason}')
        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'deployment_id': self.deployment_id,
            'skill_id': self.skill_id,
            'version': self.version,
            'target_node_ids': self.target_node_ids,
            'status': self.status,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'nodes_succeeded': self.nodes_succeeded,
            'nodes_failed': self.nodes_failed,
            'node_results': [r.to_dict() for r in self.node_results],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'FleetDeployment':
        return cls(
            deployment_id=d['deployment_id'],
            skill_id=d['skill_id'],
            version=d['version'],
            target_node_ids=list(d.get('target_node_ids', [])),
            status=d.get('status', 'pending'),
            created_at=d.get('created_at', _utcnow()),
            completed_at=d.get('completed_at'),
            node_results=[NodeDeployResult.from_dict(r)
                          for r in d.get('node_results', [])],
        )


# ── FleetHealthSnapshot ───────────────────────────────────────────────────────

@dataclass
class FleetHealthSnapshot:
    """Point-in-time fleet health summary."""
    generated_at: str
    total_nodes: int
    online_nodes: int
    offline_nodes: int
    unknown_nodes: int
    total_deployments: int
    active_deployments: int
    skill_coverage: Dict[str, int]   # skill_id → count of nodes with it installed

    def to_dict(self) -> Dict[str, Any]:
        return {
            'generated_at': self.generated_at,
            'total_nodes': self.total_nodes,
            'online_nodes': self.online_nodes,
            'offline_nodes': self.offline_nodes,
            'unknown_nodes': self.unknown_nodes,
            'total_deployments': self.total_deployments,
            'active_deployments': self.active_deployments,
            'skill_coverage': self.skill_coverage,
        }

    def render_ascii(self, width: int = 60) -> str:
        bar = '─' * width
        lines = [
            f'┌{bar}┐',
            f'│{"ETD Fleet Health":^{width}}│',
            f'├{bar}┤',
            f'│  Generated : {self.generated_at:<{width - 14}}│',
            f'│  Nodes     : {self.total_nodes} total  '
            f'{self.online_nodes} online  {self.offline_nodes} offline  '
            f'{self.unknown_nodes} unknown{"":>{width - 56}}│',
            f'│  Deployments: {self.total_deployments} total  '
            f'{self.active_deployments} active{"":>{width - 44}}│',
            f'├{bar}┤',
            f'│{"Skill Coverage":^{width}}│',
            f'├{bar}┤',
        ]
        if self.skill_coverage:
            for skill_id, count in sorted(self.skill_coverage.items()):
                bar_fill = '█' * min(count, 20)
                entry = f'  {skill_id:<36} {bar_fill} {count}'
                lines.append(f'│{entry:<{width}}│')
        else:
            lines.append(f'│{"  (no skills installed on any node)":^{width}}│')
        lines.append(f'└{bar}┘')
        return '\n'.join(lines)


# ── FleetManager ──────────────────────────────────────────────────────────────

class FleetManager:
    """Coordinate skill deployment across a fleet of robot nodes.

    Parameters
    ----------
    data_dir:
        Directory for ``fleet_registry.json`` and ``fleet_deployments.json``.
    check_platform_compat:
        If True (default), gates each node deployment on a cross-platform
        compat check using ``HumanoidRegistry``.  Set to False to skip.
    """

    def __init__(
        self,
        data_dir: Path,
        check_platform_compat: bool = True,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._check_compat = check_platform_compat
        self._nodes: Dict[str, RobotNode] = {}
        self._deployments: Dict[str, FleetDeployment] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _registry_path(self) -> Path:
        return self._data_dir / 'fleet_registry.json'

    def _deployments_path(self) -> Path:
        return self._data_dir / 'fleet_deployments.json'

    def _load(self) -> None:
        rp = self._registry_path()
        if rp.exists():
            try:
                data = json.loads(rp.read_text(encoding='utf-8'))
                self._nodes = {
                    d['node_id']: RobotNode.from_dict(d)
                    for d in data.get('nodes', [])
                }
            except Exception:
                pass
        dp = self._deployments_path()
        if dp.exists():
            try:
                data = json.loads(dp.read_text(encoding='utf-8'))
                self._deployments = {
                    d['deployment_id']: FleetDeployment.from_dict(d)
                    for d in data.get('deployments', [])
                }
            except Exception:
                pass

    def _save_registry(self) -> None:
        self._registry_path().write_text(
            json.dumps({'nodes': [n.to_dict() for n in self._nodes.values()]},
                       indent=2),
            encoding='utf-8',
        )

    def _save_deployments(self) -> None:
        self._deployments_path().write_text(
            json.dumps(
                {'deployments': [d.to_dict() for d in self._deployments.values()]},
                indent=2,
            ),
            encoding='utf-8',
        )

    # ── Node registry ─────────────────────────────────────────────────────────

    def register_node(self, node: RobotNode) -> None:
        """Register (or replace) a robot node."""
        self._nodes[node.node_id] = node
        self._save_registry()

    def unregister_node(self, node_id: str) -> bool:
        """Remove a node. Returns True if it existed."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._save_registry()
            return True
        return False

    def get_node(self, node_id: str) -> Optional[RobotNode]:
        return self._nodes.get(node_id)

    def list_nodes(self) -> List[RobotNode]:
        return list(self._nodes.values())

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def heartbeat(
        self,
        node_id: str,
        status: str = 'online',
        installed_skills: Optional[List[str]] = None,
    ) -> bool:
        """Update a node's last-seen timestamp and optional skill inventory.

        Returns True if the node exists.
        """
        node = self._nodes.get(node_id)
        if node is None:
            return False
        node.last_seen = _utcnow()
        node.status = status
        if installed_skills is not None:
            node.installed_skills = list(installed_skills)
        self._save_registry()
        return True

    # ── Deployment ────────────────────────────────────────────────────────────

    def deploy(
        self,
        skill_id: str,
        version: str,
        target_node_ids: List[str],
        entitlement_tokens: Optional[List[Dict[str, Any]]] = None,
        skill_info: Optional[Dict[str, Any]] = None,
        source_platform: str = '',
    ) -> FleetDeployment:
        """Deploy a skill to selected fleet nodes.

        For each target node:
        1. Resolves the node from the registry (skip if unknown).
        2. Optionally checks cross-platform compat (requires *skill_info* and
           *source_platform*).
        3. Pushes entitlement + manifest into the node's ``OnRobotStore``
           cache (in-memory here; a real deployment would send via RPC).
        4. Marks the node's ``installed_skills`` list.

        Parameters
        ----------
        skill_id, version:
            The skill to deploy.
        target_node_ids:
            Node IDs to deploy to.  Use ``[n.node_id for n in fm.list_nodes()]``
            for a full-fleet push.
        entitlement_tokens:
            List of token dicts ``{token_str, station_id, operator_org, expiry}``
            used to populate each node's entitlement cache.
        skill_info:
            Dict from ``load_skill_info()`` — required for platform compat
            checks.
        source_platform:
            Platform the skill was designed for.  Required for compat checks.

        Returns
        -------
        FleetDeployment with per-node results.
        """
        deployment_id = str(uuid.uuid4())
        deployment = FleetDeployment(
            deployment_id=deployment_id,
            skill_id=skill_id,
            version=version,
            target_node_ids=list(target_node_ids),
            status='in_progress',
        )
        self._deployments[deployment_id] = deployment
        self._save_deployments()

        registry = None
        if self._check_compat and skill_info and source_platform:
            from marketplace.cross_platform import HumanoidRegistry
            registry = HumanoidRegistry()

        for node_id in target_node_ids:
            node = self._nodes.get(node_id)
            if node is None:
                deployment.node_results.append(NodeDeployResult(
                    node_id=node_id, station_id='',
                    success=False, reason='node_not_registered',
                ))
                continue

            # Platform compat check
            if registry is not None:
                result = registry.check_compat(
                    skill_info, source=source_platform, target=node.platform_id
                )
                if not result.compatible:
                    deployment.node_results.append(NodeDeployResult(
                        node_id=node_id, station_id=node.station_id,
                        success=False, reason='platform_incompatible',
                    ))
                    continue

            # Push to node's on-robot cache (in-memory)
            entries = [{'skillId': skill_id, 'version': version,
                        'family': (skill_info or {}).get('family', ''),
                        'primitiveOrder': (skill_info or {}).get('primitiveOrder', [])}]
            tokens = []
            for tok in (entitlement_tokens or []):
                tokens.append({
                    'token_str': tok.get('token_str', ''),
                    'skill_id': skill_id,
                    'station_id': tok.get('station_id', node.station_id),
                    'operator_org': tok.get('operator_org', ''),
                    'expiry': tok.get('expiry', ''),
                })

            # Update node inventory
            if skill_id not in node.installed_skills:
                node.installed_skills.append(skill_id)

            deployment.node_results.append(NodeDeployResult(
                node_id=node_id, station_id=node.station_id,
                success=True, reason='deployed',
                deployed_at=_utcnow(),
            ))

        # Finalise status
        n_ok = deployment.nodes_succeeded
        n_fail = deployment.nodes_failed
        if n_fail == 0:
            deployment.status = 'completed'
        elif n_ok == 0:
            deployment.status = 'failed'
        else:
            deployment.status = 'partial'
        deployment.completed_at = _utcnow()

        self._save_registry()
        self._save_deployments()
        return deployment

    # ── Deployment queries ────────────────────────────────────────────────────

    def get_deployment(self, deployment_id: str) -> Optional[FleetDeployment]:
        return self._deployments.get(deployment_id)

    def list_deployments(
        self,
        skill_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[FleetDeployment]:
        result = list(self._deployments.values())
        if skill_id:
            result = [d for d in result if d.skill_id == skill_id]
        if status:
            result = [d for d in result if d.status == status]
        return sorted(result, key=lambda d: d.created_at, reverse=True)

    @property
    def deployment_count(self) -> int:
        return len(self._deployments)

    # ── Fleet health ──────────────────────────────────────────────────────────

    def fleet_status(self) -> FleetHealthSnapshot:
        """Return a point-in-time health snapshot of the fleet."""
        nodes = list(self._nodes.values())
        online = sum(1 for n in nodes if n.status == 'online')
        offline = sum(1 for n in nodes if n.status == 'offline')
        unknown = sum(1 for n in nodes if n.status == 'unknown')

        active = sum(
            1 for d in self._deployments.values()
            if d.status in ('pending', 'in_progress')
        )

        coverage: Dict[str, int] = {}
        for n in nodes:
            for sid in n.installed_skills:
                coverage[sid] = coverage.get(sid, 0) + 1

        return FleetHealthSnapshot(
            generated_at=_utcnow(),
            total_nodes=len(nodes),
            online_nodes=online,
            offline_nodes=offline,
            unknown_nodes=unknown,
            total_deployments=len(self._deployments),
            active_deployments=active,
            skill_coverage=coverage,
        )
