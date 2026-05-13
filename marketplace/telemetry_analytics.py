"""ETD Skill Telemetry Analytics — execution recording, stats, and anomaly detection.

Each skill package declares telemetry event schemas (``telemetry/events.json``).
This module provides the complementary *analytics* layer: a persistent store for
completed execution records and an analyser that computes per-skill statistics
and surfaces anomalous executions.

Architecture
------------
::

    Robot executor  ──▶  TelemetryStore  ──▶  TelemetryAnalyzer
                          (JSON-backed)         (stats / anomalies)
                              │
                         executions.jsonl   (JSON Lines, one record per line)

Key abstractions
----------------
``ExecutionEvent``
    One atomic event emitted during a skill execution (a primitive start/end,
    a safety check, a telemetry probe).

``ExecutionRecord``
    A complete skill run from start to finish.  Contains the ordered list of
    ``ExecutionEvent``s, start/end timestamps, node and station IDs, and the
    final status (``success`` | ``failed`` | ``aborted``).

``SkillStats``
    Aggregated statistics for one ``skill_id``: execution count, success rate,
    duration percentiles (p50 / p95 / p99), and a ranked list of common failure
    reasons.

``TelemetryStore``
    JSON-Lines–backed store.  Supports append-only recording and filtered
    query.  New records are appended to a ``.jsonl`` file so the store is
    suitable for high-frequency writes without full re-serialisation.

``TelemetryAnalyzer``
    Computes ``SkillStats``, per-node health, recent failures, and
    anomaly detection (executions whose duration deviates more than
    *z_threshold* standard deviations from the skill mean).

Usage::

    from marketplace.telemetry_analytics import (
        TelemetryStore, TelemetryAnalyzer, ExecutionRecord,
    )
    from pathlib import Path

    store    = TelemetryStore(Path('telemetry/executions.jsonl'))
    analyzer = TelemetryAnalyzer(store)

    store.record(ExecutionRecord(
        execution_id='exec-001',
        skill_id='etd.pickplace.basic',
        node_id='arm-01',
        station_id='workcell-01',
        started_at='2026-05-13T10:00:00Z',
        completed_at='2026-05-13T10:00:05Z',
        status='success',
        total_duration_ms=5000,
    ))

    stats = analyzer.skill_stats('etd.pickplace.basic')
    print(f'p95 = {stats.p95_ms} ms   success_rate = {stats.success_rate:.0%}')
"""
from __future__ import annotations

import datetime
import json
import math
import statistics
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _new_id() -> str:
    return str(uuid.uuid4())


# ── ExecutionEvent ────────────────────────────────────────────────────────────

@dataclass
class ExecutionEvent:
    """One event emitted during a skill execution."""
    primitive: str
    status: str          # 'started' | 'completed' | 'failed' | 'skipped'
    duration_ms: int = 0
    timestamp: str = field(default_factory=_utcnow)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'primitive': self.primitive,
            'status': self.status,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp,
            'payload': self.payload,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ExecutionEvent':
        return cls(
            primitive=d['primitive'],
            status=d['status'],
            duration_ms=int(d.get('duration_ms', 0)),
            timestamp=d.get('timestamp', _utcnow()),
            payload=dict(d.get('payload', {})),
        )


# ── ExecutionRecord ───────────────────────────────────────────────────────────

@dataclass
class ExecutionRecord:
    """A complete skill execution from start to finish."""
    execution_id: str
    skill_id: str
    node_id: str
    station_id: str
    started_at: str
    completed_at: str
    status: str              # 'success' | 'failed' | 'aborted'
    total_duration_ms: int = 0
    failure_reason: str = ''
    events: List[ExecutionEvent] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status == 'success'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'execution_id': self.execution_id,
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'station_id': self.station_id,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'status': self.status,
            'total_duration_ms': self.total_duration_ms,
            'failure_reason': self.failure_reason,
            'events': [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ExecutionRecord':
        return cls(
            execution_id=d['execution_id'],
            skill_id=d['skill_id'],
            node_id=d['node_id'],
            station_id=d['station_id'],
            started_at=d['started_at'],
            completed_at=d['completed_at'],
            status=d['status'],
            total_duration_ms=int(d.get('total_duration_ms', 0)),
            failure_reason=d.get('failure_reason', ''),
            events=[ExecutionEvent.from_dict(e) for e in d.get('events', [])],
        )

    @classmethod
    def make(
        cls,
        skill_id: str,
        node_id: str,
        station_id: str,
        status: str,
        total_duration_ms: int = 0,
        failure_reason: str = '',
        events: Optional[List[ExecutionEvent]] = None,
    ) -> 'ExecutionRecord':
        """Convenience factory: fills in IDs and timestamps automatically."""
        now = _utcnow()
        return cls(
            execution_id=_new_id(),
            skill_id=skill_id,
            node_id=node_id,
            station_id=station_id,
            started_at=now,
            completed_at=now,
            status=status,
            total_duration_ms=total_duration_ms,
            failure_reason=failure_reason,
            events=events or [],
        )


# ── SkillStats ────────────────────────────────────────────────────────────────

@dataclass
class SkillStats:
    """Aggregated execution statistics for one skill."""
    skill_id: str
    execution_count: int
    success_count: int
    failure_count: int
    aborted_count: int
    success_rate: float          # 0.0 – 1.0
    mean_duration_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_duration_ms: int
    max_duration_ms: int
    common_failures: List[Tuple[str, int]]   # [(reason, count), ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'aborted_count': self.aborted_count,
            'success_rate': round(self.success_rate, 4),
            'mean_duration_ms': round(self.mean_duration_ms, 1),
            'p50_ms': round(self.p50_ms, 1),
            'p95_ms': round(self.p95_ms, 1),
            'p99_ms': round(self.p99_ms, 1),
            'min_duration_ms': self.min_duration_ms,
            'max_duration_ms': self.max_duration_ms,
            'common_failures': [
                {'reason': r, 'count': c} for r, c in self.common_failures
            ],
        }

    def summary(self) -> str:
        lines = [
            f'{self.skill_id}',
            f'  Executions : {self.execution_count}  '
            f'({self.success_count} ok / {self.failure_count} failed / '
            f'{self.aborted_count} aborted)',
            f'  Success    : {self.success_rate:.0%}',
            f'  Duration   : mean={self.mean_duration_ms:.0f} ms  '
            f'p50={self.p50_ms:.0f}  p95={self.p95_ms:.0f}  p99={self.p99_ms:.0f}',
        ]
        if self.common_failures:
            top = ', '.join(f'{r}×{c}' for r, c in self.common_failures[:3])
            lines.append(f'  Top failures: {top}')
        return '\n'.join(lines)


# ── TelemetryStore ────────────────────────────────────────────────────────────

class TelemetryStore:
    """Append-only JSON-Lines store for execution records.

    Each line in the backing file is one JSON-serialised ``ExecutionRecord``.
    Reads load all lines into memory; writes append a single line.

    Parameters
    ----------
    store_path:
        Path to the ``.jsonl`` file.  Created (with parent dirs) on first
        write if absent.
    """

    def __init__(self, store_path: Path) -> None:
        self._path = Path(store_path)
        self._records: List[ExecutionRecord] = []
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        self._records = []
        for line in self._path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                self._records.append(ExecutionRecord.from_dict(json.loads(line)))
            except Exception:
                pass

    def record(self, execution: ExecutionRecord) -> None:
        """Append one execution record to the store."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(execution.to_dict()) + '\n')
        self._records.append(execution)

    def query(
        self,
        skill_id: Optional[str] = None,
        node_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ExecutionRecord]:
        """Return records matching the given filters, newest-first."""
        result = list(self._records)
        if skill_id:
            result = [r for r in result if r.skill_id == skill_id]
        if node_id:
            result = [r for r in result if r.node_id == node_id]
        if status:
            result = [r for r in result if r.status == status]
        if since:
            result = [r for r in result if r.started_at >= since]
        result.sort(key=lambda r: r.started_at, reverse=True)
        if limit is not None:
            result = result[:limit]
        return result

    def skill_ids(self) -> List[str]:
        """Return unique skill IDs present in the store."""
        seen: dict = {}
        for r in self._records:
            seen[r.skill_id] = True
        return list(seen.keys())

    def node_ids(self) -> List[str]:
        seen: dict = {}
        for r in self._records:
            seen[r.node_id] = True
        return list(seen.keys())

    @property
    def execution_count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        """Wipe all records (truncates the backing file)."""
        self._records = []
        if self._path.exists():
            self._path.write_text('', encoding='utf-8')


# ── percentile helper ─────────────────────────────────────────────────────────

def _percentile(data: List[float], pct: float) -> float:
    """Return the *pct*-th percentile (0–100) of *data* (must be sorted)."""
    if not data:
        return 0.0
    k = (len(data) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (k - lo)


# ── TelemetryAnalyzer ─────────────────────────────────────────────────────────

class TelemetryAnalyzer:
    """Compute analytics from a ``TelemetryStore``.

    All methods read directly from the store's in-memory records; no
    additional I/O is performed.
    """

    def __init__(self, store: TelemetryStore) -> None:
        self._store = store

    def skill_stats(self, skill_id: str) -> Optional[SkillStats]:
        """Return aggregated stats for *skill_id*, or None if no records."""
        records = self._store.query(skill_id=skill_id)
        if not records:
            return None

        n_ok = sum(1 for r in records if r.succeeded)
        n_fail = sum(1 for r in records if r.status == 'failed')
        n_abort = sum(1 for r in records if r.status == 'aborted')
        durations = sorted(float(r.total_duration_ms) for r in records)

        failure_counts: Dict[str, int] = {}
        for r in records:
            if r.failure_reason:
                failure_counts[r.failure_reason] = \
                    failure_counts.get(r.failure_reason, 0) + 1
        common = sorted(failure_counts.items(), key=lambda x: -x[1])

        return SkillStats(
            skill_id=skill_id,
            execution_count=len(records),
            success_count=n_ok,
            failure_count=n_fail,
            aborted_count=n_abort,
            success_rate=n_ok / len(records),
            mean_duration_ms=statistics.mean(durations) if durations else 0.0,
            p50_ms=_percentile(durations, 50),
            p95_ms=_percentile(durations, 95),
            p99_ms=_percentile(durations, 99),
            min_duration_ms=int(durations[0]) if durations else 0,
            max_duration_ms=int(durations[-1]) if durations else 0,
            common_failures=common,
        )

    def node_stats(self, node_id: str) -> Dict[str, Any]:
        """Return a health summary for one robot node."""
        records = self._store.query(node_id=node_id)
        if not records:
            return {'node_id': node_id, 'execution_count': 0}
        n_ok = sum(1 for r in records if r.succeeded)
        skills = list({r.skill_id for r in records})
        return {
            'node_id': node_id,
            'execution_count': len(records),
            'success_count': n_ok,
            'failure_count': len(records) - n_ok,
            'success_rate': round(n_ok / len(records), 4),
            'skills_executed': skills,
            'last_execution_at': records[0].completed_at,
        }

    def recent_failures(self, limit: int = 10) -> List[ExecutionRecord]:
        """Return the most recent failed or aborted executions."""
        return self._store.query(limit=limit * 2)[:limit] if limit else []

    def anomalies(
        self,
        skill_id: Optional[str] = None,
        z_threshold: float = 2.0,
    ) -> List[Tuple[ExecutionRecord, float]]:
        """Return executions whose duration deviates >= *z_threshold* σ from mean.

        Returns list of ``(record, z_score)`` tuples sorted by z_score desc.
        Requires at least 2 records with non-zero duration to compute.
        """
        records = self._store.query(skill_id=skill_id)
        durations = [r.total_duration_ms for r in records if r.total_duration_ms > 0]
        if len(durations) < 2:
            return []
        mean = statistics.mean(durations)
        stdev = statistics.stdev(durations)
        if stdev == 0:
            return []
        result: List[Tuple[ExecutionRecord, float]] = []
        for r in records:
            if r.total_duration_ms <= 0:
                continue
            z = abs(r.total_duration_ms - mean) / stdev
            if z >= z_threshold:
                result.append((r, round(z, 3)))
        result.sort(key=lambda x: -x[1])
        return result

    def report(self) -> Dict[str, Any]:
        """Return a full fleet telemetry report across all skill IDs."""
        skill_ids = self._store.skill_ids()
        node_ids = self._store.node_ids()
        skills_summary = []
        for sid in skill_ids:
            stats = self.skill_stats(sid)
            if stats:
                skills_summary.append(stats.to_dict())
        nodes_summary = [self.node_stats(nid) for nid in node_ids]
        return {
            'generated_at': _utcnow(),
            'total_executions': self._store.execution_count,
            'skill_count': len(skill_ids),
            'node_count': len(node_ids),
            'skills': skills_summary,
            'nodes': nodes_summary,
        }
