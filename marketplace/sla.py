"""ETD Skill SLA Tracker.

Define per-skill SLA policies (max p95 latency in ms, minimum success rate)
and evaluate compliance against execution records.

Evaluation is a pure function that accepts a list of execution dicts so it
works independently of any telemetry store — callers supply the data.

Usage::

    from marketplace.sla import SLAStore
    from pathlib import Path

    store = SLAStore(Path('sla'))
    store.set_policy('etd.pickplace.basic',
                     max_p95_ms=2000, min_success_rate=0.95)

    executions = [
        {'status': 'success', 'total_duration_ms': 1200},
        {'status': 'success', 'total_duration_ms': 1800},
        {'status': 'failed',  'total_duration_ms': 500},
    ]
    result = store.evaluate('etd.pickplace.basic', executions)
    # result.compliant → False  (success_rate 0.67 < 0.95)
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _percentile(values: List[float], p: float) -> float:
    """Return the *p*-th percentile (0–100) of *values* (sorted ascending)."""
    if not values:
        return 0.0
    sv = sorted(values)
    idx = (p / 100) * (len(sv) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sv) - 1)
    frac = idx - lo
    return round(sv[lo] + frac * (sv[hi] - sv[lo]), 2)


# ── SLAPolicy ─────────────────────────────────────────────────────────────────

@dataclass
class SLAPolicy:
    """SLA targets for one skill."""
    skill_id: str
    max_p95_ms: Optional[int] = None       # p95 latency ceiling (ms); None = no target
    min_success_rate: Optional[float] = None  # 0.0–1.0; None = no target
    window_hours: int = 24
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'max_p95_ms': self.max_p95_ms,
            'min_success_rate': self.min_success_rate,
            'window_hours': self.window_hours,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SLAPolicy':
        return cls(
            skill_id=d['skill_id'],
            max_p95_ms=d.get('max_p95_ms'),
            min_success_rate=d.get('min_success_rate'),
            window_hours=d.get('window_hours', 24),
            created_at=d.get('created_at', _utcnow()),
            updated_at=d.get('updated_at', _utcnow()),
        )


# ── SLAViolation ──────────────────────────────────────────────────────────────

@dataclass
class SLAViolation:
    """One SLA breach."""
    field: str          # 'latency_p95' | 'success_rate'
    threshold: float
    actual: float
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'field': self.field,
            'threshold': self.threshold,
            'actual': self.actual,
            'message': self.message,
        }


# ── SLAResult ─────────────────────────────────────────────────────────────────

@dataclass
class SLAResult:
    """Evaluation result for one skill against its SLA policy."""
    skill_id: str
    compliant: bool
    violations: List[SLAViolation]
    p95_ms: Optional[float]
    success_rate: Optional[float]
    sample_count: int
    evaluated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'compliant': self.compliant,
            'violations': [v.to_dict() for v in self.violations],
            'p95_ms': self.p95_ms,
            'success_rate': self.success_rate,
            'sample_count': self.sample_count,
            'evaluated_at': self.evaluated_at,
        }


# ── SLAStore ──────────────────────────────────────────────────────────────────

class SLAStore:
    """JSON-backed store for SLA policies with evaluation logic.

    Storage: ``sla_policies.json`` — dict keyed by ``skill_id``.
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._policies: Dict[str, SLAPolicy] = {}
        if (self._dir / 'sla_policies.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'sla_policies.json').read_text(encoding='utf-8')
            )
            self._policies = {k: SLAPolicy.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._policies = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'sla_policies.json').write_text(
            json.dumps(
                {k: v.to_dict() for k, v in self._policies.items()},
                indent=2,
            ),
            encoding='utf-8',
        )

    # ── Policy CRUD ───────────────────────────────────────────────────────────

    def set_policy(
        self,
        skill_id: str,
        max_p95_ms: Optional[int] = None,
        min_success_rate: Optional[float] = None,
        window_hours: int = 24,
    ) -> tuple[SLAPolicy, bool]:
        """Create or update an SLA policy.

        Returns ``(policy, created)`` where *created* is ``True`` for new entries.
        Raises ``ValueError`` if ``min_success_rate`` is not in [0, 1].
        """
        if min_success_rate is not None and not 0.0 <= min_success_rate <= 1.0:
            raise ValueError(
                f'min_success_rate must be 0.0–1.0, got {min_success_rate!r}'
            )
        existing = self._policies.get(skill_id)
        if existing is None:
            policy = SLAPolicy(skill_id=skill_id, max_p95_ms=max_p95_ms,
                               min_success_rate=min_success_rate,
                               window_hours=window_hours)
            self._policies[skill_id] = policy
            self._flush()
            return policy, True
        existing.max_p95_ms = max_p95_ms
        existing.min_success_rate = min_success_rate
        existing.window_hours = window_hours
        existing.updated_at = _utcnow()
        self._flush()
        return existing, False

    def get_policy(self, skill_id: str) -> Optional[SLAPolicy]:
        return self._policies.get(skill_id)

    def remove_policy(self, skill_id: str) -> bool:
        if skill_id not in self._policies:
            return False
        del self._policies[skill_id]
        self._flush()
        return True

    def list_policies(self) -> List[SLAPolicy]:
        return list(self._policies.values())

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    # ── Evaluation ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        skill_id: str,
        executions: List[Dict[str, Any]],
    ) -> Optional[SLAResult]:
        """Evaluate *executions* against the SLA policy for *skill_id*.

        Returns ``None`` if no policy exists for the skill.

        Each execution dict must have at minimum a ``'status'`` key.
        ``'status' == 'success'`` counts as a success; anything else is a failure.
        ``'total_duration_ms'`` (int) is used for latency; executions without
        this key are excluded from latency calculations.
        """
        policy = self._policies.get(skill_id)
        if policy is None:
            return None

        n = len(executions)
        successes = [e for e in executions if e.get('status') == 'success']
        success_rate = round(len(successes) / n, 4) if n > 0 else None

        durations = [e['total_duration_ms'] for e in executions
                     if 'total_duration_ms' in e]
        p95 = _percentile(durations, 95) if durations else None

        violations: List[SLAViolation] = []

        if policy.max_p95_ms is not None and p95 is not None:
            if p95 > policy.max_p95_ms:
                violations.append(SLAViolation(
                    field='latency_p95',
                    threshold=float(policy.max_p95_ms),
                    actual=p95,
                    message=(f'p95 latency {p95} ms exceeds limit '
                             f'{policy.max_p95_ms} ms'),
                ))

        if policy.min_success_rate is not None and success_rate is not None:
            if success_rate < policy.min_success_rate:
                violations.append(SLAViolation(
                    field='success_rate',
                    threshold=policy.min_success_rate,
                    actual=success_rate,
                    message=(f'success rate {success_rate:.1%} below minimum '
                             f'{policy.min_success_rate:.1%}'),
                ))

        return SLAResult(
            skill_id=skill_id,
            compliant=len(violations) == 0,
            violations=violations,
            p95_ms=p95,
            success_rate=success_rate,
            sample_count=n,
        )
