"""Tests for marketplace.telemetry_analytics and the /telemetry REST API."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

from marketplace.telemetry_analytics import (
    ExecutionEvent,
    ExecutionRecord,
    SkillStats,
    TelemetryAnalyzer,
    TelemetryStore,
    _percentile,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_store(tmp_path):
    return TelemetryStore(tmp_path / 'execs.jsonl')


def _rec(skill_id='etd.pick', node_id='r01', status='success',
         duration_ms=1000, failure_reason='', station_id='ws-01') -> ExecutionRecord:
    return ExecutionRecord.make(
        skill_id=skill_id,
        node_id=node_id,
        station_id=station_id,
        status=status,
        total_duration_ms=duration_ms,
        failure_reason=failure_reason,
    )


# ── ExecutionEvent ────────────────────────────────────────────────────────────

class TestExecutionEvent:
    def test_to_dict_keys(self):
        e = ExecutionEvent(primitive='pick', status='completed', duration_ms=50)
        d = e.to_dict()
        assert set(d) >= {'primitive', 'status', 'duration_ms', 'timestamp', 'payload'}

    def test_round_trip(self):
        e = ExecutionEvent(primitive='place', status='failed', duration_ms=20,
                           payload={'error': 'timeout'})
        assert ExecutionEvent.from_dict(e.to_dict()).primitive == 'place'
        assert ExecutionEvent.from_dict(e.to_dict()).payload == {'error': 'timeout'}

    def test_defaults(self):
        e = ExecutionEvent(primitive='grasp', status='started')
        assert e.duration_ms == 0
        assert e.payload == {}

    def test_from_dict_missing_optional(self):
        e = ExecutionEvent.from_dict({'primitive': 'x', 'status': 'completed'})
        assert e.duration_ms == 0


# ── ExecutionRecord ───────────────────────────────────────────────────────────

class TestExecutionRecord:
    def test_make_fills_ids(self):
        r = _rec()
        assert r.execution_id  # non-empty UUID
        assert r.started_at
        assert r.completed_at

    def test_succeeded_property(self):
        assert _rec(status='success').succeeded is True
        assert _rec(status='failed').succeeded is False
        assert _rec(status='aborted').succeeded is False

    def test_to_dict_has_events(self):
        r = _rec()
        r.events.append(ExecutionEvent('pick', 'completed', 100))
        d = r.to_dict()
        assert len(d['events']) == 1

    def test_round_trip(self):
        r = _rec(skill_id='etd.inspect', duration_ms=300)
        r2 = ExecutionRecord.from_dict(r.to_dict())
        assert r2.skill_id == 'etd.inspect'
        assert r2.total_duration_ms == 300

    def test_from_dict_defaults(self):
        r = ExecutionRecord.from_dict({
            'execution_id': 'x', 'skill_id': 'a', 'node_id': 'n',
            'station_id': 's', 'started_at': 't', 'completed_at': 't',
            'status': 'success',
        })
        assert r.total_duration_ms == 0
        assert r.failure_reason == ''
        assert r.events == []

    def test_make_with_events(self):
        evts = [ExecutionEvent('pick', 'completed', 50)]
        r = ExecutionRecord.make('s', 'n', 'ws', 'success', events=evts)
        assert len(r.events) == 1


# ── _percentile ───────────────────────────────────────────────────────────────

class TestPercentile:
    def test_empty(self):
        assert _percentile([], 50) == 0.0

    def test_single(self):
        assert _percentile([7.0], 50) == 7.0

    def test_median(self):
        data = sorted([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _percentile(data, 50) == 3.0

    def test_p100(self):
        data = sorted([1.0, 2.0, 3.0])
        assert _percentile(data, 100) == 3.0

    def test_p0(self):
        data = sorted([10.0, 20.0, 30.0])
        assert _percentile(data, 0) == 10.0


# ── TelemetryStore ────────────────────────────────────────────────────────────

class TestTelemetryStore:
    def test_empty_count(self, tmp_store):
        assert tmp_store.execution_count == 0

    def test_record_and_count(self, tmp_store):
        tmp_store.record(_rec())
        assert tmp_store.execution_count == 1

    def test_record_persisted(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        r = _rec(skill_id='etd.pick')
        store.record(r)
        store2 = TelemetryStore(tmp_path / 'e.jsonl')
        assert store2.execution_count == 1
        assert store2._records[0].skill_id == 'etd.pick'

    def test_query_no_filter(self, tmp_store):
        for _ in range(5):
            tmp_store.record(_rec())
        assert len(tmp_store.query()) == 5

    def test_query_by_skill_id(self, tmp_store):
        tmp_store.record(_rec(skill_id='etd.pick'))
        tmp_store.record(_rec(skill_id='etd.inspect'))
        result = tmp_store.query(skill_id='etd.pick')
        assert all(r.skill_id == 'etd.pick' for r in result)
        assert len(result) == 1

    def test_query_by_node_id(self, tmp_store):
        tmp_store.record(_rec(node_id='r01'))
        tmp_store.record(_rec(node_id='r02'))
        assert len(tmp_store.query(node_id='r01')) == 1

    def test_query_by_status(self, tmp_store):
        tmp_store.record(_rec(status='success'))
        tmp_store.record(_rec(status='failed'))
        assert len(tmp_store.query(status='success')) == 1

    def test_query_limit(self, tmp_store):
        for _ in range(10):
            tmp_store.record(_rec())
        assert len(tmp_store.query(limit=3)) == 3

    def test_query_newest_first(self, tmp_store):
        for i in range(3):
            r = _rec()
            r.started_at = f'2026-01-0{i+1}T00:00:00+00:00'
            tmp_store.record(r)
        results = tmp_store.query()
        assert results[0].started_at > results[-1].started_at

    def test_skill_ids(self, tmp_store):
        tmp_store.record(_rec(skill_id='etd.a'))
        tmp_store.record(_rec(skill_id='etd.b'))
        tmp_store.record(_rec(skill_id='etd.a'))
        ids = tmp_store.skill_ids()
        assert set(ids) == {'etd.a', 'etd.b'}

    def test_node_ids(self, tmp_store):
        tmp_store.record(_rec(node_id='n1'))
        tmp_store.record(_rec(node_id='n2'))
        assert set(tmp_store.node_ids()) == {'n1', 'n2'}

    def test_clear(self, tmp_store):
        tmp_store.record(_rec())
        tmp_store.clear()
        assert tmp_store.execution_count == 0

    def test_clear_wipes_file(self, tmp_path):
        path = tmp_path / 'e.jsonl'
        store = TelemetryStore(path)
        store.record(_rec())
        store.clear()
        store2 = TelemetryStore(path)
        assert store2.execution_count == 0

    def test_malformed_lines_skipped(self, tmp_path):
        path = tmp_path / 'e.jsonl'
        path.write_text('not-json\n{"bad": true}\n')
        store = TelemetryStore(path)
        assert store.execution_count == 0

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / 'a' / 'b' / 'c.jsonl'
        store = TelemetryStore(nested)
        store.record(_rec())
        assert nested.exists()

    def test_query_since(self, tmp_store):
        r1 = _rec(); r1.started_at = '2026-01-01T00:00:00+00:00'
        r2 = _rec(); r2.started_at = '2026-06-01T00:00:00+00:00'
        tmp_store.record(r1); tmp_store.record(r2)
        result = tmp_store.query(since='2026-03-01T00:00:00+00:00')
        assert len(result) == 1
        assert result[0].started_at == '2026-06-01T00:00:00+00:00'


# ── TelemetryAnalyzer ─────────────────────────────────────────────────────────

class TestTelemetryAnalyzer:
    def _populated_store(self, tmp_path) -> TelemetryStore:
        store = TelemetryStore(tmp_path / 'e.jsonl')
        store.record(_rec(skill_id='etd.pick', duration_ms=1000, status='success'))
        store.record(_rec(skill_id='etd.pick', duration_ms=1200, status='success'))
        store.record(_rec(skill_id='etd.pick', duration_ms=800,  status='failed',
                          failure_reason='grip_fail'))
        store.record(_rec(skill_id='etd.inspect', duration_ms=500, status='success',
                          node_id='r02'))
        return store

    def test_skill_stats_none_for_unknown(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        assert TelemetryAnalyzer(store).skill_stats('unknown.skill') is None

    def test_skill_stats_counts(self, tmp_path):
        store = self._populated_store(tmp_path)
        stats = TelemetryAnalyzer(store).skill_stats('etd.pick')
        assert stats.execution_count == 3
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert stats.aborted_count == 0

    def test_skill_stats_success_rate(self, tmp_path):
        store = self._populated_store(tmp_path)
        stats = TelemetryAnalyzer(store).skill_stats('etd.pick')
        assert abs(stats.success_rate - 2/3) < 0.001

    def test_skill_stats_durations(self, tmp_path):
        store = self._populated_store(tmp_path)
        stats = TelemetryAnalyzer(store).skill_stats('etd.pick')
        assert stats.min_duration_ms == 800
        assert stats.max_duration_ms == 1200
        assert 900 < stats.mean_duration_ms < 1100

    def test_skill_stats_common_failures(self, tmp_path):
        store = self._populated_store(tmp_path)
        stats = TelemetryAnalyzer(store).skill_stats('etd.pick')
        assert stats.common_failures[0][0] == 'grip_fail'
        assert stats.common_failures[0][1] == 1

    def test_skill_stats_percentiles(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        for d in [100, 200, 300, 400, 500]:
            store.record(_rec(duration_ms=d))
        stats = TelemetryAnalyzer(store).skill_stats('etd.pick')
        assert stats.p50_ms > 0
        assert stats.p95_ms >= stats.p50_ms
        assert stats.p99_ms >= stats.p95_ms

    def test_skill_stats_to_dict(self, tmp_path):
        store = self._populated_store(tmp_path)
        d = TelemetryAnalyzer(store).skill_stats('etd.pick').to_dict()
        assert 'p95_ms' in d
        assert 'common_failures' in d

    def test_skill_stats_summary_str(self, tmp_path):
        store = self._populated_store(tmp_path)
        s = TelemetryAnalyzer(store).skill_stats('etd.pick').summary()
        assert 'etd.pick' in s
        assert 'p95' in s

    def test_node_stats_empty(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        ns = TelemetryAnalyzer(store).node_stats('ghost')
        assert ns['execution_count'] == 0

    def test_node_stats_populated(self, tmp_path):
        store = self._populated_store(tmp_path)
        ns = TelemetryAnalyzer(store).node_stats('r01')
        assert ns['execution_count'] >= 3
        assert 'success_rate' in ns
        assert 'skills_executed' in ns

    def test_recent_failures_returns_list(self, tmp_path):
        store = self._populated_store(tmp_path)
        analyzer = TelemetryAnalyzer(store)
        failures = analyzer.recent_failures(limit=5)
        assert isinstance(failures, list)

    def test_recent_failures_limit_zero(self, tmp_path):
        store = self._populated_store(tmp_path)
        assert TelemetryAnalyzer(store).recent_failures(limit=0) == []

    def test_anomalies_insufficient_data(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        store.record(_rec(duration_ms=1000))
        assert TelemetryAnalyzer(store).anomalies() == []

    def test_anomalies_zero_stdev(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        for _ in range(5):
            store.record(_rec(duration_ms=1000))
        assert TelemetryAnalyzer(store).anomalies() == []

    def test_anomalies_detects_outlier(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        for _ in range(9):
            store.record(_rec(duration_ms=1000))
        store.record(_rec(duration_ms=9000))  # outlier
        results = TelemetryAnalyzer(store).anomalies(z_threshold=2.0)
        assert len(results) >= 1
        assert results[0][1] > 2.0

    def test_anomalies_sorted_desc(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        for d in [1000, 1100, 900, 950, 1050, 9000, 50]:
            store.record(_rec(duration_ms=d))
        results = TelemetryAnalyzer(store).anomalies(z_threshold=0.1)
        z_scores = [z for _, z in results]
        assert z_scores == sorted(z_scores, reverse=True)

    def test_anomalies_skill_filter(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        for _ in range(5):
            store.record(_rec(skill_id='etd.pick', duration_ms=1000))
        store.record(_rec(skill_id='etd.pick', duration_ms=9000))
        for _ in range(5):
            store.record(_rec(skill_id='etd.inspect', duration_ms=500))
        results = TelemetryAnalyzer(store).anomalies(skill_id='etd.pick', z_threshold=1.5)
        assert all(r.skill_id == 'etd.pick' for r, _ in results)

    def test_report_structure(self, tmp_path):
        store = self._populated_store(tmp_path)
        rpt = TelemetryAnalyzer(store).report()
        assert 'generated_at' in rpt
        assert 'total_executions' in rpt
        assert 'skill_count' in rpt
        assert 'node_count' in rpt
        assert isinstance(rpt['skills'], list)
        assert isinstance(rpt['nodes'], list)

    def test_report_empty_store(self, tmp_path):
        store = TelemetryStore(tmp_path / 'e.jsonl')
        rpt = TelemetryAnalyzer(store).report()
        assert rpt['total_executions'] == 0
        assert rpt['skill_count'] == 0


# ── REST API /telemetry ───────────────────────────────────────────────────────

import os
import unittest.mock as mock

@pytest.fixture(autouse=True)
def patch_store_path(tmp_path, monkeypatch):
    """Redirect the API's store path to a temp file for each test."""
    import api.telemetry as _mod
    monkeypatch.setattr(_mod, '_STORE_PATH', tmp_path / 'api_execs.jsonl')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestTelemetryApiRecord:
    def test_record_returns_201(self, api_client):
        r = api_client.post('/telemetry/executions', json={
            'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success',
            'total_duration_ms': 1000,
        })
        assert r.status_code == 201

    def test_record_body_has_execution_id(self, api_client):
        data = api_client.post('/telemetry/executions', json={
            'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success',
        }).json()
        assert 'execution_id' in data

    def test_record_explicit_ids(self, api_client):
        data = api_client.post('/telemetry/executions', json={
            'skill_id': 'etd.pick', 'node_id': 'r01',
            'execution_id': 'my-exec-123',
            'started_at': '2026-01-01T00:00:00+00:00',
            'completed_at': '2026-01-01T00:00:01+00:00',
            'status': 'success', 'total_duration_ms': 500,
        }).json()
        assert data['execution_id'] == 'my-exec-123'


class TestTelemetryApiList:
    def _post(self, api_client, **kwargs):
        defaults = {'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success'}
        defaults.update(kwargs)
        api_client.post('/telemetry/executions', json=defaults)

    def test_list_returns_200(self, api_client):
        r = api_client.get('/telemetry/executions')
        assert r.status_code == 200

    def test_list_empty(self, api_client):
        data = api_client.get('/telemetry/executions').json()
        assert data['count'] == 0
        assert data['executions'] == []

    def test_list_after_record(self, api_client):
        self._post(api_client)
        data = api_client.get('/telemetry/executions').json()
        assert data['count'] == 1

    def test_list_filter_skill_id(self, api_client):
        self._post(api_client, skill_id='etd.pick')
        self._post(api_client, skill_id='etd.inspect')
        data = api_client.get('/telemetry/executions?skill_id=etd.pick').json()
        assert all(e['skill_id'] == 'etd.pick' for e in data['executions'])

    def test_list_filter_status(self, api_client):
        self._post(api_client, status='success')
        self._post(api_client, status='failed')
        data = api_client.get('/telemetry/executions?status=failed').json()
        assert data['count'] == 1

    def test_list_limit(self, api_client):
        for _ in range(10):
            self._post(api_client)
        data = api_client.get('/telemetry/executions?limit=3').json()
        assert data['count'] == 3


class TestTelemetryApiStats:
    def test_stats_404_unknown(self, api_client):
        r = api_client.get('/telemetry/stats/unknown.skill')
        assert r.status_code == 404

    def test_stats_200_after_record(self, api_client):
        api_client.post('/telemetry/executions', json={
            'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success',
            'total_duration_ms': 1000,
        })
        r = api_client.get('/telemetry/stats/etd.pick')
        assert r.status_code == 200

    def test_stats_structure(self, api_client):
        api_client.post('/telemetry/executions', json={
            'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success',
            'total_duration_ms': 1000,
        })
        data = api_client.get('/telemetry/stats/etd.pick').json()
        assert 'success_rate' in data
        assert 'p95_ms' in data
        assert 'execution_count' in data


class TestTelemetryApiReport:
    def test_report_200(self, api_client):
        r = api_client.get('/telemetry/report')
        assert r.status_code == 200

    def test_report_structure(self, api_client):
        data = api_client.get('/telemetry/report').json()
        assert 'generated_at' in data
        assert 'total_executions' in data
        assert 'skills' in data
        assert 'nodes' in data

    def test_report_empty(self, api_client):
        data = api_client.get('/telemetry/report').json()
        assert data['total_executions'] == 0


class TestTelemetryApiAnomalies:
    def _seed(self, api_client, n_normal=9, outlier_ms=9000):
        for _ in range(n_normal):
            api_client.post('/telemetry/executions', json={
                'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success',
                'total_duration_ms': 1000,
            })
        api_client.post('/telemetry/executions', json={
            'skill_id': 'etd.pick', 'node_id': 'r01', 'status': 'success',
            'total_duration_ms': outlier_ms,
        })

    def test_anomalies_200(self, api_client):
        r = api_client.get('/telemetry/anomalies')
        assert r.status_code == 200

    def test_anomalies_structure(self, api_client):
        data = api_client.get('/telemetry/anomalies').json()
        assert 'count' in data
        assert 'anomalies' in data
        assert 'z_threshold' in data

    def test_anomalies_detects_outlier(self, api_client):
        self._seed(api_client)
        data = api_client.get('/telemetry/anomalies?z_threshold=2.0').json()
        assert data['count'] >= 1

    def test_anomalies_has_z_score(self, api_client):
        self._seed(api_client)
        data = api_client.get('/telemetry/anomalies?z_threshold=2.0').json()
        if data['anomalies']:
            assert 'z_score' in data['anomalies'][0]

    def test_anomalies_filter_by_skill(self, api_client):
        self._seed(api_client)
        data = api_client.get(
            '/telemetry/anomalies?skill_id=etd.pick&z_threshold=2.0'
        ).json()
        for a in data['anomalies']:
            assert a['skill_id'] == 'etd.pick'
