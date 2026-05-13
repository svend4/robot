"""ETD Skill Dependency Resolver.

Skills may declare prerequisite skills they depend on.  This module provides
a dependency graph, topological install-order computation, cycle detection,
and a persistent registry of skill dependency declarations.

Architecture
------------
::

    DependencyStore  ──▶  DependencyResolver  ──▶  DependencyGraph
      (JSON-backed)         install_order()          resolve() / cycles()
                            check_satisfied()        transitive_deps()
                            dependency_tree()

Key abstractions
----------------
``SkillDependency``
    One edge in the dependency graph: the ID of a required skill,
    an optional SemVer-style version constraint string (informational),
    and an ``optional`` flag.

``DependencyGraph``
    Directed graph of ``skill_id → [dep_skill_id, ...]``.  Pure graph
    logic; no version awareness.

    ``resolve(skill_id)``
        Depth-first topological sort; returns install order with
        *skill_id* last.  Raises ``CyclicDependencyError`` on a cycle.

    ``detect_cycles()``
        Returns all cycles found in the full graph as lists of skill IDs.

    ``transitive_deps(skill_id)``
        All transitive dependencies (excluding the root skill itself).

    ``missing(skill_id, available)``
        Required (non-optional) deps not in the *available* set.

``DependencyResolver``
    Higher-level wrapper around a ``{skill_id: [SkillDependency]}`` registry.
    ``install_order()``, ``check_satisfied()``, ``dependency_tree()``.

``DependencyStore``
    JSON-backed persistent registry of ``SkillDependency`` lists, keyed
    by ``skill_id``.

Usage::

    from marketplace.dependency_resolver import (
        DependencyStore, DependencyResolver, SkillDependency,
    )
    from pathlib import Path

    store = DependencyStore(Path('deps'))
    store.register('etd.composed.pipeline', [
        SkillDependency('etd.pickplace.basic'),
        SkillDependency('etd.inspect.vision'),
    ])

    resolver = DependencyResolver(store.as_dict())
    order = resolver.install_order('etd.composed.pipeline')
    # → ['etd.pickplace.basic', 'etd.inspect.vision', 'etd.composed.pipeline']
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ── errors ────────────────────────────────────────────────────────────────────

class CyclicDependencyError(Exception):
    """Raised when a dependency cycle is detected during resolution."""


# ── SkillDependency ───────────────────────────────────────────────────────────

@dataclass
class SkillDependency:
    """One prerequisite skill declaration."""
    skill_id: str
    version_constraint: str = ''   # e.g. '>=0.1.0' (informational only)
    optional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'version_constraint': self.version_constraint,
            'optional': self.optional,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SkillDependency':
        return cls(
            skill_id=d['skill_id'],
            version_constraint=d.get('version_constraint', ''),
            optional=bool(d.get('optional', False)),
        )


# ── DependencyGraph ───────────────────────────────────────────────────────────

class DependencyGraph:
    """Directed graph of skill dependencies (skill_id → [dep_skill_id]).

    Stores only the edge topology; no version or optional metadata.
    """

    def __init__(self) -> None:
        self._adj: Dict[str, List[str]] = {}   # node → [dep, ...]

    def add_skill(self, skill_id: str, dep_ids: List[str]) -> None:
        """Register *skill_id* with its direct dependency IDs."""
        self._adj[skill_id] = list(dep_ids)
        # Ensure dep nodes exist (as leaves if not already declared)
        for dep in dep_ids:
            if dep not in self._adj:
                self._adj[dep] = []

    def skills(self) -> List[str]:
        return list(self._adj.keys())

    # ── topological sort ──────────────────────────────────────────────────────

    def resolve(self, skill_id: str) -> List[str]:
        """Return install order ending with *skill_id*.

        Uses iterative DFS with a temporary/permanent mark scheme.
        Raises ``CyclicDependencyError`` if a cycle is detected.
        """
        if skill_id not in self._adj:
            return [skill_id]

        order: List[str] = []
        permanent: Set[str] = set()
        temporary: Set[str] = set()

        def visit(node: str) -> None:
            if node in permanent:
                return
            if node in temporary:
                raise CyclicDependencyError(
                    f'Cycle detected involving skill: {node!r}'
                )
            temporary.add(node)
            for dep in self._adj.get(node, []):
                visit(dep)
            temporary.discard(node)
            permanent.add(node)
            order.append(node)

        visit(skill_id)
        return order

    # ── cycle detection ───────────────────────────────────────────────────────

    def detect_cycles(self) -> List[List[str]]:
        """Return a list of cycles found in the full graph.

        Each cycle is represented as the list of skill IDs forming the loop
        (the first ID is repeated at the end for clarity).
        """
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []
        in_stack: Set[str] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            in_stack.add(node)
            for dep in self._adj.get(node, []):
                if dep not in visited:
                    dfs(dep)
                elif dep in in_stack:
                    # Found a cycle — extract the cycle path
                    idx = rec_stack.index(dep)
                    cycle = rec_stack[idx:] + [dep]
                    if cycle not in cycles:
                        cycles.append(cycle)
            rec_stack.pop()
            in_stack.discard(node)

        for node in list(self._adj.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    # ── helpers ───────────────────────────────────────────────────────────────

    def transitive_deps(self, skill_id: str) -> List[str]:
        """Return all transitive dependencies (excluding *skill_id* itself)."""
        try:
            order = self.resolve(skill_id)
        except CyclicDependencyError:
            return []
        return [s for s in order if s != skill_id]

    def missing(
        self,
        skill_id: str,
        available: Set[str],
        *,
        required_only: bool = True,
    ) -> List[str]:
        """Return deps of *skill_id* (direct, non-optional) not in *available*."""
        deps = self._adj.get(skill_id, [])
        return [d for d in deps if d not in available]


# ── DependencyResolver ────────────────────────────────────────────────────────

class DependencyResolver:
    """High-level dependency resolution over a registry of SkillDependency lists.

    Parameters
    ----------
    registry:
        Mapping of ``skill_id → List[SkillDependency]``.
    """

    def __init__(self, registry: Dict[str, List[SkillDependency]]) -> None:
        self._registry = registry
        self._graph = self._build_graph()

    def _build_graph(self) -> DependencyGraph:
        g = DependencyGraph()
        for skill_id, deps in self._registry.items():
            g.add_skill(skill_id, [d.skill_id for d in deps])
        return g

    def install_order(self, skill_id: str) -> List[str]:
        """Return full topological install order ending with *skill_id*."""
        return self._graph.resolve(skill_id)

    def check_satisfied(
        self,
        skill_id: str,
        available: Set[str],
    ) -> tuple[bool, List[str]]:
        """Check whether all required deps of *skill_id* are in *available*.

        Returns ``(satisfied, missing_ids)`` where ``missing_ids`` is the list
        of required dependency IDs absent from *available*.
        """
        deps = self._registry.get(skill_id, [])
        missing = [
            d.skill_id for d in deps
            if not d.optional and d.skill_id not in available
        ]
        return (len(missing) == 0, missing)

    def dependency_tree(
        self,
        skill_id: str,
        _visited: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Return a nested dict tree rooted at *skill_id*."""
        if _visited is None:
            _visited = set()
        if skill_id in _visited:
            return {'skill_id': skill_id, 'cycle': True, 'deps': []}
        _visited = _visited | {skill_id}
        deps = self._registry.get(skill_id, [])
        return {
            'skill_id': skill_id,
            'deps': [
                {
                    **self.dependency_tree(d.skill_id, _visited),
                    'optional': d.optional,
                    'version_constraint': d.version_constraint,
                }
                for d in deps
            ],
        }

    def cycles(self) -> List[List[str]]:
        return self._graph.detect_cycles()

    @classmethod
    def from_dict(
        cls,
        d: Dict[str, List[Dict[str, Any]]],
    ) -> 'DependencyResolver':
        """Build from ``{skill_id: [{skill_id, version_constraint, optional}]}``.
        """
        registry: Dict[str, List[SkillDependency]] = {}
        for skill_id, dep_list in d.items():
            registry[skill_id] = [
                SkillDependency.from_dict(dep) if isinstance(dep, dict)
                else SkillDependency(skill_id=dep)
                for dep in dep_list
            ]
        return cls(registry)


# ── DependencyStore ───────────────────────────────────────────────────────────

class DependencyStore:
    """JSON-backed persistent store of skill dependency declarations.

    Parameters
    ----------
    data_dir:
        Directory for ``deps.json``.  Created on first write if absent.
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._registry: Dict[str, List[SkillDependency]] = {}
        deps_path = self._dir / 'deps.json'
        if deps_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'deps.json').read_text(encoding='utf-8')
            )
            self._registry = {
                k: [SkillDependency.from_dict(d) for d in v]
                for k, v in raw.items()
            }
        except Exception:
            self._registry = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'deps.json').write_text(
            json.dumps(
                {k: [d.to_dict() for d in v]
                 for k, v in self._registry.items()},
                indent=2,
            ),
            encoding='utf-8',
        )

    def register(
        self,
        skill_id: str,
        deps: List[SkillDependency],
    ) -> None:
        """Register or replace dependency list for *skill_id*."""
        self._registry[skill_id] = list(deps)
        self._flush()

    def get(self, skill_id: str) -> Optional[List[SkillDependency]]:
        return self._registry.get(skill_id)

    def remove(self, skill_id: str) -> bool:
        if skill_id not in self._registry:
            return False
        del self._registry[skill_id]
        self._flush()
        return True

    def list_skills(self) -> List[str]:
        return list(self._registry.keys())

    def as_dict(self) -> Dict[str, List[SkillDependency]]:
        return dict(self._registry)

    def resolver(self) -> DependencyResolver:
        """Return a ``DependencyResolver`` over the current registry."""
        return DependencyResolver(self.as_dict())

    @property
    def skill_count(self) -> int:
        return len(self._registry)
