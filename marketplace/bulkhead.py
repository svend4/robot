"""ETD Skill Execution Bulkhead.

Limits the number of concurrent executions of a skill (optionally per
robot node) to prevent resource exhaustion.  Callers must ``acquire()``
a slot before starting an execution and ``release()`` it when done.

Architecture
------------
::

    BulkheadConfig  ──▶  Bulkhead  ──▶  AcquireResult
                              │          BulkheadState
                        BulkheadStore
                        (JSON-backed)

Usage::

    from marketplace.bulkhead import Bulkhead, BulkheadConfig
    from pathlib import Path

    bh = Bulkhead(data_dir=Path('bulkhead'))
    bh.set_config('etd.pickplace.basic', BulkheadConfig(max_concurrent=3))

    result = bh.acquire('etd.pickplace.basic')
    if result.acquired:
        try:
            run_skill()
        finally:
            bh.release('etd.pickplace.basic')
    else:
        print(f'Capacity exceeded: {result.active_count}/{result.max_concurrent}')
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── BulkheadConfig ────────────────────────────────────────────────────────────

@dataclass
class BulkheadConfig:
    """Concurrency limits for one skill."""
    max_concurrent: int = 10

    def __post_init__(self) -> None:
        if self.max_concurrent < 1:
            raise ValueError('max_concurrent must be >= 1')

    def to_dict(self) -> Dict[str, Any]:
        return {'max_concurrent': self.max_concurrent}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'BulkheadConfig':
        return cls(max_concurrent=int(d.get('max_concurrent', 10)))


# ── BulkheadState ─────────────────────────────────────────────────────────────

@dataclass
class BulkheadState:
    """Runtime counters for one bulkhead slot."""
    key: str
    skill_id: str
    node_id: str                # '*' = all nodes
    active_count: int = 0
    total_acquired: int = 0
    total_released: int = 0
    total_rejected: int = 0

    @property
    def utilisation(self) -> float:
        """active_count / max_concurrent (requires config to know max)."""
        return float(self.active_count)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'active_count': self.active_count,
            'total_acquired': self.total_acquired,
            'total_released': self.total_released,
            'total_rejected': self.total_rejected,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'BulkheadState':
        return cls(
            key=d['key'],
            skill_id=d['skill_id'],
            node_id=d.get('node_id', '*'),
            active_count=int(d.get('active_count', 0)),
            total_acquired=int(d.get('total_acquired', 0)),
            total_released=int(d.get('total_released', 0)),
            total_rejected=int(d.get('total_rejected', 0)),
        )


# ── AcquireResult ─────────────────────────────────────────────────────────────

@dataclass
class AcquireResult:
    """Result of an acquire() call."""
    acquired: bool
    reason: str           # 'ok' | 'capacity_exceeded'
    skill_id: str
    node_id: str
    active_count: int
    max_concurrent: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'acquired': self.acquired,
            'reason': self.reason,
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'active_count': self.active_count,
            'max_concurrent': self.max_concurrent,
        }


# ── BulkheadStore ─────────────────────────────────────────────────────────────

def _make_key(skill_id: str, node_id: str) -> str:
    return skill_id if node_id == '*' else f'{skill_id}:{node_id}'


class BulkheadStore:
    """JSON-backed persistence for bulkhead states and configs."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._states: Dict[str, BulkheadState] = {}
        self._configs: Dict[str, BulkheadConfig] = {}
        if (self._dir / 'bulkhead.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'bulkhead.json').read_text(encoding='utf-8')
            )
            self._states = {
                k: BulkheadState.from_dict(v)
                for k, v in raw.get('states', {}).items()
            }
            self._configs = {
                k: BulkheadConfig.from_dict(v)
                for k, v in raw.get('configs', {}).items()
            }
        except Exception:
            self._states = {}
            self._configs = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'bulkhead.json').write_text(
            json.dumps({
                'states': {k: v.to_dict() for k, v in self._states.items()},
                'configs': {k: v.to_dict() for k, v in self._configs.items()},
            }, indent=2),
            encoding='utf-8',
        )

    def get_or_create_state(self, skill_id: str, node_id: str) -> BulkheadState:
        key = _make_key(skill_id, node_id)
        if key not in self._states:
            self._states[key] = BulkheadState(
                key=key, skill_id=skill_id, node_id=node_id,
            )
        return self._states[key]

    def save_state(self, state: BulkheadState) -> None:
        self._states[state.key] = state
        self._flush()

    def get_state(self, skill_id: str, node_id: str) -> Optional[BulkheadState]:
        return self._states.get(_make_key(skill_id, node_id))

    def remove_state(self, skill_id: str, node_id: str) -> bool:
        key = _make_key(skill_id, node_id)
        if key not in self._states:
            return False
        del self._states[key]
        self._flush()
        return True

    def list_states(self) -> List[BulkheadState]:
        return list(self._states.values())

    def get_config(self, skill_id: str) -> Optional[BulkheadConfig]:
        return self._configs.get(skill_id)

    def set_config(self, skill_id: str, config: BulkheadConfig) -> None:
        self._configs[skill_id] = config
        self._flush()

    def remove_config(self, skill_id: str) -> bool:
        if skill_id not in self._configs:
            return False
        del self._configs[skill_id]
        self._flush()
        return True

    def list_configs(self) -> Dict[str, BulkheadConfig]:
        return dict(self._configs)


# ── Bulkhead ──────────────────────────────────────────────────────────────────

class Bulkhead:
    """Per-skill concurrency limiter.

    Parameters
    ----------
    data_dir:
        Directory for persisting state and configs to ``bulkhead.json``.
    default_config:
        Fallback ``BulkheadConfig`` when no per-skill config is registered.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        default_config: Optional[BulkheadConfig] = None,
    ) -> None:
        self._store = BulkheadStore(data_dir or Path('bulkhead'))
        self._default = default_config or BulkheadConfig()

    def get_config(self, skill_id: str) -> BulkheadConfig:
        return self._store.get_config(skill_id) or self._default

    def set_config(self, skill_id: str, config: BulkheadConfig) -> None:
        self._store.set_config(skill_id, config)

    def remove_config(self, skill_id: str) -> bool:
        return self._store.remove_config(skill_id)

    def list_configs(self) -> Dict[str, BulkheadConfig]:
        return self._store.list_configs()

    def acquire(self, skill_id: str, node_id: str = '*') -> AcquireResult:
        """Attempt to acquire a concurrency slot.

        Returns an ``AcquireResult`` indicating whether the slot was granted.
        Does NOT raise; callers must check ``result.acquired``.
        """
        cfg = self.get_config(skill_id)
        state = self._store.get_or_create_state(skill_id, node_id)

        if state.active_count >= cfg.max_concurrent:
            state.total_rejected += 1
            self._store.save_state(state)
            return AcquireResult(
                acquired=False,
                reason='capacity_exceeded',
                skill_id=skill_id,
                node_id=node_id,
                active_count=state.active_count,
                max_concurrent=cfg.max_concurrent,
            )

        state.active_count += 1
        state.total_acquired += 1
        self._store.save_state(state)
        return AcquireResult(
            acquired=True,
            reason='ok',
            skill_id=skill_id,
            node_id=node_id,
            active_count=state.active_count,
            max_concurrent=cfg.max_concurrent,
        )

    def release(self, skill_id: str, node_id: str = '*') -> bool:
        """Release a previously acquired concurrency slot.

        Returns ``False`` if there is no active slot to release (i.e. the
        active_count is already 0 or the state does not exist).
        """
        state = self._store.get_state(skill_id, node_id)
        if state is None or state.active_count <= 0:
            return False
        state.active_count -= 1
        state.total_released += 1
        self._store.save_state(state)
        return True

    def reset(self, skill_id: str, node_id: str = '*') -> bool:
        """Reset active_count to 0 for a bulkhead. Returns False if not found."""
        state = self._store.get_state(skill_id, node_id)
        if state is None:
            return False
        state.active_count = 0
        self._store.save_state(state)
        return True

    def get_state(self, skill_id: str, node_id: str = '*') -> Optional[BulkheadState]:
        return self._store.get_state(skill_id, node_id)

    def list_states(self) -> List[BulkheadState]:
        return self._store.list_states()

    @property
    def state_count(self) -> int:
        return len(self._store.list_states())
