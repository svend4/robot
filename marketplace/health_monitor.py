"""ETD Skill Health Monitor.

Continuously evaluates skill and node health from telemetry data and surfaces
degradation before it becomes a production incident.

Architecture
------------
::

    TelemetryStore  ──▶  HealthMonitor  ──▶  SkillHealthReport
                              │               NodeHealthReport
                          AlertStore          FleetHealthReport
                          (JSON-backed)

Health status levels
--------------------
``healthy``   — success rate above warn threshold, no failure streaks
``degraded``  — success rate between warn and critical, or short failure streak
``critical``  — success rate below critical threshold, or long failure streak
``unknown``   — no recent executions to evaluate

Alert levels
------------
``info``      — informational, no action required
``warning``   — degraded condition detected, investigation recommended
``critical``  — critical condition, immediate action required

Usage::

    from marketplace.health_monitor import HealthMonitor, HealthThresholds
    from marketplace.telemetry_analytics import TelemetryStore
    from pathlib import Path

    store    = TelemetryStore(Path('telemetry/executions.jsonl'))
    monitor  = HealthMonitor(store, alert_dir=Path('health'))

    report   = monitor.check_skill('etd.pickplace.basic')
    print(report.status, report.message)

    fleet    = monitor.check_fleet()
    for alert in fleet.alerts:
        print(alert.level, alert.message)
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


def _new_id() -> str:
    return str(uuid.uuid4())


# ── HealthThresholds ──────────────────────────────────────────────────────────

@dataclass
class HealthThresholds:
    """Configurable thresholds for health evaluation."""
    warn_success_rate: float = 0.90      # below → degraded
    critical_success_rate: float = 0.70  # below → critical
    warn_failure_streak: int = 3         # consecutive failures → degraded
    critical_failure_streak: int = 5     # consecutive failures → critical
    min_executions: int = 2              # fewer → unknown

    def to_dict(self) -> Dict[str, Any]:
        return {
            'warn_success_rate': self.warn_success_rate,
            'critical_success_rate': self.critical_success_rate,
            'warn_failure_streak': self.warn_failure_streak,
            'critical_failure_streak': self.critical_failure_streak,
            'min_executions': self.min_executions,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'HealthThresholds':
        return cls(
            warn_success_rate=float(d.get('warn_success_rate', 0.90)),
            critical_success_rate=float(d.get('critical_success_rate', 0.70)),
            warn_failure_streak=int(d.get('warn_failure_streak', 3)),
            critical_failure_streak=int(d.get('critical_failure_streak', 5)),
            min_executions=int(d.get('min_executions', 2)),
        )


# ── SkillHealthReport ─────────────────────────────────────────────────────────

@dataclass
class SkillHealthReport:
    """Health evaluation result for one skill."""
    skill_id: str
    status: str                   # 'healthy' | 'degraded' | 'critical' | 'unknown'
    success_rate: float
    execution_count: int
    recent_failure_count: int
    failure_streak: int           # consecutive failures at tail of records
    last_run_at: Optional[str]
    message: str
    window_hours: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'status': self.status,
            'success_rate': round(self.success_rate, 4),
            'execution_count': self.execution_count,
            'recent_failure_count': self.recent_failure_count,
            'failure_streak': self.failure_streak,
            'last_run_at': self.last_run_at,
            'message': self.message,
            'window_hours': self.window_hours,
        }


# ── NodeHealthReport ──────────────────────────────────────────────────────────

@dataclass
class NodeHealthReport:
    """Health evaluation result for one robot node."""
    node_id: str
    status: str
    success_rate: float
    execution_count: int
    skills_executed: List[str]
    last_run_at: Optional[str]
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'status': self.status,
            'success_rate': round(self.success_rate, 4),
            'execution_count': self.execution_count,
            'skills_executed': self.skills_executed,
            'last_run_at': self.last_run_at,
            'message': self.message,
        }


# ── HealthAlert ───────────────────────────────────────────────────────────────

@dataclass
class HealthAlert:
    """One triggered health alert."""
    alert_id: str
    level: str                   # 'info' | 'warning' | 'critical'
    subject_type: str            # 'skill' | 'node'
    subject_id: str
    message: str
    triggered_at: str
    resolved: bool = False
    resolved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'level': self.level,
            'subject_type': self.subject_type,
            'subject_id': self.subject_id,
            'message': self.message,
            'triggered_at': self.triggered_at,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'HealthAlert':
        return cls(
            alert_id=d['alert_id'],
            level=d['level'],
            subject_type=d['subject_type'],
            subject_id=d['subject_id'],
            message=d['message'],
            triggered_at=d['triggered_at'],
            resolved=bool(d.get('resolved', False)),
            resolved_at=d.get('resolved_at'),
        )


# ── AlertStore ────────────────────────────────────────────────────────────────

class AlertStore:
    """JSON-backed store for health alerts."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._alerts: Dict[str, HealthAlert] = {}
        alerts_path = self._dir / 'alerts.json'
        if alerts_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'alerts.json').read_text(encoding='utf-8')
            )
            self._alerts = {k: HealthAlert.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._alerts = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'alerts.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._alerts.items()},
                       indent=2),
            encoding='utf-8',
        )

    def add(self, alert: HealthAlert) -> None:
        self._alerts[alert.alert_id] = alert
        self._flush()

    def get(self, alert_id: str) -> Optional[HealthAlert]:
        return self._alerts.get(alert_id)

    def resolve(self, alert_id: str) -> bool:
        alert = self._alerts.get(alert_id)
        if alert is None or alert.resolved:
            return False
        alert.resolved = True
        alert.resolved_at = _utcnow()
        self._flush()
        return True

    def active(self) -> List[HealthAlert]:
        return [a for a in self._alerts.values() if not a.resolved]

    def all_alerts(self) -> List[HealthAlert]:
        return list(self._alerts.values())

    @property
    def alert_count(self) -> int:
        return len(self._alerts)


# ── FleetHealthReport ─────────────────────────────────────────────────────────

@dataclass
class FleetHealthReport:
    """Fleet-wide health summary."""
    generated_at: str
    overall_status: str
    skill_reports: List[SkillHealthReport]
    node_reports: List[NodeHealthReport]
    alerts: List[HealthAlert]

    def to_dict(self) -> Dict[str, Any]:
        status_priority = {'critical': 3, 'degraded': 2,
                           'unknown': 1, 'healthy': 0}
        return {
            'generated_at': self.generated_at,
            'overall_status': self.overall_status,
            'skill_count': len(self.skill_reports),
            'node_count': len(self.node_reports),
            'alert_count': len(self.alerts),
            'skills': [r.to_dict() for r in self.skill_reports],
            'nodes': [r.to_dict() for r in self.node_reports],
            'alerts': [a.to_dict() for a in self.alerts],
        }


# ── HealthMonitor ─────────────────────────────────────────────────────────────

class HealthMonitor:
    """Evaluate skill and node health from telemetry data.

    Parameters
    ----------
    telemetry_store:
        A ``TelemetryStore`` instance to read execution records from.
    alert_dir:
        Directory for persisting ``HealthAlert`` records.
    thresholds:
        ``HealthThresholds`` instance (defaults used if None).
    """

    def __init__(
        self,
        telemetry_store: Any,
        alert_dir: Optional[Path] = None,
        thresholds: Optional[HealthThresholds] = None,
    ) -> None:
        self._store = telemetry_store
        self._thresholds = thresholds or HealthThresholds()
        self._alert_store = AlertStore(
            alert_dir or Path('health')
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    def _failure_streak(self, records: list) -> int:
        """Count consecutive failed/aborted records from the most recent."""
        streak = 0
        for r in sorted(records, key=lambda r: r.started_at, reverse=True):
            if r.status in ('failed', 'aborted'):
                streak += 1
            else:
                break
        return streak

    def _classify(
        self,
        success_rate: float,
        streak: int,
        exec_count: int,
    ) -> str:
        t = self._thresholds
        if exec_count < t.min_executions:
            return 'unknown'
        if (success_rate < t.critical_success_rate
                or streak >= t.critical_failure_streak):
            return 'critical'
        if (success_rate < t.warn_success_rate
                or streak >= t.warn_failure_streak):
            return 'degraded'
        return 'healthy'

    def _maybe_alert(
        self,
        status: str,
        subject_type: str,
        subject_id: str,
        message: str,
    ) -> Optional[HealthAlert]:
        if status == 'healthy' or status == 'unknown':
            return None
        level = 'critical' if status == 'critical' else 'warning'
        # Avoid duplicate unresolved alerts for same subject
        for a in self._alert_store.active():
            if a.subject_id == subject_id and a.level == level:
                return None
        alert = HealthAlert(
            alert_id=_new_id(),
            level=level,
            subject_type=subject_type,
            subject_id=subject_id,
            message=message,
            triggered_at=_utcnow(),
        )
        self._alert_store.add(alert)
        return alert

    # ── public API ────────────────────────────────────────────────────────────

    def check_skill(
        self,
        skill_id: str,
        window_hours: int = 1,
    ) -> SkillHealthReport:
        """Evaluate health of one skill over the last *window_hours* hours."""
        since = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=window_hours)
        ).isoformat(timespec='seconds')
        records = self._store.query(skill_id=skill_id, since=since)

        if not records:
            return SkillHealthReport(
                skill_id=skill_id,
                status='unknown',
                success_rate=0.0,
                execution_count=0,
                recent_failure_count=0,
                failure_streak=0,
                last_run_at=None,
                message='No recent executions.',
                window_hours=window_hours,
            )

        n_ok = sum(1 for r in records if r.status == 'success')
        n_fail = sum(1 for r in records if r.status != 'success')
        rate = n_ok / len(records)
        streak = self._failure_streak(records)
        status = self._classify(rate, streak, len(records))
        last_run = max(r.completed_at for r in records)

        if status == 'critical':
            msg = (f'CRITICAL: success_rate={rate:.0%} '
                   f'streak={streak} over last {window_hours}h')
        elif status == 'degraded':
            msg = (f'DEGRADED: success_rate={rate:.0%} '
                   f'streak={streak} over last {window_hours}h')
        else:
            msg = f'OK: {len(records)} executions, {rate:.0%} success.'

        self._maybe_alert(status, 'skill', skill_id, msg)
        return SkillHealthReport(
            skill_id=skill_id,
            status=status,
            success_rate=rate,
            execution_count=len(records),
            recent_failure_count=n_fail,
            failure_streak=streak,
            last_run_at=last_run,
            message=msg,
            window_hours=window_hours,
        )

    def check_node(
        self,
        node_id: str,
        window_hours: int = 1,
    ) -> NodeHealthReport:
        """Evaluate health of one robot node over the last *window_hours* hours."""
        since = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=window_hours)
        ).isoformat(timespec='seconds')
        records = self._store.query(node_id=node_id, since=since)

        if not records:
            return NodeHealthReport(
                node_id=node_id,
                status='unknown',
                success_rate=0.0,
                execution_count=0,
                skills_executed=[],
                last_run_at=None,
                message='No recent executions.',
            )

        n_ok = sum(1 for r in records if r.status == 'success')
        rate = n_ok / len(records)
        streak = self._failure_streak(records)
        status = self._classify(rate, streak, len(records))
        skills = list({r.skill_id for r in records})
        last_run = max(r.completed_at for r in records)

        msg = (f'{status.upper()}: success_rate={rate:.0%} '
               f'over last {window_hours}h')
        self._maybe_alert(status, 'node', node_id, msg)

        return NodeHealthReport(
            node_id=node_id,
            status=status,
            success_rate=rate,
            execution_count=len(records),
            skills_executed=skills,
            last_run_at=last_run,
            message=msg,
        )

    def check_fleet(self, window_hours: int = 1) -> FleetHealthReport:
        """Return a fleet-wide health report across all known skills and nodes."""
        skill_ids = self._store.skill_ids()
        node_ids = self._store.node_ids()

        skill_reports = [self.check_skill(s, window_hours) for s in skill_ids]
        node_reports = [self.check_node(n, window_hours) for n in node_ids]

        # Overall = worst individual status
        priority = {'critical': 3, 'degraded': 2, 'unknown': 1, 'healthy': 0}
        all_statuses = [r.status for r in skill_reports + node_reports]  # type: ignore[operator]
        overall = max(all_statuses, key=lambda s: priority.get(s, 0),
                      default='unknown')

        return FleetHealthReport(
            generated_at=_utcnow(),
            overall_status=overall,
            skill_reports=skill_reports,
            node_reports=node_reports,
            alerts=self._alert_store.active(),
        )

    def active_alerts(self) -> List[HealthAlert]:
        return self._alert_store.active()

    def all_alerts(self) -> List[HealthAlert]:
        return self._alert_store.all_alerts()

    def resolve_alert(self, alert_id: str) -> bool:
        return self._alert_store.resolve(alert_id)
