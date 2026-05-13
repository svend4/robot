"""Tests for the ETD runtime dashboard."""
from __future__ import annotations

import json
import sys
import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.dashboard import (
    Dashboard,
    DashboardSnapshot,
    RecentEvent,
    RolloutEntry,
    StationHealth,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(offset_hours: int = 0) -> str:
    """Return an ISO UTC timestamp offset_hours from now."""
    t = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=offset_hours)
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def _make_dash(tmp_path: Path, *, audit_lines=None, station_profiles=None,
               rollout_entries=None, store_entries=None) -> Dashboard:
    """Build a Dashboard pointing to temp directories."""
    (tmp_path / 'logs').mkdir(exist_ok=True)
    (tmp_path / 'station_profiles').mkdir(exist_ok=True)
    (tmp_path / 'marketplace').mkdir(exist_ok=True)

    # Audit log
    audit_path = tmp_path / 'logs' / 'etd_audit.jsonl'
    if audit_lines:
        audit_path.write_text('\n'.join(json.dumps(e) for e in audit_lines) + '\n', encoding='utf-8')

    # Station profiles
    for prof in (station_profiles or []):
        sid = prof.get('station_id', 'unknown')
        (tmp_path / 'station_profiles' / f'{sid}.json').write_text(
            json.dumps(prof), encoding='utf-8'
        )

    # Rollout state
    rollout_path = tmp_path / 'marketplace' / 'rollout_state.json'
    if rollout_entries is not None:
        entries_dict = {}
        for r in rollout_entries:
            key = f"{r['skillId']}@{r['version']}"
            entries_dict[key] = r
        rollout_path.write_text(json.dumps({'entries': entries_dict}), encoding='utf-8')
    else:
        rollout_path.write_text(json.dumps({'entries': {}}), encoding='utf-8')

    # Skill store index
    index_path = tmp_path / 'marketplace' / 'skill_store_index.json'
    index_path.write_text(json.dumps({'entries': store_entries or []}), encoding='utf-8')

    return Dashboard(
        repo_root=tmp_path,
        audit_log_path=tmp_path / 'logs' / 'etd_audit.jsonl',
        station_profiles_dir=tmp_path / 'station_profiles',
        rollout_state_path=rollout_path,
    )


# ── StationHealth dataclass ───────────────────────────────────────────────────

class TestStationHealth:
    def test_fields(self):
        sh = StationHealth(
            station_id='ws1',
            allowed_families=['manipulator'],
            compatible_skill_count=3,
        )
        assert sh.station_id == 'ws1'
        assert sh.compatible_skill_count == 3
        assert sh.status == 'idle'

    def test_active_status(self):
        sh = StationHealth(
            station_id='ws1', allowed_families=[], compatible_skill_count=0, status='active'
        )
        assert sh.status == 'active'


# ── RolloutEntry dataclass ────────────────────────────────────────────────────

class TestRolloutEntry:
    def test_fields(self):
        r = RolloutEntry(
            skill_id='etd.pickplace.basic',
            version='1.0.0',
            stage='canary',
            approved_stations=['ws1'],
            updated_at='2026-01-01T00:00:00Z',
        )
        assert r.stage == 'canary'
        assert r.approved_stations == ['ws1']


# ── RecentEvent dataclass ─────────────────────────────────────────────────────

class TestRecentEvent:
    def test_fields(self):
        ev = RecentEvent(timestamp='2026-01-01T00:00:00Z', skill_id='etd.x',
                         result='allowed', reason='install_allowed')
        assert ev.station_id is None
        assert ev.validation_level == 'n/a'


# ── DashboardSnapshot ─────────────────────────────────────────────────────────

class TestDashboardSnapshot:
    def _snap(self, **kw):
        defaults = dict(generated_at='2026-01-01T00:00:00Z', skills_in_store=5)
        defaults.update(kw)
        return DashboardSnapshot(**defaults)

    def test_render_ascii_contains_header(self):
        snap = self._snap()
        s = snap.render_ascii()
        assert 'ETD Dashboard' in s

    def test_render_ascii_contains_summary(self):
        snap = self._snap(summary={'skills_in_store': 8, 'station_count': 3,
                                    'rollout_count': 1, 'recent_event_count': 5,
                                    'installs_allowed': 10, 'installs_blocked': 2})
        s = snap.render_ascii()
        assert 'SUMMARY' in s
        assert '8' in s

    def test_render_ascii_contains_station_health(self):
        sh = StationHealth(station_id='ws1', allowed_families=['test'], compatible_skill_count=2)
        snap = self._snap(station_health=[sh])
        s = snap.render_ascii()
        assert 'STATION HEALTH' in s
        assert 'ws1' in s

    def test_render_ascii_no_station_data_placeholder(self):
        snap = self._snap()
        s = snap.render_ascii()
        assert 'no station data' in s

    def test_render_ascii_contains_rollout(self):
        r = RolloutEntry('etd.a', '1.0.0', 'production', [], '2026-01-01T00:00:00Z')
        snap = self._snap(rollout_entries=[r])
        s = snap.render_ascii()
        assert 'ROLLOUT STATE' in s
        assert 'etd.a' in s

    def test_render_ascii_no_rollout_placeholder(self):
        snap = self._snap()
        s = snap.render_ascii()
        assert 'no rollout entries' in s

    def test_render_ascii_contains_events(self):
        ev = RecentEvent('2026-01-01T12:00:00Z', 'etd.b', 'blocked', 'skill_revoked')
        snap = self._snap(recent_events=[ev])
        s = snap.render_ascii()
        assert 'RECENT AUDIT EVENTS' in s
        assert 'FAIL' in s

    def test_render_ascii_no_events_placeholder(self):
        snap = self._snap()
        s = snap.render_ascii()
        assert 'no events logged' in s

    def test_render_ascii_allowed_shows_ok(self):
        ev = RecentEvent('2026-01-01T12:00:00Z', 'etd.c', 'allowed', 'install_allowed')
        snap = self._snap(recent_events=[ev])
        s = snap.render_ascii()
        assert 'OK' in s

    def test_to_dict_has_required_keys(self):
        snap = self._snap()
        d = snap.to_dict()
        for k in ('generated_at', 'skills_in_store', 'summary',
                  'station_health', 'rollout_entries', 'recent_events'):
            assert k in d

    def test_to_dict_is_json_serialisable(self):
        sh = StationHealth('ws1', ['test'], 2, _ts(-1), 'allowed', 'active')
        ev = RecentEvent(_ts(), 'etd.x', 'allowed', 'install_allowed', 'ws1', 'A')
        r = RolloutEntry('etd.x', '1.0.0', 'canary', ['ws1'], _ts())
        snap = self._snap(station_health=[sh], recent_events=[ev], rollout_entries=[r])
        json.dumps(snap.to_dict())  # must not raise

    def test_to_dict_station_health_fields(self):
        sh = StationHealth('ws1', ['test'], 2)
        snap = self._snap(station_health=[sh])
        d = snap.to_dict()['station_health'][0]
        for k in ('station_id', 'allowed_families', 'compatible_skill_count',
                  'last_event_ts', 'last_result', 'status'):
            assert k in d

    def test_render_ascii_custom_width(self):
        snap = self._snap()
        s = snap.render_ascii(width=80)
        first_line = s.splitlines()[0]
        assert len(first_line) == 80


# ── Dashboard — data loading ──────────────────────────────────────────────────

class TestDashboardDataLoading:
    def test_snapshot_no_data_sources(self, tmp_path):
        # Missing files → should not raise, just return empty snapshot
        dash = Dashboard(tmp_path)
        snap = dash.snapshot()
        assert isinstance(snap, DashboardSnapshot)
        assert snap.skills_in_store == 0

    def test_snapshot_loads_store_entries(self, tmp_path):
        store = [
            {'skillId': 'etd.a', 'version': '1.0.0', 'family': 'test',
             'packagePath': 'examples/etd.a', 'publisher': 'test',
             'riskLevel': 'low', 'certificationState': 'test', 'targetUse': 't'},
            {'skillId': 'etd.b', 'version': '1.0.0', 'family': 'test',
             'packagePath': 'examples/etd.b', 'publisher': 'test',
             'riskLevel': 'low', 'certificationState': 'test', 'targetUse': 't'},
        ]
        dash = _make_dash(tmp_path, store_entries=store)
        snap = dash.snapshot()
        assert snap.skills_in_store == 2
        assert snap.summary['skills_in_store'] == 2

    def test_snapshot_loads_rollout(self, tmp_path):
        rollout = [{
            'skillId': 'etd.x', 'version': '1.0.0', 'stage': 'canary',
            'approvedStations': ['ws1'], 'updatedAt': '2026-01-01T00:00:00Z'
        }]
        dash = _make_dash(tmp_path, rollout_entries=rollout)
        snap = dash.snapshot()
        assert len(snap.rollout_entries) == 1
        assert snap.rollout_entries[0].stage == 'canary'

    def test_snapshot_loads_station_profiles(self, tmp_path):
        profiles = [
            {'station_id': 's1', 'allowed_skill_families': ['test']},
            {'station_id': 's2', 'allowed_skill_families': []},
        ]
        dash = _make_dash(tmp_path, station_profiles=profiles)
        snap = dash.snapshot()
        assert snap.summary['station_count'] == 2
        station_ids = {sh.station_id for sh in snap.station_health}
        assert 's1' in station_ids

    def test_snapshot_loads_audit_events(self, tmp_path):
        events = [
            {'skill_id': 'etd.x', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(-1), 'station_id': 's1', 'validation_level': 'A'},
            {'skill_id': 'etd.y', 'result': 'blocked', 'reason': 'rev',
             'timestamp': _ts(-2), 'station_id': None, 'validation_level': 'D'},
        ]
        dash = _make_dash(tmp_path, audit_lines=events)
        snap = dash.snapshot(last_n_events=10)
        assert len(snap.recent_events) == 2

    def test_snapshot_respects_last_n_events(self, tmp_path):
        events = [
            {'skill_id': f'etd.s{i}', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(-i), 'station_id': None, 'validation_level': 'A'}
            for i in range(15)
        ]
        dash = _make_dash(tmp_path, audit_lines=events)
        snap = dash.snapshot(last_n_events=5)
        assert len(snap.recent_events) == 5

    def test_snapshot_recent_events_sorted_newest_first(self, tmp_path):
        events = [
            {'skill_id': 'etd.old', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(-5), 'station_id': None, 'validation_level': 'A'},
            {'skill_id': 'etd.new', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(-1), 'station_id': None, 'validation_level': 'A'},
        ]
        dash = _make_dash(tmp_path, audit_lines=events)
        snap = dash.snapshot(last_n_events=10)
        assert snap.recent_events[0].skill_id == 'etd.new'


# ── Dashboard — summary counters ──────────────────────────────────────────────

class TestDashboardSummary:
    def test_installs_allowed_count(self, tmp_path):
        events = [
            {'skill_id': 'etd.a', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(), 'station_id': None, 'validation_level': 'A'},
            {'skill_id': 'etd.b', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(), 'station_id': None, 'validation_level': 'A'},
            {'skill_id': 'etd.c', 'result': 'blocked', 'reason': 'rev',
             'timestamp': _ts(), 'station_id': None, 'validation_level': 'D'},
        ]
        dash = _make_dash(tmp_path, audit_lines=events)
        snap = dash.snapshot()
        assert snap.summary['installs_allowed'] == 2
        assert snap.summary['installs_blocked'] == 1

    def test_rollout_count_in_summary(self, tmp_path):
        rollout = [
            {'skillId': 'etd.x', 'version': '1.0.0', 'stage': 'canary',
             'approvedStations': [], 'updatedAt': _ts()},
            {'skillId': 'etd.y', 'version': '2.0.0', 'stage': 'production',
             'approvedStations': [], 'updatedAt': _ts()},
        ]
        dash = _make_dash(tmp_path, rollout_entries=rollout)
        snap = dash.snapshot()
        assert snap.summary['rollout_count'] == 2


# ── Dashboard — station health ────────────────────────────────────────────────

class TestDashboardStationHealth:
    def test_compatible_skill_count_by_family(self, tmp_path):
        profiles = [{'station_id': 'ws1', 'allowed_skill_families': ['pickplace']}]
        store = [
            {'skillId': 'etd.a', 'family': 'pickplace', 'version': '1.0.0',
             'packagePath': 'e', 'publisher': 'p', 'riskLevel': 'l',
             'certificationState': 'c', 'targetUse': 't'},
            {'skillId': 'etd.b', 'family': 'weld', 'version': '1.0.0',
             'packagePath': 'e', 'publisher': 'p', 'riskLevel': 'l',
             'certificationState': 'c', 'targetUse': 't'},
        ]
        dash = _make_dash(tmp_path, station_profiles=profiles, store_entries=store)
        snap = dash.snapshot()
        ws1 = next(sh for sh in snap.station_health if sh.station_id == 'ws1')
        assert ws1.compatible_skill_count == 1

    def test_station_active_when_recent_event(self, tmp_path):
        profiles = [{'station_id': 'ws1', 'allowed_skill_families': []}]
        events = [
            {'skill_id': 'etd.x', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(-1), 'station_id': 'ws1', 'validation_level': 'A'},
        ]
        dash = _make_dash(tmp_path, station_profiles=profiles, audit_lines=events)
        snap = dash.snapshot()
        ws1 = next(sh for sh in snap.station_health if sh.station_id == 'ws1')
        assert ws1.status == 'active'
        assert ws1.last_result == 'allowed'

    def test_station_idle_when_no_events(self, tmp_path):
        profiles = [{'station_id': 'ws2', 'allowed_skill_families': []}]
        dash = _make_dash(tmp_path, station_profiles=profiles)
        snap = dash.snapshot()
        ws2 = snap.station_health[0]
        assert ws2.status == 'idle'
        assert ws2.last_event_ts is None

    def test_station_idle_when_old_event(self, tmp_path):
        profiles = [{'station_id': 'ws3', 'allowed_skill_families': []}]
        events = [
            {'skill_id': 'etd.x', 'result': 'allowed', 'reason': 'ok',
             'timestamp': _ts(-48), 'station_id': 'ws3', 'validation_level': 'A'},
        ]
        dash = _make_dash(tmp_path, station_profiles=profiles, audit_lines=events)
        snap = dash.snapshot()
        ws3 = snap.station_health[0]
        assert ws3.status == 'idle'


# ── Dashboard.watch() ─────────────────────────────────────────────────────────

class TestDashboardWatch:
    def test_watch_refresh_count(self, tmp_path, capsys):
        dash = _make_dash(tmp_path)
        with patch('os.system'):  # suppress clear
            dash.watch(interval_s=0.0, refresh_count=2,
                       last_n_events=5, clear_screen=False)
        captured = capsys.readouterr()
        # Should have rendered twice — check Dashboard appeared at least twice
        assert captured.out.count('ETD Dashboard') == 2

    def test_watch_once_no_clear(self, tmp_path, capsys):
        dash = _make_dash(tmp_path)
        dash.watch(interval_s=0.0, refresh_count=1, clear_screen=False)
        captured = capsys.readouterr()
        assert 'ETD Dashboard' in captured.out


# ── Dashboard — real repo data ────────────────────────────────────────────────

class TestDashboardRealData:
    def test_real_repo_snapshot(self):
        dash = Dashboard(ROOT)
        snap = dash.snapshot(last_n_events=5)
        assert isinstance(snap, DashboardSnapshot)
        assert snap.skills_in_store >= 8
        assert snap.summary['station_count'] >= 6

    def test_real_repo_rollout_entries(self):
        dash = Dashboard(ROOT)
        snap = dash.snapshot()
        assert len(snap.rollout_entries) >= 1

    def test_real_repo_ascii_render(self):
        dash = Dashboard(ROOT)
        snap = dash.snapshot()
        s = snap.render_ascii()
        assert 'ETD Dashboard' in s
        assert len(s.splitlines()) > 10


# ── CLI dashboard command ─────────────────────────────────────────────────────

class TestDashboardCLI:
    def test_dashboard_ascii_output(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['dashboard'])
        assert result.exit_code == 0
        assert 'ETD Dashboard' in result.output

    def test_dashboard_json_output(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['dashboard', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'generated_at' in data
        assert 'summary' in data

    def test_dashboard_json_has_all_sections(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['dashboard', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for k in ('generated_at', 'skills_in_store', 'summary',
                  'station_health', 'rollout_entries', 'recent_events'):
            assert k in data

    def test_dashboard_events_option(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['dashboard', '--json', '--events', '3'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data['recent_events']) <= 3
