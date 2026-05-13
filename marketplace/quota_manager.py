"""ETD Execution Quota & Rate Limiting.

Enforces per-skill (and optionally per-node) hourly / daily execution limits
using rolling time windows.  Wildcard policies (``skill_id='*'``) act as
catch-all defaults; more specific policies take precedence.

Architecture
------------
::

    QuotaPolicy          — limit rule (skill × node, max_per_hour, max_per_day)
    QuotaManager
      ├── _policies.json — persisted QuotaPolicy records
      └── _usage.json    — persisted execution timestamp lists (rolling)

Policy matching priority (highest → lowest)
--------------------------------------------
1. exact skill_id  + exact node_id
2. exact skill_id  + wildcard node  (``'*'``)
3. wildcard skill  + exact node_id
4. wildcard skill  + wildcard node  (``'*'``)

Usage::

    from marketplace.quota_manager import QuotaManager, QuotaPolicy
    from pathlib import Path

    qm = QuotaManager(Path('quota'))
    qm.set_policy(QuotaPolicy(
        skill_id='etd.pickplace.basic',
        max_per_hour=60,
        max_per_day=500,
    ))

    result = qm.check('etd.pickplace.basic', node_id='arm-01')
    if result.allowed:
        qm.record('etd.pickplace.basic', node_id='arm-01')
    else:
        print(f'Blocked: {result.reason}')
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow_str() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _parse_dt(s: str) -> datetime.datetime:
    # Accept both +00:00 and Z suffixes
    s = s.replace('Z', '+00:00')
    return datetime.datetime.fromisoformat(s)


def _window_start(now: datetime.datetime, hours: int) -> datetime.datetime:
    return now - datetime.timedelta(hours=hours)


# ── QuotaPolicy ───────────────────────────────────────────────────────────────

@dataclass
class QuotaPolicy:
    """A rate-limit rule for one skill (and optionally one node)."""
    skill_id: str                       # exact ID or ``'*'`` wildcard
    node_id: str = '*'                  # exact node or ``'*'`` wildcard
    max_per_hour: Optional[int] = None  # None = unlimited
    max_per_day: Optional[int] = None   # None = unlimited
    burst_allowance: int = 0            # extra executions above rate
    enabled: bool = True

    # ── specificity score (higher = more specific = higher priority) ──────────
    @property
    def specificity(self) -> int:
        score = 0
        if self.skill_id != '*':
            score += 2
        if self.node_id != '*':
            score += 1
        return score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'max_per_hour': self.max_per_hour,
            'max_per_day': self.max_per_day,
            'burst_allowance': self.burst_allowance,
            'enabled': self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'QuotaPolicy':
        return cls(
            skill_id=d['skill_id'],
            node_id=d.get('node_id', '*'),
            max_per_hour=d.get('max_per_hour'),
            max_per_day=d.get('max_per_day'),
            burst_allowance=int(d.get('burst_allowance', 0)),
            enabled=bool(d.get('enabled', True)),
        )


# ── QuotaCheckResult ──────────────────────────────────────────────────────────

@dataclass
class QuotaCheckResult:
    """Result of a quota check."""
    allowed: bool
    reason: str                        # 'ok'|'hourly_limit'|'daily_limit'|'disabled'|'no_policy'
    policy_matched: Optional[str]      # skill_id of matched policy (or None)
    used_last_hour: int
    used_last_day: int
    remaining_hour: Optional[int]      # None if no hourly limit
    remaining_day: Optional[int]       # None if no daily limit

    def to_dict(self) -> Dict[str, Any]:
        return {
            'allowed': self.allowed,
            'reason': self.reason,
            'policy_matched': self.policy_matched,
            'used_last_hour': self.used_last_hour,
            'used_last_day': self.used_last_day,
            'remaining_hour': self.remaining_hour,
            'remaining_day': self.remaining_day,
        }


# ── QuotaManager ──────────────────────────────────────────────────────────────

class QuotaManager:
    """Enforce and record per-skill execution quotas.

    Parameters
    ----------
    data_dir:
        Directory for ``policies.json`` and ``usage.json``.  Created on first
        write if absent.
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._policies: Dict[str, QuotaPolicy] = {}   # key = f'{skill_id}::{node_id}'
        self._usage: Dict[str, List[str]] = {}         # key = f'{skill_id}::{node_id}'
        if (self._dir / 'policies.json').exists():
            self._load_policies()
        if (self._dir / 'usage.json').exists():
            self._load_usage()

    # ── persistence ───────────────────────────────────────────────────────────

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _load_policies(self) -> None:
        try:
            raw = json.loads((self._dir / 'policies.json').read_text(encoding='utf-8'))
            self._policies = {
                k: QuotaPolicy.from_dict(v) for k, v in raw.items()
            }
        except Exception:
            self._policies = {}

    def _save_policies(self) -> None:
        self._ensure_dir()
        (self._dir / 'policies.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._policies.items()}, indent=2),
            encoding='utf-8',
        )

    def _load_usage(self) -> None:
        try:
            self._usage = json.loads(
                (self._dir / 'usage.json').read_text(encoding='utf-8')
            )
        except Exception:
            self._usage = {}

    def _save_usage(self) -> None:
        self._ensure_dir()
        (self._dir / 'usage.json').write_text(
            json.dumps(self._usage, indent=2),
            encoding='utf-8',
        )

    # ── policy management ─────────────────────────────────────────────────────

    @staticmethod
    def _policy_key(skill_id: str, node_id: str) -> str:
        return f'{skill_id}::{node_id}'

    def set_policy(self, policy: QuotaPolicy) -> None:
        """Add or replace a quota policy."""
        key = self._policy_key(policy.skill_id, policy.node_id)
        self._policies[key] = policy
        self._save_policies()

    def get_policy(self, skill_id: str, node_id: str = '*') -> Optional[QuotaPolicy]:
        """Return the policy stored for an exact (skill_id, node_id) pair."""
        return self._policies.get(self._policy_key(skill_id, node_id))

    def list_policies(self) -> List[QuotaPolicy]:
        return list(self._policies.values())

    def remove_policy(self, skill_id: str, node_id: str = '*') -> bool:
        key = self._policy_key(skill_id, node_id)
        if key not in self._policies:
            return False
        del self._policies[key]
        self._save_policies()
        return True

    # ── policy matching ───────────────────────────────────────────────────────

    def _match_policy(self, skill_id: str, node_id: str) -> Optional[QuotaPolicy]:
        """Return the highest-specificity policy matching (skill_id, node_id)."""
        candidates: List[QuotaPolicy] = []
        for p in self._policies.values():
            skill_match = (p.skill_id == skill_id or p.skill_id == '*')
            node_match = (p.node_id == node_id or p.node_id == '*')
            if skill_match and node_match:
                candidates.append(p)
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.specificity)

    # ── usage helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _usage_key(skill_id: str, node_id: str) -> str:
        return f'{skill_id}::{node_id}'

    def _timestamps(self, skill_id: str, node_id: str) -> List[datetime.datetime]:
        key = self._usage_key(skill_id, node_id)
        raw = self._usage.get(key, [])
        result = []
        for s in raw:
            try:
                result.append(_parse_dt(s))
            except Exception:
                pass
        return result

    def _count_in_window(
        self,
        timestamps: List[datetime.datetime],
        now: datetime.datetime,
        hours: int,
    ) -> int:
        cutoff = _window_start(now, hours)
        return sum(1 for t in timestamps if t >= cutoff)

    def _prune_old_timestamps(
        self,
        skill_id: str,
        node_id: str,
        now: datetime.datetime,
    ) -> None:
        """Remove timestamps older than 7 days (longest window we care about)."""
        key = self._usage_key(skill_id, node_id)
        cutoff = now - datetime.timedelta(days=7)
        raw = self._usage.get(key, [])
        pruned = []
        for s in raw:
            try:
                if _parse_dt(s) >= cutoff:
                    pruned.append(s)
            except Exception:
                pass
        if pruned:
            self._usage[key] = pruned
        elif key in self._usage:
            del self._usage[key]

    # ── public API ────────────────────────────────────────────────────────────

    def check(
        self,
        skill_id: str,
        node_id: str = '*',
        _now: Optional[datetime.datetime] = None,
    ) -> QuotaCheckResult:
        """Check whether an execution is allowed under the applicable policy.

        Parameters
        ----------
        skill_id:
            Skill to check.
        node_id:
            Node that will execute the skill (``'*'`` = unspecified).
        _now:
            Override current time (used in tests).
        """
        now = _now or datetime.datetime.now(datetime.timezone.utc)
        policy = self._match_policy(skill_id, node_id)

        if policy is None:
            return QuotaCheckResult(
                allowed=True,
                reason='no_policy',
                policy_matched=None,
                used_last_hour=0,
                used_last_day=0,
                remaining_hour=None,
                remaining_day=None,
            )

        if not policy.enabled:
            return QuotaCheckResult(
                allowed=False,
                reason='disabled',
                policy_matched=policy.skill_id,
                used_last_hour=0,
                used_last_day=0,
                remaining_hour=0,
                remaining_day=0,
            )

        # Aggregate usage across all matching node keys for this skill
        # (for wildcard policies we aggregate over the specific node)
        ts = self._timestamps(skill_id, node_id)
        used_hour = self._count_in_window(ts, now, 1)
        used_day = self._count_in_window(ts, now, 24)

        effective_hour = (
            (policy.max_per_hour + policy.burst_allowance)
            if policy.max_per_hour is not None else None
        )
        effective_day = (
            (policy.max_per_day + policy.burst_allowance)
            if policy.max_per_day is not None else None
        )

        rem_hour = (effective_hour - used_hour) if effective_hour is not None else None
        rem_day = (effective_day - used_day) if effective_day is not None else None

        if effective_hour is not None and used_hour >= effective_hour:
            return QuotaCheckResult(
                allowed=False,
                reason='hourly_limit',
                policy_matched=policy.skill_id,
                used_last_hour=used_hour,
                used_last_day=used_day,
                remaining_hour=max(rem_hour, 0),
                remaining_day=rem_day,
            )

        if effective_day is not None and used_day >= effective_day:
            return QuotaCheckResult(
                allowed=False,
                reason='daily_limit',
                policy_matched=policy.skill_id,
                used_last_hour=used_hour,
                used_last_day=used_day,
                remaining_hour=rem_hour,
                remaining_day=max(rem_day, 0),
            )

        return QuotaCheckResult(
            allowed=True,
            reason='ok',
            policy_matched=policy.skill_id,
            used_last_hour=used_hour,
            used_last_day=used_day,
            remaining_hour=rem_hour,
            remaining_day=rem_day,
        )

    def record(
        self,
        skill_id: str,
        node_id: str = '*',
        timestamp: Optional[str] = None,
    ) -> None:
        """Record one execution for quota tracking.

        Parameters
        ----------
        timestamp:
            ISO 8601 string; defaults to now.  Pass a fixed value in tests.
        """
        ts = timestamp or _utcnow_str()
        key = self._usage_key(skill_id, node_id)
        if key not in self._usage:
            self._usage[key] = []
        self._usage[key].append(ts)

        # Prune old data periodically
        now = datetime.datetime.now(datetime.timezone.utc)
        self._prune_old_timestamps(skill_id, node_id, now)
        self._save_usage()

    def usage(
        self,
        skill_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return current rolling-window usage for matching keys.

        Filters by skill_id and/or node_id prefix when provided.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        rows = []
        for key, raw_ts in self._usage.items():
            parts = key.split('::', 1)
            s_id, n_id = parts[0], parts[1] if len(parts) > 1 else '*'
            if skill_id and s_id != skill_id:
                continue
            if node_id and n_id != node_id:
                continue
            ts_list = []
            for s in raw_ts:
                try:
                    ts_list.append(_parse_dt(s))
                except Exception:
                    pass
            used_hr = self._count_in_window(ts_list, now, 1)
            used_day = self._count_in_window(ts_list, now, 24)
            rows.append({
                'skill_id': s_id,
                'node_id': n_id,
                'used_last_hour': used_hr,
                'used_last_day': used_day,
                'total_recorded': len(raw_ts),
            })
        rows.sort(key=lambda r: (r['skill_id'], r['node_id']))
        return rows

    def clear_usage(
        self,
        skill_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> int:
        """Clear usage counters. Returns number of keys cleared."""
        if skill_id is None and node_id is None:
            count = len(self._usage)
            self._usage = {}
            self._save_usage()
            return count
        keys_to_del = []
        for key in list(self._usage):
            parts = key.split('::', 1)
            s_id, n_id = parts[0], parts[1] if len(parts) > 1 else '*'
            if skill_id and s_id != skill_id:
                continue
            if node_id and n_id != node_id:
                continue
            keys_to_del.append(key)
        for k in keys_to_del:
            del self._usage[k]
        if keys_to_del:
            self._save_usage()
        return len(keys_to_del)
