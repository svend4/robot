"""ETD Skill Runtime Dashboard — real-time view of skills, stations, and events.

Aggregates data from the skill store index, rollout state, station profiles, and
audit log to produce a structured ``DashboardSnapshot`` that can be rendered as
ASCII or serialised as JSON.

Usage::

    from marketplace.dashboard import Dashboard
    from pathlib import Path

    dash = Dashboard(Path('.'))
    snap = dash.snapshot()
    print(snap.render_ascii())

    # Live watch (refreshes every 5 s, Ctrl-C to stop)
    dash.watch(interval_s=5.0)
"""
from __future__ import annotations

import datetime
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class StationHealth:
    station_id: str
    allowed_families: List[str]
    compatible_skill_count: int
    last_event_ts: Optional[str] = None   # ISO timestamp from audit log
    last_result: Optional[str] = None     # 'allowed' | 'blocked'
    status: str = 'idle'                  # 'active' | 'idle' | 'unknown'


@dataclass
class RolloutEntry:
    skill_id: str
    version: str
    stage: str
    approved_stations: List[str]
    updated_at: str


@dataclass
class RecentEvent:
    timestamp: str
    skill_id: str
    result: str
    reason: str
    station_id: Optional[str] = None
    validation_level: str = 'n/a'


@dataclass
class DashboardSnapshot:
    generated_at: str
    skills_in_store: int
    station_health: List[StationHealth] = field(default_factory=list)
    rollout_entries: List[RolloutEntry] = field(default_factory=list)
    recent_events: List[RecentEvent] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render_ascii(self, width: int = 62) -> str:
        W = width
        lines: List[str] = []

        def _rule(char: str = '═') -> str:
            return '╠' + char * (W - 2) + '╣'

        def _row(text: str = '') -> str:
            text = text[:W - 4]
            return '║  ' + text + ' ' * (W - 4 - len(text)) + '  ║'

        lines.append('╔' + '═' * (W - 2) + '╗')
        title = f'ETD Dashboard  {self.generated_at}'
        lines.append('║  ' + title + ' ' * (W - 4 - len(title)) + '  ║')
        lines.append(_rule())

        # Summary
        lines.append(_row('SUMMARY'))
        s = self.summary
        lines.append(_row(
            f"Skills in store : {s.get('skills_in_store', 0):>3}   "
            f"Stations : {s.get('station_count', 0):>2}"
        ))
        lines.append(_row(
            f"Rollout entries : {s.get('rollout_count', 0):>3}   "
            f"Recent events : {s.get('recent_event_count', 0):>2}"
        ))
        lines.append(_row(
            f"Installs allowed: {s.get('installs_allowed', 0):>3}   "
            f"Installs blocked: {s.get('installs_blocked', 0):>2}"
        ))

        # Station health
        lines.append(_rule())
        lines.append(_row('STATION HEALTH'))
        if self.station_health:
            for sh in self.station_health:
                ts = sh.last_event_ts[:10] if sh.last_event_ts else '—'
                compatible = f"{sh.compatible_skill_count} compatible"
                status = sh.status.upper()
                row = f'{sh.station_id:<24} {compatible:<15} {status}  {ts}'
                lines.append(_row(row))
        else:
            lines.append(_row('  (no station data)'))

        # Rollout state
        lines.append(_rule())
        lines.append(_row('ROLLOUT STATE'))
        if self.rollout_entries:
            for r in self.rollout_entries:
                row = f'{r.skill_id:<32} v{r.version:<8} {r.stage}'
                lines.append(_row(row))
        else:
            lines.append(_row('  (no rollout entries)'))

        # Recent events
        lines.append(_rule())
        n = len(self.recent_events)
        lines.append(_row(f'RECENT AUDIT EVENTS  (last {n})'))
        if self.recent_events:
            for ev in self.recent_events:
                ts = ev.timestamp[:16].replace('T', ' ')
                result_mark = 'OK  ' if ev.result == 'allowed' else 'FAIL'
                skill_short = ev.skill_id[:28]
                row = f'{ts}  {result_mark}  {skill_short}'
                lines.append(_row(row))
        else:
            lines.append(_row('  (no events logged)'))

        lines.append('╚' + '═' * (W - 2) + '╝')
        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'generated_at': self.generated_at,
            'skills_in_store': self.skills_in_store,
            'summary': self.summary,
            'station_health': [
                {
                    'station_id': sh.station_id,
                    'allowed_families': sh.allowed_families,
                    'compatible_skill_count': sh.compatible_skill_count,
                    'last_event_ts': sh.last_event_ts,
                    'last_result': sh.last_result,
                    'status': sh.status,
                }
                for sh in self.station_health
            ],
            'rollout_entries': [
                {
                    'skill_id': r.skill_id,
                    'version': r.version,
                    'stage': r.stage,
                    'approved_stations': r.approved_stations,
                    'updated_at': r.updated_at,
                }
                for r in self.rollout_entries
            ],
            'recent_events': [
                {
                    'timestamp': ev.timestamp,
                    'skill_id': ev.skill_id,
                    'result': ev.result,
                    'reason': ev.reason,
                    'station_id': ev.station_id,
                    'validation_level': ev.validation_level,
                }
                for ev in self.recent_events
            ],
        }


# ── Dashboard engine ──────────────────────────────────────────────────────────

class Dashboard:
    """Aggregate runtime state and produce a ``DashboardSnapshot``.

    Parameters
    ----------
    repo_root:
        Project root directory (contains ``marketplace/``, ``station_profiles/``).
    audit_log_path:
        Path to the JSONL audit log. Defaults to ``<repo_root>/logs/etd_audit.jsonl``.
    station_profiles_dir:
        Directory of station profile JSON files. Defaults to
        ``<repo_root>/station_profiles``.
    rollout_state_path:
        Path to ``rollout_state.json``. Defaults to
        ``<repo_root>/marketplace/rollout_state.json``.
    """

    def __init__(
        self,
        repo_root: Path,
        audit_log_path: Optional[Path] = None,
        station_profiles_dir: Optional[Path] = None,
        rollout_state_path: Optional[Path] = None,
    ) -> None:
        self._root = repo_root if isinstance(repo_root, Path) else Path(repo_root)
        self._audit_path = audit_log_path or (self._root / 'logs' / 'etd_audit.jsonl')
        self._stations_dir = station_profiles_dir or (self._root / 'station_profiles')
        self._rollout_path = rollout_state_path or (self._root / 'marketplace' / 'rollout_state.json')

    # ── Public API ────────────────────────────────────────────────────────────

    def snapshot(self, last_n_events: int = 10) -> DashboardSnapshot:
        """Collect all data sources and return a current ``DashboardSnapshot``."""
        now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        store_entries = self._load_store_entries()
        audit_entries = self._load_audit_entries()
        station_profiles = self._load_station_profiles()
        rollout_entries = self._load_rollout_entries()

        station_health = self._build_station_health(station_profiles, store_entries, audit_entries)
        recent_events = self._build_recent_events(audit_entries, last_n_events)

        allowed = sum(1 for e in audit_entries if e.get('result') == 'allowed')
        blocked = sum(1 for e in audit_entries if e.get('result') == 'blocked')

        summary = {
            'skills_in_store': len(store_entries),
            'station_count': len(station_profiles),
            'rollout_count': len(rollout_entries),
            'recent_event_count': len(recent_events),
            'total_audit_events': len(audit_entries),
            'installs_allowed': allowed,
            'installs_blocked': blocked,
        }

        return DashboardSnapshot(
            generated_at=now,
            skills_in_store=len(store_entries),
            station_health=station_health,
            rollout_entries=rollout_entries,
            recent_events=recent_events,
            summary=summary,
        )

    def watch(
        self,
        interval_s: float = 5.0,
        refresh_count: Optional[int] = None,
        last_n_events: int = 10,
        clear_screen: bool = True,
    ) -> None:
        """Render the dashboard repeatedly until *refresh_count* refreshes or Ctrl-C.

        Parameters
        ----------
        interval_s:
            Seconds between refreshes.
        refresh_count:
            Stop after this many renders. ``None`` means run forever.
        clear_screen:
            Clear the terminal between renders.
        """
        i = 0
        try:
            while refresh_count is None or i < refresh_count:
                snap = self.snapshot(last_n_events=last_n_events)
                if clear_screen:
                    os.system('clear' if os.name != 'nt' else 'cls')
                print(snap.render_ascii())
                i += 1
                if refresh_count is None or i < refresh_count:
                    time.sleep(interval_s)
        except KeyboardInterrupt:
            pass

    # ── Internal data loaders ─────────────────────────────────────────────────

    def _load_store_entries(self) -> List[Dict[str, Any]]:
        index_path = self._root / 'marketplace' / 'skill_store_index.json'
        if not index_path.exists():
            return []
        try:
            data = json.loads(index_path.read_text(encoding='utf-8'))
            return data.get('entries', [])
        except Exception:
            return []

    def _load_audit_entries(self) -> List[Dict[str, Any]]:
        if not self._audit_path.exists():
            return []
        try:
            entries = []
            for line in self._audit_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return entries
        except Exception:
            return []

    def _load_station_profiles(self) -> List[Dict[str, Any]]:
        profiles = []
        if not self._stations_dir.exists():
            return profiles
        for f in sorted(self._stations_dir.glob('*.json')):
            try:
                profiles.append(json.loads(f.read_text(encoding='utf-8')))
            except Exception:
                pass
        return profiles

    def _load_rollout_entries(self) -> List[RolloutEntry]:
        if not self._rollout_path.exists():
            return []
        try:
            data = json.loads(self._rollout_path.read_text(encoding='utf-8'))
            result = []
            for raw in data.get('entries', {}).values():
                result.append(RolloutEntry(
                    skill_id=raw.get('skillId', ''),
                    version=raw.get('version', '0.0.0'),
                    stage=raw.get('stage', 'unknown'),
                    approved_stations=raw.get('approvedStations', []),
                    updated_at=raw.get('updatedAt', ''),
                ))
            return sorted(result, key=lambda r: r.updated_at, reverse=True)
        except Exception:
            return []

    # ── Internal builders ─────────────────────────────────────────────────────

    def _build_station_health(
        self,
        profiles: List[Dict[str, Any]],
        store_entries: List[Dict[str, Any]],
        audit_entries: List[Dict[str, Any]],
    ) -> List[StationHealth]:
        # Build per-station audit index
        station_events: Dict[str, List[Dict[str, Any]]] = {}
        for ev in audit_entries:
            sid = ev.get('station_id')
            if sid:
                station_events.setdefault(sid, []).append(ev)

        results = []
        for prof in profiles:
            station_id = prof.get('station_id', prof.get('stationId', ''))
            allowed_families = prof.get('allowed_skill_families', [])
            available_services = set(prof.get('availableServices', []))

            # Count compatible skills from store
            compatible = 0
            for entry in store_entries:
                family = entry.get('family', '')
                if family in allowed_families:
                    compatible += 1
                elif not allowed_families:
                    compatible += 1  # no restriction → all skills compatible

            # Last audit event for this station
            evs = sorted(station_events.get(station_id, []), key=lambda e: e.get('timestamp', ''))
            last_event = evs[-1] if evs else None

            # Determine status: 'active' if there's been an event in the last 24 h
            status = 'idle'
            last_ts = None
            last_result = None
            if last_event:
                last_ts = last_event.get('timestamp')
                last_result = last_event.get('result')
                try:
                    ts = datetime.datetime.fromisoformat(last_ts.rstrip('Z')).replace(
                        tzinfo=datetime.timezone.utc
                    )
                    age = datetime.datetime.now(datetime.timezone.utc) - ts
                    if age.total_seconds() < 86400:
                        status = 'active'
                except Exception:
                    pass

            results.append(StationHealth(
                station_id=station_id,
                allowed_families=allowed_families,
                compatible_skill_count=compatible,
                last_event_ts=last_ts,
                last_result=last_result,
                status=status,
            ))
        return results

    def _build_recent_events(
        self,
        audit_entries: List[Dict[str, Any]],
        last_n: int,
    ) -> List[RecentEvent]:
        events = sorted(audit_entries, key=lambda e: e.get('timestamp', ''), reverse=True)
        result = []
        for ev in events[:last_n]:
            result.append(RecentEvent(
                timestamp=ev.get('timestamp', ''),
                skill_id=ev.get('skill_id', ''),
                result=ev.get('result', ''),
                reason=ev.get('reason', ''),
                station_id=ev.get('station_id'),
                validation_level=ev.get('validation_level', 'n/a'),
            ))
        return result
