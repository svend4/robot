"""On-robot embedded skill store — offline entitlement cache + mesh sync.

ETD's ``SkillStore`` is designed for server-side / workstation use.  The
``OnRobotStore`` is a lightweight companion that runs *on the robot's compute
unit*.  It keeps a local cache of verified entitlement tokens and skill
manifests so that skills can be executed even when the central marketplace is
unreachable (e.g. during factory network partitions or untethered field ops).

Architecture
------------
::

    Central Marketplace  ──(sync)──▶  OnRobotStore  ──▶  robot executor
                                           │
                              ┌────────────┴────────────┐
                        EntitlementCache         SkillManifestCache
                        (verified tokens)        (skill.json + manifest.yaml
                                                  stored as JSON blobs)

    Fleet peers  ◀──(mesh sync)──▶  OnRobotStore

Components
----------
``CachedEntitlement``
    A locally persisted, pre-verified entitlement token.  Stores the raw
    token string so it can be re-verified on retrieval, plus a cached
    ``verified_at`` timestamp.

``EntitlementCache``
    JSON-backed store for ``CachedEntitlement`` records.  Supports:
    - ``add(token_str, verify_key)`` — verify then persist
    - ``get(skill_id, station_id)`` — retrieve valid token or None
    - ``evict_expired()`` — prune stale entries
    - ``list_skills()`` — skill IDs with at least one valid cached token

``SkillManifestCache``
    Directory-backed cache of skill package metadata (``skill.json`` +
    ``manifest.yaml`` contents).  Enables offline validation.

``MeshSyncRecord``
    Tracks the last successful sync with one fleet peer.

``MeshSync``
    Fleet peer-to-peer sync stub: ``announce()``, ``receive_from_peer()``,
    ``sync_status()``.  In this prototype the transport is in-memory; a real
    deployment would use UDP multicast or a local MQTT broker.

``OnRobotStore``
    Top-level façade:
    - ``install_offline(skill_id, station_id)`` — serve from cache
    - ``is_available_offline(skill_id, station_id)`` — entitlement + manifest
    - ``sync_from_central(entries)`` — update local caches from a central feed
    - ``get_offline_skills()`` — list skills available entirely offline
    - ``summary()`` / ``to_dict()``

Usage::

    from marketplace.onrobot_store import OnRobotStore, EntitlementCache
    from pathlib import Path

    store = OnRobotStore(cache_dir=Path('/var/etd/cache'), node_id='robot-01')
    store.sync_from_central(entries)         # call when network available
    result = store.install_offline('etd.pickplace.basic', 'workcell-01')
    print(result)
"""
from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _is_expired(expiry: str) -> bool:
    try:
        dt = datetime.datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        return datetime.datetime.now(datetime.timezone.utc) > dt
    except Exception:
        return True


# ── CachedEntitlement ─────────────────────────────────────────────────────────

@dataclass
class CachedEntitlement:
    """A locally persisted, pre-verified entitlement token."""
    skill_id: str
    station_id: str     # '*' means any station
    operator_org: str
    expiry: str         # ISO 8601 UTC
    token_str: str      # raw wire-format token for re-verification
    cached_at: str = field(default_factory=_utcnow)
    verified_by_node: str = ''

    @property
    def is_expired(self) -> bool:
        return _is_expired(self.expiry)

    def covers(self, skill_id: str, station_id: str) -> bool:
        if self.is_expired:
            return False
        return (self.skill_id == skill_id and
                self.station_id in ('*', station_id))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'station_id': self.station_id,
            'operator_org': self.operator_org,
            'expiry': self.expiry,
            'token_str': self.token_str,
            'cached_at': self.cached_at,
            'verified_by_node': self.verified_by_node,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CachedEntitlement':
        return cls(
            skill_id=d['skill_id'],
            station_id=d['station_id'],
            operator_org=d.get('operator_org', ''),
            expiry=d['expiry'],
            token_str=d['token_str'],
            cached_at=d.get('cached_at', _utcnow()),
            verified_by_node=d.get('verified_by_node', ''),
        )


# ── EntitlementCache ──────────────────────────────────────────────────────────

class EntitlementCache:
    """JSON-backed store of pre-verified entitlement tokens.

    Parameters
    ----------
    cache_path:
        Path to the JSON cache file (created if absent).
    node_id:
        Identifier for this robot node, recorded on each cached entry.
    """

    def __init__(self, cache_path: Path, node_id: str = '') -> None:
        self._path = cache_path
        self._node_id = node_id
        self._entries: List[CachedEntitlement] = []
        if cache_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding='utf-8'))
            self._entries = [CachedEntitlement.from_dict(e) for e in data.get('entries', [])]
        except Exception:
            self._entries = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({'entries': [e.to_dict() for e in self._entries]}, indent=2),
            encoding='utf-8',
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def add(
        self,
        token_str: str,
        skill_id: str,
        station_id: str,
        operator_org: str,
        expiry: str,
        verify_key: Any = None,
    ) -> Tuple[bool, str]:
        """Add and persist a token.

        If *verify_key* is provided (a ``nacl.signing.VerifyKey``), the token
        is cryptographically re-verified before caching.

        Returns
        -------
        (success, reason)
        """
        if verify_key is not None:
            try:
                from marketplace.entitlement_token import verify_token
                valid, reason, _ = verify_token(token_str, verify_key, skill_id, station_id)
                if not valid:
                    return False, reason
            except Exception as exc:
                return False, str(exc)

        if _is_expired(expiry):
            return False, 'token_already_expired'

        entry = CachedEntitlement(
            skill_id=skill_id,
            station_id=station_id,
            operator_org=operator_org,
            expiry=expiry,
            token_str=token_str,
            verified_by_node=self._node_id,
        )
        # Replace any existing entry for the same (skill_id, station_id)
        self._entries = [
            e for e in self._entries
            if not (e.skill_id == skill_id and e.station_id == station_id)
        ]
        self._entries.append(entry)
        self._save()
        return True, 'cached'

    def get(self, skill_id: str, station_id: str) -> Optional[CachedEntitlement]:
        """Return the first valid cached entitlement for *skill_id* @ *station_id*."""
        for e in self._entries:
            if e.covers(skill_id, station_id):
                return e
        return None

    def evict_expired(self) -> int:
        """Remove expired entries and persist.  Returns count removed."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if not e.is_expired]
        removed = before - len(self._entries)
        if removed:
            self._save()
        return removed

    def list_skills(self) -> List[str]:
        """Return skill IDs with at least one valid non-expired cached token."""
        seen = set()
        result = []
        for e in self._entries:
            if not e.is_expired and e.skill_id not in seen:
                seen.add(e.skill_id)
                result.append(e.skill_id)
        return result

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def valid_count(self) -> int:
        return sum(1 for e in self._entries if not e.is_expired)


# ── SkillManifestCache ────────────────────────────────────────────────────────

@dataclass
class CachedManifest:
    """Locally cached skill package metadata."""
    skill_id: str
    version: str
    family: str
    primitive_order: List[str]
    cached_at: str = field(default_factory=_utcnow)
    source_node: str = ''
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'version': self.version,
            'family': self.family,
            'primitive_order': self.primitive_order,
            'cached_at': self.cached_at,
            'source_node': self.source_node,
            'extra': self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CachedManifest':
        return cls(
            skill_id=d['skill_id'],
            version=d['version'],
            family=d.get('family', ''),
            primitive_order=d.get('primitive_order', []),
            cached_at=d.get('cached_at', _utcnow()),
            source_node=d.get('source_node', ''),
            extra=d.get('extra', {}),
        )


class SkillManifestCache:
    """JSON-backed cache of skill package metadata for offline validation.

    Parameters
    ----------
    cache_path:
        Path to the JSON cache file (created if absent).
    """

    def __init__(self, cache_path: Path, node_id: str = '') -> None:
        self._path = cache_path
        self._node_id = node_id
        self._manifests: Dict[str, CachedManifest] = {}
        if cache_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding='utf-8'))
            for d in data.get('manifests', []):
                m = CachedManifest.from_dict(d)
                self._manifests[m.skill_id] = m
        except Exception:
            self._manifests = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {'manifests': [m.to_dict() for m in self._manifests.values()]},
                indent=2,
            ),
            encoding='utf-8',
        )

    def put(self, manifest: CachedManifest) -> None:
        """Insert or replace a manifest entry."""
        manifest.source_node = manifest.source_node or self._node_id
        self._manifests[manifest.skill_id] = manifest
        self._save()

    def get(self, skill_id: str) -> Optional[CachedManifest]:
        return self._manifests.get(skill_id)

    def list_skills(self) -> List[str]:
        return list(self._manifests.keys())

    def remove(self, skill_id: str) -> bool:
        """Remove a cached manifest.  Returns True if it existed."""
        if skill_id in self._manifests:
            del self._manifests[skill_id]
            self._save()
            return True
        return False

    @property
    def manifest_count(self) -> int:
        return len(self._manifests)


# ── MeshSync ──────────────────────────────────────────────────────────────────

@dataclass
class MeshSyncRecord:
    """Tracks last sync state with one fleet peer."""
    peer_node_id: str
    last_sync_at: Optional[str] = None
    synced_skill_ids: List[str] = field(default_factory=list)
    sync_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'peer_node_id': self.peer_node_id,
            'last_sync_at': self.last_sync_at,
            'synced_skill_ids': self.synced_skill_ids,
            'sync_count': self.sync_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'MeshSyncRecord':
        return cls(
            peer_node_id=d['peer_node_id'],
            last_sync_at=d.get('last_sync_at'),
            synced_skill_ids=d.get('synced_skill_ids', []),
            sync_count=d.get('sync_count', 0),
        )


class MeshSync:
    """Fleet peer-to-peer skill cache synchronisation.

    In this prototype the "transport" is in-memory (dict of peer → manifests).
    A production deployment would use UDP multicast or a local MQTT broker.

    Parameters
    ----------
    node_id:
        Unique identifier for this robot node.
    manifest_cache:
        The local ``SkillManifestCache`` to push/pull into.
    """

    def __init__(self, node_id: str, manifest_cache: SkillManifestCache) -> None:
        self._node_id = node_id
        self._manifest_cache = manifest_cache
        self._peers: Dict[str, MeshSyncRecord] = {}
        # In-memory peer message bus: peer_id → list of CachedManifest dicts
        self._peer_announcements: Dict[str, List[Dict[str, Any]]] = {}

    def register_peer(self, peer_id: str) -> None:
        if peer_id not in self._peers:
            self._peers[peer_id] = MeshSyncRecord(peer_node_id=peer_id)

    def announce(self, skill_id: str) -> None:
        """Broadcast a locally available skill to all registered peers."""
        manifest = self._manifest_cache.get(skill_id)
        if manifest is None:
            return
        for peer_id in self._peers:
            self._peer_announcements.setdefault(peer_id, [])
            self._peer_announcements[peer_id].append(manifest.to_dict())

    def receive_from_peer(self, peer_id: str) -> List[str]:
        """Pull pending announcements from *peer_id* into local cache.

        Returns list of skill IDs newly cached.
        """
        if peer_id not in self._peers:
            self.register_peer(peer_id)

        announcements = self._peer_announcements.pop(peer_id, [])
        imported: List[str] = []
        for d in announcements:
            m = CachedManifest.from_dict(d)
            m.source_node = peer_id
            self._manifest_cache.put(m)
            imported.append(m.skill_id)

        rec = self._peers[peer_id]
        rec.last_sync_at = _utcnow()
        rec.synced_skill_ids = list(set(rec.synced_skill_ids) | set(imported))
        rec.sync_count += 1
        return imported

    def sync_status(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._peers.values()]

    @property
    def peer_count(self) -> int:
        return len(self._peers)

    @property
    def pending_announcement_count(self) -> int:
        return sum(len(v) for v in self._peer_announcements.values())


# ── OnRobotStore ──────────────────────────────────────────────────────────────

@dataclass
class OfflineInstallResult:
    skill_id: str
    station_id: str
    success: bool
    reason: str
    entitlement: Optional[CachedEntitlement] = None
    manifest: Optional[CachedManifest] = None

    def __str__(self) -> str:
        status = 'OK' if self.success else 'FAIL'
        return f'[{status}] {self.skill_id} @ {self.station_id}: {self.reason}'


class OnRobotStore:
    """Embedded skill store for the robot compute unit.

    Provides offline-first skill execution by maintaining local caches of
    entitlement tokens and skill manifests.  When the central marketplace is
    reachable, ``sync_from_central()`` updates both caches.  Fleet peers share
    manifest updates via ``MeshSync``.

    Parameters
    ----------
    cache_dir:
        Directory for all local cache files.  Created if absent.
    node_id:
        Unique identifier for this robot node (e.g. ``'robot-arm-01'``).
    """

    def __init__(self, cache_dir: Path, node_id: str = 'robot') -> None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._node_id = node_id
        self._entitlement_cache = EntitlementCache(
            cache_dir / 'entitlements.json', node_id=node_id
        )
        self._manifest_cache = SkillManifestCache(
            cache_dir / 'manifests.json', node_id=node_id
        )
        self._mesh = MeshSync(node_id, self._manifest_cache)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def entitlement_cache(self) -> EntitlementCache:
        return self._entitlement_cache

    @property
    def manifest_cache(self) -> SkillManifestCache:
        return self._manifest_cache

    @property
    def mesh(self) -> MeshSync:
        return self._mesh

    # ── Core operations ───────────────────────────────────────────────────────

    def is_available_offline(self, skill_id: str, station_id: str = '*') -> bool:
        """Return True if both entitlement and manifest are cached and valid."""
        ent = self._entitlement_cache.get(skill_id, station_id)
        man = self._manifest_cache.get(skill_id)
        return ent is not None and man is not None

    def install_offline(
        self, skill_id: str, station_id: str = '*'
    ) -> OfflineInstallResult:
        """Serve a skill from local cache (no network required).

        Returns an :class:`OfflineInstallResult` describing the outcome.
        """
        ent = self._entitlement_cache.get(skill_id, station_id)
        if ent is None:
            return OfflineInstallResult(
                skill_id=skill_id, station_id=station_id,
                success=False, reason='no_cached_entitlement',
            )
        man = self._manifest_cache.get(skill_id)
        if man is None:
            return OfflineInstallResult(
                skill_id=skill_id, station_id=station_id,
                success=False, reason='no_cached_manifest',
                entitlement=ent,
            )
        return OfflineInstallResult(
            skill_id=skill_id, station_id=station_id,
            success=True, reason='served_from_cache',
            entitlement=ent, manifest=man,
        )

    def sync_from_central(
        self,
        entries: List[Dict[str, Any]],
        entitlement_tokens: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Update local caches from a central marketplace feed.

        Parameters
        ----------
        entries:
            List of skill store entry dicts (from ``SkillStore`` or a vendor
            feed).  Each dict should contain ``skillId``, ``version``,
            ``family``, and optionally ``primitiveOrder``.
        entitlement_tokens:
            Optional list of pre-issued token dicts with keys
            ``{token_str, skill_id, station_id, operator_org, expiry}``.

        Returns
        -------
        Dict with ``manifests_updated``, ``entitlements_cached``,
        ``entitlements_skipped``.
        """
        manifests_updated = 0
        for e in entries:
            skill_id = e.get('skillId') or e.get('skill_id', '')
            if not skill_id:
                continue
            m = CachedManifest(
                skill_id=skill_id,
                version=e.get('version', '0.0.0'),
                family=e.get('family', ''),
                primitive_order=list(e.get('primitiveOrder', e.get('primitive_order', []))),
                source_node='central',
            )
            self._manifest_cache.put(m)
            manifests_updated += 1

        entitlements_cached = 0
        entitlements_skipped = 0
        for tok in (entitlement_tokens or []):
            ok, _ = self._entitlement_cache.add(
                token_str=tok.get('token_str', ''),
                skill_id=tok.get('skill_id', ''),
                station_id=tok.get('station_id', '*'),
                operator_org=tok.get('operator_org', ''),
                expiry=tok.get('expiry', ''),
            )
            if ok:
                entitlements_cached += 1
            else:
                entitlements_skipped += 1

        return {
            'manifests_updated': manifests_updated,
            'entitlements_cached': entitlements_cached,
            'entitlements_skipped': entitlements_skipped,
        }

    def get_offline_skills(self) -> List[str]:
        """Return skill IDs available entirely offline (entitlement + manifest)."""
        result = []
        for skill_id in self._entitlement_cache.list_skills():
            if self._manifest_cache.get(skill_id) is not None:
                result.append(skill_id)
        return sorted(result)

    def evict_expired_entitlements(self) -> int:
        """Prune expired entitlements.  Returns count removed."""
        return self._entitlement_cache.evict_expired()

    def summary(self) -> str:
        n_ent = self._entitlement_cache.valid_count
        n_man = self._manifest_cache.manifest_count
        offline = len(self.get_offline_skills())
        n_peers = self._mesh.peer_count
        return (
            f'OnRobotStore [{self._node_id}]\n'
            f'  Entitlements (valid) : {n_ent}\n'
            f'  Manifest cache       : {n_man}\n'
            f'  Skills offline       : {offline}\n'
            f'  Mesh peers           : {n_peers}'
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self._node_id,
            'entitlement_count': self._entitlement_cache.entry_count,
            'valid_entitlement_count': self._entitlement_cache.valid_count,
            'manifest_count': self._manifest_cache.manifest_count,
            'offline_skills': self.get_offline_skills(),
            'peer_count': self._mesh.peer_count,
        }
