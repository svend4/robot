"""Tests for marketplace.health_monitor and the /monitor REST API."""
from __future__ import annotations

import datetime
import uuid
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from marketplace.health_monitor import (
    AlertStore,
    FleetHealthReport,
    HealthAlert,
    HealthMonitor,
    HealthThresholds,
    NodeHealthReport,
    SkillHealthReport,
    _utcnow,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_record(skill_id='etd.pick', node_id='robot-1', status='success',
                 minutes_ago=5):
    """Return a minimal mock execution record."""
    r = MagicMock()
    r.skill_id = skill_id
    r.node_id = node_id
    r.status = status
    ts = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(minutes=minutes_ago)
    ).isoformat(timespec='seconds')
    r.started_at = ts
    r.completed_at = ts
    return r


def _store_with(records):
    """Return a mock TelemetryStore that yields *records* on any query."""
    s = MagicMock()
    s.query.return_value = records
    s.skill_ids.return_value = list({r.skill_id for r in records})
    s.node_ids.return_value = list({r.node_id for r in records})
    return s


def _monitor(records, tmp_path, thresholds=None):
    store = _store_with(records)
    return HealthMonitor(store, alert_dir=tmp_path / 'alerts',
                         thresholds=thresholds)


# ── HealthThresholds ──────────────────────────────────────────────────────────

class TestHealthThresholds:
    def test_defaults(self):
        t = HealthThresholds()
        assert t.warn_success_rate == 0.90
        assert t.critical_success_rate == 0.70
        assert t.warn_failure_streak == 3
        assert t.critical_failure_streak == 5
        assert t.min_executions == 2

    def test_round_trip(self):
        t = HealthThresholds(warn_success_rate=0.80, critical_success_rate=0.60,
                             warn_failure_streak=2, critical_failure_streak=4,
                             min_executions=3)
        t2 = HealthThresholds.from_dict(t.to_dict())
        assert t2.warn_success_rate == 0.80
        assert t2.critical_success_rate == 0.60
        assert t2.warn_failure_streak == 2
        assert t2.critical_failure_streak == 4
        assert t2.min_executions == 3

    def test_from_dict_defaults(self):
        t = HealthThresholds.from_dict({})
        assert t.warn_success_rate == 0.90

    def test_to_dict_keys(self):
        keys = set(HealthThresholds().to_dict())
        assert keys == {'warn_success_rate', 'critical_success_rate',
                        'warn_failure_streak', 'critical_failure_streak',
                        'min_executions'}


# ── SkillHealthReport / NodeHealthReport ─────────────────────────────────────

class TestSkillHealthReport:
    def test_to_dict_keys(self):
        r = SkillHealthReport(
            skill_id='etd.pick', status='healthy', success_rate=1.0,
            execution_count=5, recent_failure_count=0, failure_streak=0,
            last_run_at=None, message='OK', window_hours=1,
        )
        keys = set(r.to_dict())
        assert 'skill_id' in keys
        assert 'status' in keys
        assert 'success_rate' in keys
        assert 'window_hours' in keys

    def test_success_rate_rounded(self):
        r = SkillHealthReport(
            skill_id='x', status='healthy', success_rate=0.333333,
            execution_count=3, recent_failure_count=1, failure_streak=0,
            last_run_at=None, message='', window_hours=1,
        )
        assert r.to_dict()['success_rate'] == round(0.333333, 4)


class TestNodeHealthReport:
    def test_to_dict_has_skills_executed(self):
        r = NodeHealthReport(
            node_id='r1', status='healthy', success_rate=1.0,
            execution_count=2, skills_executed=['etd.pick'],
            last_run_at=None, message='OK',
        )
        d = r.to_dict()
        assert d['skills_executed'] == ['etd.pick']


# ── HealthAlert / AlertStore ──────────────────────────────────────────────────

class TestHealthAlert:
    def test_round_trip(self):
        a = HealthAlert(
            alert_id='abc', level='critical', subject_type='skill',
            subject_id='etd.pick', message='bad', triggered_at=_utcnow(),
        )
        a2 = HealthAlert.from_dict(a.to_dict())
        assert a2.alert_id == 'abc'
        assert a2.level == 'critical'
        assert a2.resolved is False
        assert a2.resolved_at is None

    def test_resolved_fields(self):
        a = HealthAlert(
            alert_id='x', level='warning', subject_type='node',
            subject_id='r1', message='m', triggered_at=_utcnow(),
            resolved=True, resolved_at='2025-01-01T00:00:00+00:00',
        )
        d = a.to_dict()
        assert d['resolved'] is True
        assert d['resolved_at'] == '2025-01-01T00:00:00+00:00'


class TestAlertStore:
    @pytest.fixture()
    def store(self, tmp_path) -> AlertStore:
        return AlertStore(tmp_path / 'alerts')

    def test_empty(self, store):
        assert store.alert_count == 0
        assert store.active() == []

    def test_add_and_get(self, store):
        a = HealthAlert(alert_id='1', level='warning', subject_type='skill',
                        subject_id='etd.pick', message='m',
                        triggered_at=_utcnow())
        store.add(a)
        assert store.get('1') is not None
        assert store.alert_count == 1

    def test_active_excludes_resolved(self, store):
        a = HealthAlert(alert_id='1', level='warning', subject_type='skill',
                        subject_id='etd.pick', message='m',
                        triggered_at=_utcnow())
        store.add(a)
        store.resolve('1')
        assert store.active() == []
        assert len(store.all_alerts()) == 1

    def test_resolve_returns_false_unknown(self, store):
        assert store.resolve('ghost') is False

    def test_resolve_idempotent(self, store):
        a = HealthAlert(alert_id='1', level='warning', subject_type='skill',
                        subject_id='etd.pick', message='m',
                        triggered_at=_utcnow())
        store.add(a)
        assert store.resolve('1') is True
        assert store.resolve('1') is False  # already resolved

    def test_persists(self, tmp_path):
        p = tmp_path / 'alerts'
        s1 = AlertStore(p)
        a = HealthAlert(alert_id='x', level='critical', subject_type='node',
                        subject_id='r1', message='boom', triggered_at=_utcnow())
        s1.add(a)
        s2 = AlertStore(p)
        assert s2.get('x') is not None
        assert s2.get('x').level == 'critical'

    def test_corrupt_file_loads_empty(self, tmp_path):
        f = tmp_path / 'alerts.json'
        f.write_text('corrupt')
        s = AlertStore(tmp_path)
        assert s.alert_count == 0


# ── HealthMonitor._classify ───────────────────────────────────────────────────

class TestClassify:
    def _mon(self, tmp_path):
        return HealthMonitor(MagicMock(), alert_dir=tmp_path / 'al')

    def test_unknown_below_min(self, tmp_path):
        mon = self._mon(tmp_path)
        assert mon._classify(1.0, 0, 1) == 'unknown'

    def test_healthy(self, tmp_path):
        mon = self._mon(tmp_path)
        assert mon._classify(1.0, 0, 10) == 'healthy'

    def test_degraded_by_rate(self, tmp_path):
        mon = self._mon(tmp_path)
        assert mon._classify(0.85, 0, 10) == 'degraded'

    def test_critical_by_rate(self, tmp_path):
        mon = self._mon(tmp_path)
        assert mon._classify(0.60, 0, 10) == 'critical'

    def test_degraded_by_streak(self, tmp_path):
        mon = self._mon(tmp_path)
        assert mon._classify(1.0, 3, 10) == 'degraded'

    def test_critical_by_streak(self, tmp_path):
        mon = self._mon(tmp_path)
        assert mon._classify(1.0, 5, 10) == 'critical'


# ── HealthMonitor._failure_streak ────────────────────────────────────────────

class TestFailureStreak:
    def _mon(self, tmp_path):
        return HealthMonitor(MagicMock(), alert_dir=tmp_path / 'al')

    def test_no_failures(self, tmp_path):
        records = [_make_record(status='success', minutes_ago=i) for i in range(5)]
        mon = self._mon(tmp_path)
        assert mon._failure_streak(records) == 0

    def test_streak_at_tail(self, tmp_path):
        records = [
            _make_record(status='success', minutes_ago=10),
            _make_record(status='success', minutes_ago=5),
            _make_record(status='failed', minutes_ago=3),
            _make_record(status='failed', minutes_ago=2),
            _make_record(status='failed', minutes_ago=1),
        ]
        mon = self._mon(tmp_path)
        assert mon._failure_streak(records) == 3

    def test_streak_broken_by_success(self, tmp_path):
        records = [
            _make_record(status='failed', minutes_ago=5),
            _make_record(status='failed', minutes_ago=3),
            _make_record(status='success', minutes_ago=1),
        ]
        mon = self._mon(tmp_path)
        assert mon._failure_streak(records) == 0

    def test_aborted_counts_in_streak(self, tmp_path):
        records = [
            _make_record(status='success', minutes_ago=5),
            _make_record(status='aborted', minutes_ago=2),
            _make_record(status='failed', minutes_ago=1),
        ]
        mon = self._mon(tmp_path)
        assert mon._failure_streak(records) == 2


# ── HealthMonitor.check_skill ─────────────────────────────────────────────────

class TestCheckSkill:
    def test_unknown_when_no_records(self, tmp_path):
        mon = _monitor([], tmp_path)
        r = mon.check_skill('etd.pick')
        assert r.status == 'unknown'
        assert r.execution_count == 0
        assert r.last_run_at is None

    def test_healthy(self, tmp_path):
        records = [_make_record(status='success') for _ in range(5)]
        mon = _monitor(records, tmp_path)
        r = mon.check_skill('etd.pick')
        assert r.status == 'healthy'
        assert r.success_rate == 1.0

    def test_degraded_below_warn(self, tmp_path):
        records = (
            [_make_record(status='success')] * 8 +
            [_make_record(status='failed')] * 2
        )
        mon = _monitor(records, tmp_path)
        r = mon.check_skill('etd.pick')
        assert r.status == 'degraded'

    def test_critical_below_critical(self, tmp_path):
        records = (
            [_make_record(status='success')] * 2 +
            [_make_record(status='failed')] * 8
        )
        mon = _monitor(records, tmp_path)
        r = mon.check_skill('etd.pick')
        assert r.status == 'critical'

    def test_failure_streak_reported(self, tmp_path):
        records = [
            _make_record(status='success', minutes_ago=30),
            _make_record(status='failed', minutes_ago=3),
            _make_record(status='failed', minutes_ago=2),
            _make_record(status='failed', minutes_ago=1),
        ]
        mon = _monitor(records, tmp_path)
        r = mon.check_skill('etd.pick')
        assert r.failure_streak == 3

    def test_last_run_at_set(self, tmp_path):
        records = [_make_record(status='success')]
        mon = _monitor(records, tmp_path)
        r = mon.check_skill('etd.pick')
        assert r.last_run_at is not None

    def test_skill_id_preserved(self, tmp_path):
        records = [_make_record(skill_id='etd.weld')]
        mon = _monitor(records, tmp_path)
        r = mon.check_skill('etd.weld')
        assert r.skill_id == 'etd.weld'

    def test_window_hours_in_report(self, tmp_path):
        mon = _monitor([], tmp_path)
        r = mon.check_skill('etd.pick', window_hours=4)
        assert r.window_hours == 4


# ── HealthMonitor.check_node ──────────────────────────────────────────────────

class TestCheckNode:
    def test_unknown_when_no_records(self, tmp_path):
        mon = _monitor([], tmp_path)
        r = mon.check_node('robot-1')
        assert r.status == 'unknown'

    def test_healthy(self, tmp_path):
        records = [_make_record(status='success') for _ in range(5)]
        mon = _monitor(records, tmp_path)
        r = mon.check_node('robot-1')
        assert r.status == 'healthy'
        assert r.success_rate == 1.0

    def test_skills_executed_listed(self, tmp_path):
        records = [
            _make_record(skill_id='etd.pick', status='success'),
            _make_record(skill_id='etd.weld', status='success'),
        ]
        mon = _monitor(records, tmp_path)
        r = mon.check_node('robot-1')
        assert set(r.skills_executed) == {'etd.pick', 'etd.weld'}

    def test_node_id_preserved(self, tmp_path):
        records = [_make_record(node_id='arm-7', status='success')]
        mon = _monitor(records, tmp_path)
        r = mon.check_node('arm-7')
        assert r.node_id == 'arm-7'


# ── HealthMonitor._maybe_alert ────────────────────────────────────────────────

class TestMaybeAlert:
    def test_no_alert_for_healthy(self, tmp_path):
        mon = _monitor([], tmp_path)
        a = mon._maybe_alert('healthy', 'skill', 'etd.pick', 'ok')
        assert a is None

    def test_no_alert_for_unknown(self, tmp_path):
        mon = _monitor([], tmp_path)
        a = mon._maybe_alert('unknown', 'skill', 'etd.pick', 'no data')
        assert a is None

    def test_warning_alert_for_degraded(self, tmp_path):
        mon = _monitor([], tmp_path)
        a = mon._maybe_alert('degraded', 'skill', 'etd.pick', 'deg')
        assert a is not None
        assert a.level == 'warning'

    def test_critical_alert_for_critical(self, tmp_path):
        mon = _monitor([], tmp_path)
        a = mon._maybe_alert('critical', 'node', 'r1', 'bad')
        assert a is not None
        assert a.level == 'critical'

    def test_no_duplicate_alert(self, tmp_path):
        mon = _monitor([], tmp_path)
        a1 = mon._maybe_alert('degraded', 'skill', 'etd.pick', 'msg')
        a2 = mon._maybe_alert('degraded', 'skill', 'etd.pick', 'msg')
        assert a1 is not None
        assert a2 is None  # duplicate suppressed

    def test_new_alert_after_resolve(self, tmp_path):
        mon = _monitor([], tmp_path)
        a1 = mon._maybe_alert('degraded', 'skill', 'etd.pick', 'msg')
        mon.resolve_alert(a1.alert_id)
        a2 = mon._maybe_alert('degraded', 'skill', 'etd.pick', 'msg')
        assert a2 is not None  # old alert was resolved, new one allowed


# ── HealthMonitor.check_fleet ─────────────────────────────────────────────────

class TestCheckFleet:
    def _store_multi(self, skill_records, node_records=None):
        """Store that returns skill_records on skill queries, node_records on node."""
        s = MagicMock()
        s.skill_ids.return_value = list({r.skill_id for r in skill_records})
        s.node_ids.return_value = list({r.node_id for r in skill_records})

        def _query(skill_id=None, node_id=None, since=None):
            if skill_id:
                return [r for r in skill_records if r.skill_id == skill_id]
            if node_id:
                return [r for r in skill_records if r.node_id == node_id]
            return skill_records
        s.query.side_effect = _query
        return s

    def test_fleet_overall_healthy(self, tmp_path):
        records = [_make_record(status='success') for _ in range(5)]
        store = self._store_multi(records)
        mon = HealthMonitor(store, alert_dir=tmp_path / 'al')
        rpt = mon.check_fleet()
        assert rpt.overall_status == 'healthy'

    def test_fleet_worst_wins(self, tmp_path):
        success = [_make_record(skill_id='etd.pick', status='success') for _ in range(5)]
        failing = [_make_record(skill_id='etd.weld', status='failed') for _ in range(5)]
        store = self._store_multi(success + failing)
        mon = HealthMonitor(store, alert_dir=tmp_path / 'al')
        rpt = mon.check_fleet()
        assert rpt.overall_status == 'critical'

    def test_fleet_report_has_generated_at(self, tmp_path):
        store = MagicMock()
        store.skill_ids.return_value = []
        store.node_ids.return_value = []
        mon = HealthMonitor(store, alert_dir=tmp_path / 'al')
        rpt = mon.check_fleet()
        assert rpt.generated_at

    def test_fleet_to_dict_keys(self, tmp_path):
        store = MagicMock()
        store.skill_ids.return_value = []
        store.node_ids.return_value = []
        mon = HealthMonitor(store, alert_dir=tmp_path / 'al')
        d = mon.check_fleet().to_dict()
        assert {'generated_at', 'overall_status', 'skill_count',
                'node_count', 'alert_count', 'skills', 'nodes',
                'alerts'} <= set(d)


# ── HealthMonitor alert management ────────────────────────────────────────────

class TestAlertManagement:
    def test_active_alerts_empty(self, tmp_path):
        mon = _monitor([], tmp_path)
        assert mon.active_alerts() == []

    def test_resolve_alert_true(self, tmp_path):
        mon = _monitor([], tmp_path)
        records = [_make_record(status='failed') for _ in range(5)]
        store = _store_with(records)
        mon2 = HealthMonitor(store, alert_dir=tmp_path / 'al2')
        mon2.check_skill('etd.pick')
        alerts = mon2.active_alerts()
        assert len(alerts) >= 1
        assert mon2.resolve_alert(alerts[0].alert_id) is True

    def test_resolve_alert_false_unknown(self, tmp_path):
        mon = _monitor([], tmp_path)
        assert mon.resolve_alert('ghost-id') is False

    def test_all_alerts_includes_resolved(self, tmp_path):
        mon = _monitor([], tmp_path)
        records = [_make_record(status='failed') for _ in range(5)]
        store = _store_with(records)
        mon2 = HealthMonitor(store, alert_dir=tmp_path / 'al3')
        mon2.check_skill('etd.pick')
        a = mon2.active_alerts()[0]
        mon2.resolve_alert(a.alert_id)
        assert len(mon2.all_alerts()) >= 1
        assert mon2.active_alerts() == []


# ── REST API /monitor ─────────────────────────────────────────────────────────

import api.health_monitor as _hm_mod


@pytest.fixture(autouse=True)
def patch_hm_paths(tmp_path, monkeypatch):
    tel_path = tmp_path / 'telemetry' / 'executions.jsonl'
    tel_path.parent.mkdir(parents=True, exist_ok=True)
    alert_dir = tmp_path / 'health'
    monkeypatch.setattr(_hm_mod, '_TELEMETRY_PATH', tel_path)
    monkeypatch.setattr(_hm_mod, '_ALERT_DIR', alert_dir)


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _record_execution(api_client, skill_id='etd.pick', node_id='robot-1',
                      status='success', duration_ms=100):
    """Helper: POST an execution record via telemetry API."""
    import api.telemetry as _tel_mod
    # We need to reach into the telemetry module to use its store path too.
    # The simplest approach: write directly via the TelemetryStore.
    from marketplace.telemetry_analytics import TelemetryStore, ExecutionRecord
    store = TelemetryStore(_hm_mod._TELEMETRY_PATH)
    rec = ExecutionRecord.make(
        skill_id=skill_id, node_id=node_id, station_id='default',
        status=status, total_duration_ms=duration_ms,
    )
    store.record(rec)


class TestMonitorSkillsAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/monitor/skills')
        assert r.status_code == 200
        assert r.json()['skill_count'] == 0

    def test_list_after_records(self, api_client):
        _record_execution(api_client, skill_id='etd.pick')
        _record_execution(api_client, skill_id='etd.pick')
        r = api_client.get('/monitor/skills')
        assert r.status_code == 200
        assert r.json()['skill_count'] >= 1

    def test_single_skill_health(self, api_client):
        for _ in range(3):
            _record_execution(api_client, skill_id='etd.weld', status='success')
        r = api_client.get('/monitor/skills/etd.weld')
        assert r.status_code == 200
        data = r.json()
        assert data['skill_id'] == 'etd.weld'
        assert data['status'] == 'healthy'

    def test_skill_unknown_no_records(self, api_client):
        r = api_client.get('/monitor/skills/ghost.skill')
        assert r.status_code == 200
        assert r.json()['status'] == 'unknown'

    def test_skill_window_hours_param(self, api_client):
        r = api_client.get('/monitor/skills/etd.pick?window_hours=2')
        assert r.status_code == 200
        assert r.json()['window_hours'] == 2


class TestMonitorNodesAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/monitor/nodes')
        assert r.status_code == 200
        assert r.json()['node_count'] == 0

    def test_single_node_health(self, api_client):
        for _ in range(3):
            _record_execution(api_client, node_id='arm-1', status='success')
        r = api_client.get('/monitor/nodes/arm-1')
        assert r.status_code == 200
        data = r.json()
        assert data['node_id'] == 'arm-1'
        assert data['status'] == 'healthy'

    def test_node_unknown_no_records(self, api_client):
        r = api_client.get('/monitor/nodes/ghost-node')
        assert r.status_code == 200
        assert r.json()['status'] == 'unknown'


class TestMonitorFleetAPI:
    def test_fleet_200(self, api_client):
        r = api_client.get('/monitor/fleet')
        assert r.status_code == 200

    def test_fleet_has_overall_status(self, api_client):
        data = api_client.get('/monitor/fleet').json()
        assert 'overall_status' in data

    def test_fleet_healthy(self, api_client):
        for _ in range(3):
            _record_execution(api_client, status='success')
        data = api_client.get('/monitor/fleet').json()
        assert data['overall_status'] == 'healthy'

    def test_fleet_critical_when_failures(self, api_client):
        for _ in range(8):
            _record_execution(api_client, status='failed')
        for _ in range(2):
            _record_execution(api_client, status='success')
        data = api_client.get('/monitor/fleet').json()
        assert data['overall_status'] == 'critical'


class TestMonitorAlertsAPI:
    def test_alerts_empty(self, api_client):
        r = api_client.get('/monitor/alerts')
        assert r.status_code == 200
        assert r.json()['alert_count'] == 0

    def test_alert_triggered_on_failure(self, api_client):
        for _ in range(8):
            _record_execution(api_client, status='failed')
        for _ in range(2):
            _record_execution(api_client, status='success')
        api_client.get('/monitor/skills/etd.pick')  # triggers check
        r = api_client.get('/monitor/alerts')
        assert r.status_code == 200
        assert r.json()['alert_count'] >= 1

    def test_resolve_alert_404_unknown(self, api_client):
        r = api_client.delete('/monitor/alerts/bad-id')
        assert r.status_code == 404

    def test_resolve_alert_success(self, api_client):
        for _ in range(8):
            _record_execution(api_client, status='failed')
        for _ in range(2):
            _record_execution(api_client, status='success')
        api_client.get('/monitor/skills/etd.pick')
        alerts = api_client.get('/monitor/alerts').json()['alerts']
        assert len(alerts) >= 1
        alert_id = alerts[0]['alert_id']
        r = api_client.delete(f'/monitor/alerts/{alert_id}')
        assert r.status_code == 200
        assert r.json()['resolved'] == alert_id

    def test_all_alerts_param(self, api_client):
        r = api_client.get('/monitor/alerts?all_alerts=true')
        assert r.status_code == 200
