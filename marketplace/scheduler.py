"""ETD Skill Execution Scheduler.

Schedule skill executions on robot nodes on a fixed interval or as a
one-shot job at a specific time.  The scheduler tracks job state, detects
due jobs, records run history, and persists everything to a JSON file.

Architecture
------------
::

    SkillScheduler
      └── jobs.json        (persisted ScheduledJob records)

Job lifecycle
-------------
``active``  → run → still active (interval) | ``done`` (once)
``active``  → pause → ``paused``
``paused``  → resume → ``active``
``active``  → remove → deleted

Key abstractions
----------------
``ScheduledJob``
    One scheduled task: skill, node, schedule type (``'interval'`` or
    ``'once'``), timing parameters, status, run counter.

``JobRunResult``
    Record of one job execution attempt.

``SkillScheduler``
    Manages the job collection.  ``due_jobs()`` returns jobs whose
    ``next_run_at`` is ≤ now; ``record_run()`` updates counters and
    advances ``next_run_at`` for interval jobs.

Usage::

    from marketplace.scheduler import SkillScheduler
    from pathlib import Path

    sched = SkillScheduler(Path('scheduler'))

    job = sched.add_job(
        skill_id='etd.pickplace.basic',
        node_id='arm-01',
        station_id='workcell-01',
        schedule_type='interval',
        interval_minutes=30,
    )

    due = sched.due_jobs()
    for j in due:
        sched.record_run(j.job_id, success=True, duration_ms=1200)
"""
from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _utcnow_str() -> str:
    return _utcnow().isoformat(timespec='seconds')


def _new_id() -> str:
    return str(uuid.uuid4())


def _parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))


# ── ScheduledJob ──────────────────────────────────────────────────────────────

_VALID_SCHEDULE_TYPES = frozenset({'interval', 'once'})
_VALID_STATUSES = frozenset({'active', 'paused', 'done'})


@dataclass
class ScheduledJob:
    """One scheduled skill execution job."""
    job_id: str
    skill_id: str
    node_id: str
    station_id: str
    schedule_type: str          # 'interval' | 'once'
    interval_minutes: int       # only used when schedule_type == 'interval'
    run_at: Optional[str]       # ISO datetime; only used when schedule_type == 'once'
    status: str                 # 'active' | 'paused' | 'done'
    created_at: str
    next_run_at: Optional[str]  # ISO datetime of next scheduled run
    last_run_at: Optional[str]  # ISO datetime of most recent run
    run_count: int
    last_run_success: Optional[bool]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'skill_id': self.skill_id,
            'node_id': self.node_id,
            'station_id': self.station_id,
            'schedule_type': self.schedule_type,
            'interval_minutes': self.interval_minutes,
            'run_at': self.run_at,
            'status': self.status,
            'created_at': self.created_at,
            'next_run_at': self.next_run_at,
            'last_run_at': self.last_run_at,
            'run_count': self.run_count,
            'last_run_success': self.last_run_success,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ScheduledJob':
        return cls(
            job_id=d['job_id'],
            skill_id=d['skill_id'],
            node_id=d['node_id'],
            station_id=d.get('station_id', 'default'),
            schedule_type=d.get('schedule_type', 'interval'),
            interval_minutes=int(d.get('interval_minutes', 60)),
            run_at=d.get('run_at'),
            status=d.get('status', 'active'),
            created_at=d.get('created_at', _utcnow_str()),
            next_run_at=d.get('next_run_at'),
            last_run_at=d.get('last_run_at'),
            run_count=int(d.get('run_count', 0)),
            last_run_success=d.get('last_run_success'),
            metadata=dict(d.get('metadata', {})),
        )


# ── JobRunResult ──────────────────────────────────────────────────────────────

@dataclass
class JobRunResult:
    """Record of one execution attempt for a scheduled job."""
    job_id: str
    ran_at: str
    success: bool
    duration_ms: int
    error: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'ran_at': self.ran_at,
            'success': self.success,
            'duration_ms': self.duration_ms,
            'error': self.error,
        }


# ── SkillScheduler ────────────────────────────────────────────────────────────

class SkillScheduler:
    """Manage scheduled skill execution jobs.

    Parameters
    ----------
    data_dir:
        Directory for ``jobs.json``.  Created on first write if absent.
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._jobs: Dict[str, ScheduledJob] = {}
        jobs_path = self._dir / 'jobs.json'
        if jobs_path.exists():
            self._load()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            raw = json.loads((self._dir / 'jobs.json').read_text(encoding='utf-8'))
            self._jobs = {k: ScheduledJob.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._jobs = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'jobs.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._jobs.items()}, indent=2),
            encoding='utf-8',
        )

    # ── first-run time ────────────────────────────────────────────────────────

    @staticmethod
    def _first_next_run(
        schedule_type: str,
        interval_minutes: int,
        run_at: Optional[str],
        now: datetime.datetime,
    ) -> Optional[str]:
        if schedule_type == 'once':
            return run_at  # caller-supplied absolute time
        # interval: first run is `interval_minutes` from now
        return (now + datetime.timedelta(minutes=interval_minutes)).isoformat(
            timespec='seconds'
        )

    # ── public API ────────────────────────────────────────────────────────────

    def add_job(
        self,
        skill_id: str,
        node_id: str,
        station_id: str = 'default',
        schedule_type: str = 'interval',
        interval_minutes: int = 60,
        run_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        _now: Optional[datetime.datetime] = None,
    ) -> ScheduledJob:
        """Create and persist a new scheduled job.

        For ``'once'`` jobs, ``run_at`` must be provided (ISO 8601 string).
        For ``'interval'`` jobs, ``interval_minutes`` must be ≥ 1.
        """
        if schedule_type not in _VALID_SCHEDULE_TYPES:
            raise ValueError(f'Invalid schedule_type: {schedule_type!r}')
        if schedule_type == 'once' and not run_at:
            raise ValueError("run_at is required for schedule_type='once'")
        if schedule_type == 'interval' and interval_minutes < 1:
            raise ValueError('interval_minutes must be >= 1')

        now = _now or _utcnow()
        next_run = self._first_next_run(schedule_type, interval_minutes, run_at, now)
        job = ScheduledJob(
            job_id=_new_id(),
            skill_id=skill_id,
            node_id=node_id,
            station_id=station_id,
            schedule_type=schedule_type,
            interval_minutes=interval_minutes,
            run_at=run_at,
            status='active',
            created_at=now.isoformat(timespec='seconds'),
            next_run_at=next_run,
            last_run_at=None,
            run_count=0,
            last_run_success=None,
            metadata=metadata or {},
        )
        self._jobs[job.job_id] = job
        self._flush()
        return job

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[str] = None,
        skill_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[ScheduledJob]:
        result = list(self._jobs.values())
        if status:
            result = [j for j in result if j.status == status]
        if skill_id:
            result = [j for j in result if j.skill_id == skill_id]
        if node_id:
            result = [j for j in result if j.node_id == node_id]
        result.sort(key=lambda j: j.created_at, reverse=True)
        return result

    def remove_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._flush()
        return True

    def pause_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status != 'active':
            return False
        job.status = 'paused'
        self._flush()
        return True

    def resume_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status != 'paused':
            return False
        job.status = 'active'
        self._flush()
        return True

    def due_jobs(
        self,
        _now: Optional[datetime.datetime] = None,
    ) -> List[ScheduledJob]:
        """Return active jobs whose next_run_at is ≤ now."""
        now = _now or _utcnow()
        due = []
        for job in self._jobs.values():
            if job.status != 'active':
                continue
            if job.next_run_at is None:
                continue
            try:
                if _parse_dt(job.next_run_at) <= now:
                    due.append(job)
            except Exception:
                pass
        due.sort(key=lambda j: j.next_run_at or '')
        return due

    def record_run(
        self,
        job_id: str,
        success: bool,
        duration_ms: int = 0,
        error: str = '',
        _now: Optional[datetime.datetime] = None,
    ) -> Optional[JobRunResult]:
        """Record a completed run and advance the job's next_run_at.

        For ``'once'`` jobs the status becomes ``'done'`` after the first run.
        Returns the ``JobRunResult`` or ``None`` if the job is not found.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        now = _now or _utcnow()
        ran_at = now.isoformat(timespec='seconds')

        job.last_run_at = ran_at
        job.last_run_success = success
        job.run_count += 1

        if job.schedule_type == 'once':
            job.status = 'done'
            job.next_run_at = None
        else:
            job.next_run_at = (
                now + datetime.timedelta(minutes=job.interval_minutes)
            ).isoformat(timespec='seconds')

        self._flush()
        return JobRunResult(
            job_id=job_id,
            ran_at=ran_at,
            success=success,
            duration_ms=duration_ms,
            error=error,
        )

    @property
    def job_count(self) -> int:
        return len(self._jobs)
