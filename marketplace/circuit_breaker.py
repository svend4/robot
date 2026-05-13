"""ETD Skill Execution Circuit Breaker.

Implements the classic three-state circuit breaker pattern per skill (or per
skill+node pair) to halt execution attempts when a skill is consistently
failing and resume them gradually once the failure window has elapsed.

States
------
``closed``    — normal operation; executions pass through.
``open``      — circuit tripped; executions rejected immediately.
``half_open`` — trial period; a limited number of executions are allowed to
                test whether the skill has recovered.

Transitions
-----------
``closed``   → ``open``      when failure_count >= failure_threshold
                              OR failure_rate >= failure_rate_threshold
                              (requires min_executions for rate check).
``open``     → ``half_open`` when reset_timeout_seconds has elapsed since
                              the circuit was opened.
``half_open``→ ``closed``    when half_open_successes >= half_open_max_calls.
``half_open``→ ``open``      on any failure in the half-open window.

Architecture
------------
::

    CircuitBreakerConfig  ──▶  CircuitBreaker  ──▶  CircuitBreakerResult
                                     │               CircuitBreakerState
                               CircuitStore
                               (JSON-backed)

Usage::

    from marketplace.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
    from pathlib import Path

    cb = CircuitBreaker(data_dir=Path('circuits'))
    result = cb.allow_execution('etd.pickplace.basic')
    if result.allowed:
        # run the skill
        cb.record_success('etd.pickplace.basic')
    else:
        print(f'Circuit {result.state}: {result.reason}')
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat(timespec='seconds')


def _parse_iso(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)


# ── CircuitBreakerConfig ──────────────────────────────────────────────────────

@dataclass
class CircuitBreakerConfig:
    """Thresholds that govern state transitions."""
    failure_threshold: int = 5        # consecutive/total failures → open
    failure_rate_threshold: float = 0.5  # failure rate → open (needs min_executions)
    min_executions: int = 3           # minimum calls before rate check applies
    reset_timeout_seconds: int = 60   # seconds open before moving to half_open
    half_open_max_calls: int = 2      # successes in half_open → closed

    def to_dict(self) -> Dict[str, Any]:
        return {
            'failure_threshold': self.failure_threshold,
            'failure_rate_threshold': self.failure_rate_threshold,
            'min_executions': self.min_executions,
            'reset_timeout_seconds': self.reset_timeout_seconds,
            'half_open_max_calls': self.half_open_max_calls,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CircuitBreakerConfig':
        return cls(
            failure_threshold=int(d.get('failure_threshold', 5)),
            failure_rate_threshold=float(d.get('failure_rate_threshold', 0.5)),
            min_executions=int(d.get('min_executions', 3)),
            reset_timeout_seconds=int(d.get('reset_timeout_seconds', 60)),
            half_open_max_calls=int(d.get('half_open_max_calls', 2)),
        )


# ── CircuitBreakerState ───────────────────────────────────────────────────────

@dataclass
class CircuitBreakerState:
    """Persisted runtime state for one circuit."""
    key: str                          # '{skill_id}' or '{skill_id}:{node_id}'
    skill_id: str
    node_id: str                      # '*' = all nodes
    state: str = 'closed'             # 'closed' | 'open' | 'half_open'
    failure_count: int = 0
    success_count: int = 0            # total successes tracked
    half_open_successes: int = 0      # successes since entering half_open
    half_open_calls: int = 0          # calls permitted through in half_open
    total_calls: int = 0
    opened_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_state_change_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'state': self.state,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'half_open_successes': self.half_open_successes,
            'half_open_calls': self.half_open_calls,
            'total_calls': self.total_calls,
            'opened_at': self.opened_at,
            'last_failure_at': self.last_failure_at,
            'last_success_at': self.last_success_at,
            'last_state_change_at': self.last_state_change_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CircuitBreakerState':
        return cls(
            key=d['key'],
            skill_id=d['skill_id'],
            node_id=d.get('node_id', '*'),
            state=d.get('state', 'closed'),
            failure_count=int(d.get('failure_count', 0)),
            success_count=int(d.get('success_count', 0)),
            half_open_successes=int(d.get('half_open_successes', 0)),
            half_open_calls=int(d.get('half_open_calls', 0)),
            total_calls=int(d.get('total_calls', 0)),
            opened_at=d.get('opened_at'),
            last_failure_at=d.get('last_failure_at'),
            last_success_at=d.get('last_success_at'),
            last_state_change_at=d.get('last_state_change_at'),
        )

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failure_count / self.total_calls


# ── CircuitBreakerResult ──────────────────────────────────────────────────────

@dataclass
class CircuitBreakerResult:
    """Result of an allow_execution() check."""
    allowed: bool
    reason: str            # 'ok' | 'open' | 'half_open_quota_exceeded'
    state: str
    skill_id: str
    node_id: str
    remaining_half_open: Optional[int] = None  # only in half_open state

    def to_dict(self) -> Dict[str, Any]:
        return {
            'allowed': self.allowed,
            'reason': self.reason,
            'state': self.state,
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'remaining_half_open': self.remaining_half_open,
        }


# ── CircuitBreakerStore ───────────────────────────────────────────────────────

class CircuitBreakerStore:
    """JSON-backed persistence for circuit breaker states."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._states: Dict[str, CircuitBreakerState] = {}
        path = self._dir / 'circuits.json'
        if path.exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'circuits.json').read_text(encoding='utf-8')
            )
            self._states = {k: CircuitBreakerState.from_dict(v)
                            for k, v in raw.items()}
        except Exception:
            self._states = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'circuits.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._states.items()},
                       indent=2),
            encoding='utf-8',
        )

    def get_or_create(self, skill_id: str, node_id: str = '*') -> CircuitBreakerState:
        key = _make_key(skill_id, node_id)
        if key not in self._states:
            self._states[key] = CircuitBreakerState(
                key=key, skill_id=skill_id, node_id=node_id,
            )
        return self._states[key]

    def save(self, state: CircuitBreakerState) -> None:
        self._states[state.key] = state
        self._flush()

    def get(self, skill_id: str, node_id: str = '*') -> Optional[CircuitBreakerState]:
        return self._states.get(_make_key(skill_id, node_id))

    def remove(self, skill_id: str, node_id: str = '*') -> bool:
        key = _make_key(skill_id, node_id)
        if key not in self._states:
            return False
        del self._states[key]
        self._flush()
        return True

    def list_states(self) -> List[CircuitBreakerState]:
        return list(self._states.values())

    @property
    def breaker_count(self) -> int:
        return len(self._states)


def _make_key(skill_id: str, node_id: str) -> str:
    return skill_id if node_id == '*' else f'{skill_id}:{node_id}'


# ── CircuitBreaker ────────────────────────────────────────────────────────────

class CircuitBreaker:
    """Per-skill (optionally per-node) circuit breaker.

    Parameters
    ----------
    data_dir:
        Directory for persisting state to ``circuits.json``.
    config:
        Default ``CircuitBreakerConfig`` applied to all circuits unless
        per-skill config is provided via ``set_config()``.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self._store = CircuitBreakerStore(data_dir or Path('circuits'))
        self._default_config = config or CircuitBreakerConfig()
        self._configs: Dict[str, CircuitBreakerConfig] = {}

    def set_config(self, skill_id: str, config: CircuitBreakerConfig) -> None:
        """Override the default config for a specific skill."""
        self._configs[skill_id] = config

    def get_config(self, skill_id: str) -> CircuitBreakerConfig:
        return self._configs.get(skill_id, self._default_config)

    # ── state machine helpers ─────────────────────────────────────────────────

    def _maybe_transition_open_to_half_open(
        self, state: CircuitBreakerState, cfg: CircuitBreakerConfig,
        now: datetime.datetime,
    ) -> None:
        """Promote open → half_open if the timeout has elapsed."""
        if state.state != 'open' or state.opened_at is None:
            return
        elapsed = (now - _parse_iso(state.opened_at)).total_seconds()
        if elapsed >= cfg.reset_timeout_seconds:
            state.state = 'half_open'
            state.half_open_successes = 0
            state.half_open_calls = 0
            state.last_state_change_at = now.isoformat(timespec='seconds')

    def _should_open(
        self, state: CircuitBreakerState, cfg: CircuitBreakerConfig,
    ) -> bool:
        if state.failure_count >= cfg.failure_threshold:
            return True
        if (state.total_calls >= cfg.min_executions
                and state.failure_rate >= cfg.failure_rate_threshold):
            return True
        return False

    def _open_circuit(
        self, state: CircuitBreakerState, now: datetime.datetime,
    ) -> None:
        state.state = 'open'
        state.opened_at = now.isoformat(timespec='seconds')
        state.last_state_change_at = now.isoformat(timespec='seconds')
        state.half_open_successes = 0
        state.half_open_calls = 0

    # ── public API ────────────────────────────────────────────────────────────

    def allow_execution(
        self,
        skill_id: str,
        node_id: str = '*',
        _now: Optional[datetime.datetime] = None,
    ) -> CircuitBreakerResult:
        """Check whether an execution attempt should be allowed.

        Does NOT record the call; call ``record_success`` / ``record_failure``
        after the execution completes.
        """
        now = _now or _utcnow()
        cfg = self.get_config(skill_id)
        state = self._store.get_or_create(skill_id, node_id)
        self._maybe_transition_open_to_half_open(state, cfg, now)

        if state.state == 'closed':
            return CircuitBreakerResult(
                allowed=True, reason='ok', state='closed',
                skill_id=skill_id, node_id=node_id,
            )

        if state.state == 'open':
            self._store.save(state)
            return CircuitBreakerResult(
                allowed=False, reason='open', state='open',
                skill_id=skill_id, node_id=node_id,
            )

        # half_open — allow up to half_open_max_calls test calls
        remaining = cfg.half_open_max_calls - state.half_open_calls
        if remaining > 0:
            state.half_open_calls += 1
            self._store.save(state)
            return CircuitBreakerResult(
                allowed=True, reason='ok', state='half_open',
                skill_id=skill_id, node_id=node_id,
                remaining_half_open=remaining,
            )
        self._store.save(state)
        return CircuitBreakerResult(
            allowed=False, reason='half_open_quota_exceeded', state='half_open',
            skill_id=skill_id, node_id=node_id, remaining_half_open=0,
        )

    def record_success(
        self,
        skill_id: str,
        node_id: str = '*',
        _now: Optional[datetime.datetime] = None,
    ) -> CircuitBreakerState:
        """Record a successful execution; may close the circuit."""
        now = _now or _utcnow()
        cfg = self.get_config(skill_id)
        state = self._store.get_or_create(skill_id, node_id)
        state.total_calls += 1
        state.success_count += 1
        state.last_success_at = now.isoformat(timespec='seconds')

        if state.state == 'half_open':
            state.half_open_successes += 1
            if state.half_open_successes >= cfg.half_open_max_calls:
                state.state = 'closed'
                state.failure_count = 0
                state.opened_at = None
                state.last_state_change_at = now.isoformat(timespec='seconds')

        self._store.save(state)
        return state

    def record_failure(
        self,
        skill_id: str,
        node_id: str = '*',
        _now: Optional[datetime.datetime] = None,
    ) -> CircuitBreakerState:
        """Record a failed execution; may open or reopen the circuit."""
        now = _now or _utcnow()
        cfg = self.get_config(skill_id)
        state = self._store.get_or_create(skill_id, node_id)
        state.total_calls += 1
        state.failure_count += 1
        state.last_failure_at = now.isoformat(timespec='seconds')

        if state.state == 'half_open':
            # Any failure in half_open reopens immediately
            self._open_circuit(state, now)
        elif state.state == 'closed' and self._should_open(state, cfg):
            self._open_circuit(state, now)

        self._store.save(state)
        return state

    def reset(self, skill_id: str, node_id: str = '*') -> bool:
        """Manually reset a circuit to closed. Returns False if not found."""
        state = self._store.get(skill_id, node_id)
        if state is None:
            return False
        state.state = 'closed'
        state.failure_count = 0
        state.half_open_successes = 0
        state.half_open_calls = 0
        state.opened_at = None
        state.last_state_change_at = _utcnow_iso()
        self._store.save(state)
        return True

    def get_state(
        self, skill_id: str, node_id: str = '*',
    ) -> Optional[CircuitBreakerState]:
        return self._store.get(skill_id, node_id)

    def list_breakers(self) -> List[CircuitBreakerState]:
        return self._store.list_states()

    def remove(self, skill_id: str, node_id: str = '*') -> bool:
        return self._store.remove(skill_id, node_id)

    @property
    def breaker_count(self) -> int:
        return self._store.breaker_count
