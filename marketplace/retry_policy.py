"""ETD Skill Execution Retry Policy.

Provides per-skill retry configuration with three backoff strategies and a
stateless ``RetryEngine`` that computes whether to retry and with what delay.

Backoff strategies
------------------
``fixed``        — same delay every attempt: ``base_delay_ms``
``linear``       — delay grows linearly: ``base_delay_ms * attempt``
``exponential``  — delay doubles each attempt: ``base_delay_ms * 2^(attempt-1)``

All strategies are capped at ``max_delay_ms`` and may add up to ``jitter_ms``
of uniform random noise.

Architecture
------------
::

    RetryConfig  ──▶  RetryEngine  ──▶  RetryDecision
                           │
                     RetryPolicyStore
                     (JSON-backed)

Usage::

    from marketplace.retry_policy import RetryEngine, RetryConfig
    from pathlib import Path

    engine = RetryEngine(data_dir=Path('retry'))
    decision = engine.should_retry('etd.pickplace.basic', attempt=1,
                                   last_status='failed')
    if decision.retry:
        time.sleep(decision.delay_ms / 1000)
        # re-run the skill
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── BackoffStrategy constants ─────────────────────────────────────────────────

FIXED = 'fixed'
LINEAR = 'linear'
EXPONENTIAL = 'exponential'

_VALID_STRATEGIES = {FIXED, LINEAR, EXPONENTIAL}


# ── RetryConfig ───────────────────────────────────────────────────────────────

@dataclass
class RetryConfig:
    """Per-skill retry configuration."""
    max_attempts: int = 3               # total attempts including the first
    backoff: str = EXPONENTIAL          # 'fixed' | 'linear' | 'exponential'
    base_delay_ms: int = 500
    max_delay_ms: int = 30_000
    jitter_ms: int = 100                # uniform random added to each delay
    retryable_statuses: List[str] = field(
        default_factory=lambda: ['failed', 'aborted']
    )

    def __post_init__(self) -> None:
        if self.backoff not in _VALID_STRATEGIES:
            raise ValueError(
                f'backoff must be one of {sorted(_VALID_STRATEGIES)}, '
                f'got {self.backoff!r}'
            )
        if self.max_attempts < 1:
            raise ValueError('max_attempts must be >= 1')
        if self.base_delay_ms < 0:
            raise ValueError('base_delay_ms must be >= 0')
        if self.max_delay_ms < 0:
            raise ValueError('max_delay_ms must be >= 0')

    def delay_for_attempt(self, attempt: int, _rng: Optional[random.Random] = None) -> int:
        """Compute delay in ms before *attempt* (1-based, first retry = attempt 2).

        Jitter is uniform random in [0, jitter_ms].
        """
        rng = _rng or random
        if attempt <= 1:
            return 0  # no delay before the very first attempt
        n = attempt - 1  # retry number (1, 2, 3…)
        if self.backoff == FIXED:
            base = self.base_delay_ms
        elif self.backoff == LINEAR:
            base = self.base_delay_ms * n
        else:  # EXPONENTIAL
            base = self.base_delay_ms * (2 ** (n - 1))
        jitter = int(rng.uniform(0, self.jitter_ms)) if self.jitter_ms > 0 else 0
        return min(base + jitter, self.max_delay_ms)

    def is_retryable(self, status: str) -> bool:
        return status in self.retryable_statuses

    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_attempts': self.max_attempts,
            'backoff': self.backoff,
            'base_delay_ms': self.base_delay_ms,
            'max_delay_ms': self.max_delay_ms,
            'jitter_ms': self.jitter_ms,
            'retryable_statuses': list(self.retryable_statuses),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'RetryConfig':
        return cls(
            max_attempts=int(d.get('max_attempts', 3)),
            backoff=str(d.get('backoff', EXPONENTIAL)),
            base_delay_ms=int(d.get('base_delay_ms', 500)),
            max_delay_ms=int(d.get('max_delay_ms', 30_000)),
            jitter_ms=int(d.get('jitter_ms', 100)),
            retryable_statuses=list(d.get('retryable_statuses',
                                          ['failed', 'aborted'])),
        )


# ── RetryDecision ─────────────────────────────────────────────────────────────

@dataclass
class RetryDecision:
    """Result of a should_retry() call."""
    retry: bool
    reason: str           # 'ok_to_retry' | 'not_retryable_status' | 'max_attempts_reached'
    attempt: int          # the attempt number just completed (1-based)
    next_attempt: int     # attempt number to use next (attempt+1)
    delay_ms: int         # suggested wait before next attempt
    max_attempts: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'retry': self.retry,
            'reason': self.reason,
            'attempt': self.attempt,
            'next_attempt': self.next_attempt,
            'delay_ms': self.delay_ms,
            'max_attempts': self.max_attempts,
        }


# ── RetryPolicyStore ──────────────────────────────────────────────────────────

class RetryPolicyStore:
    """JSON-backed store for per-skill retry policies."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._policies: Dict[str, RetryConfig] = {}
        path = self._dir / 'retry_policies.json'
        if path.exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'retry_policies.json').read_text(encoding='utf-8')
            )
            self._policies = {k: RetryConfig.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._policies = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'retry_policies.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._policies.items()},
                       indent=2),
            encoding='utf-8',
        )

    def set(self, skill_id: str, config: RetryConfig) -> None:
        self._policies[skill_id] = config
        self._flush()

    def get(self, skill_id: str) -> Optional[RetryConfig]:
        return self._policies.get(skill_id)

    def remove(self, skill_id: str) -> bool:
        if skill_id not in self._policies:
            return False
        del self._policies[skill_id]
        self._flush()
        return True

    def list_skills(self) -> List[str]:
        return list(self._policies.keys())

    @property
    def policy_count(self) -> int:
        return len(self._policies)


# ── RetryEngine ───────────────────────────────────────────────────────────────

class RetryEngine:
    """Stateless retry advisor.

    Parameters
    ----------
    data_dir:
        Directory for persisting per-skill retry policies.
    default_config:
        Fallback ``RetryConfig`` used when no per-skill policy is registered.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        default_config: Optional[RetryConfig] = None,
    ) -> None:
        self._store = RetryPolicyStore(data_dir or Path('retry'))
        self._default = default_config or RetryConfig()

    def get_config(self, skill_id: str) -> RetryConfig:
        return self._store.get(skill_id) or self._default

    def set_policy(self, skill_id: str, config: RetryConfig) -> None:
        self._store.set(skill_id, config)

    def remove_policy(self, skill_id: str) -> bool:
        return self._store.remove(skill_id)

    def list_policies(self) -> Dict[str, RetryConfig]:
        return {s: self._store.get(s) for s in self._store.list_skills()}  # type: ignore[misc]

    def should_retry(
        self,
        skill_id: str,
        attempt: int,
        last_status: str,
        _rng: Optional[random.Random] = None,
    ) -> RetryDecision:
        """Decide whether to retry after *attempt* with the given outcome status.

        Parameters
        ----------
        skill_id:
            The skill that was executed.
        attempt:
            1-based number of the attempt that just completed.
        last_status:
            Execution status of the completed attempt ('success', 'failed', …).
        """
        cfg = self.get_config(skill_id)
        next_attempt = attempt + 1

        if not cfg.is_retryable(last_status):
            return RetryDecision(
                retry=False,
                reason='not_retryable_status',
                attempt=attempt,
                next_attempt=next_attempt,
                delay_ms=0,
                max_attempts=cfg.max_attempts,
            )

        if next_attempt > cfg.max_attempts:
            return RetryDecision(
                retry=False,
                reason='max_attempts_reached',
                attempt=attempt,
                next_attempt=next_attempt,
                delay_ms=0,
                max_attempts=cfg.max_attempts,
            )

        delay = cfg.delay_for_attempt(next_attempt, _rng=_rng)
        return RetryDecision(
            retry=True,
            reason='ok_to_retry',
            attempt=attempt,
            next_attempt=next_attempt,
            delay_ms=delay,
            max_attempts=cfg.max_attempts,
        )
