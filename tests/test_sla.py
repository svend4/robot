"""Tests for marketplace.sla and the /sla REST API."""
from __future__ import annotations

import pytest

from marketplace.sla import SLAPolicy, SLAViolation, SLAResult, SLAStore, _percentile


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> SLAStore:
    return SLAStore(tmp_path / 'sla')


def _execs(*pairs):
    """Build execution list from (status, duration_ms) pairs."""
    return [{'status': s, 'total_duration_ms': d} for s, d in pairs]


# ── _percentile ───────────────────────────────────────────────────────────────

class TestPercentile:
    def test_empty(self):
        assert _percentile([], 95) == 0.0

    def test_single(self):
        assert _percentile([100.0], 95) == 100.0

    def test_p50_even(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5

    def test_p100(self):
        assert _percentile([10.0, 20.0, 30.0], 100) == 30.0

    def test_p0(self):
        assert _percentile([10.0, 20.0, 30.0], 0) == 10.0


# ── SLAPolicy ─────────────────────────────────────────────────────────────────

class TestSLAPolicy:
    def test_defaults(self):
        p = SLAPolicy(skill_id='etd.pick')
        assert p.max_p95_ms is None
        assert p.min_success_rate is None
        assert p.window_hours == 24
        assert p.created_at

    def test_round_trip(self):
        p = SLAPolicy(skill_id='etd.pick', max_p95_ms=2000,
                      min_success_rate=0.95, window_hours=12)
        p2 = SLAPolicy.from_dict(p.to_dict())
        assert p2.skill_id == 'etd.pick'
        assert p2.max_p95_ms == 2000
        assert p2.min_success_rate == 0.95
        assert p2.window_hours == 12

    def test_to_dict_keys(self):
        keys = set(SLAPolicy(skill_id='s').to_dict())
        assert {'skill_id', 'max_p95_ms', 'min_success_rate',
                'window_hours', 'created_at', 'updated_at'} <= keys

    def test_from_dict_defaults(self):
        p = SLAPolicy.from_dict({'skill_id': 's'})
        assert p.max_p95_ms is None
        assert p.window_hours == 24


# ── SLAViolation ──────────────────────────────────────────────────────────────

class TestSLAViolation:
    def test_to_dict_keys(self):
        v = SLAViolation(field='latency_p95', threshold=2000.0,
                         actual=2500.0, message='exceeded')
        keys = set(v.to_dict())
        assert {'field', 'threshold', 'actual', 'message'} <= keys


# ── SLAResult ─────────────────────────────────────────────────────────────────

class TestSLAResult:
    def test_to_dict_keys(self):
        r = SLAResult(skill_id='s', compliant=True, violations=[],
                      p95_ms=None, success_rate=None, sample_count=0)
        keys = set(r.to_dict())
        assert {'skill_id', 'compliant', 'violations', 'p95_ms',
                'success_rate', 'sample_count', 'evaluated_at'} <= keys

    def test_compliant_flag(self):
        r = SLAResult(skill_id='s', compliant=False,
                      violations=[SLAViolation('f', 1.0, 2.0, 'm')],
                      p95_ms=None, success_rate=None, sample_count=0)
        assert r.compliant is False
        assert len(r.to_dict()['violations']) == 1


# ── SLAStore — policy CRUD ────────────────────────────────────────────────────

class TestSLAStoreCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.policy_count == 0
        assert store.list_policies() == []

    def test_set_creates(self, tmp_path):
        store = _store(tmp_path)
        policy, created = store.set_policy('etd.pick', max_p95_ms=2000)
        assert created is True
        assert policy.max_p95_ms == 2000

    def test_set_updates(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=2000)
        policy, created = store.set_policy('etd.pick', max_p95_ms=1500)
        assert created is False
        assert policy.max_p95_ms == 1500

    def test_set_invalid_rate_raises(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).set_policy('etd.pick', min_success_rate=1.5)

    def test_set_invalid_rate_negative(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).set_policy('etd.pick', min_success_rate=-0.1)

    def test_get_policy(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=2000)
        assert store.get_policy('etd.pick') is not None

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get_policy('ghost') is None

    def test_remove_existing(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=2000)
        assert store.remove_policy('etd.pick') is True
        assert store.get_policy('etd.pick') is None

    def test_remove_unknown_false(self, tmp_path):
        assert _store(tmp_path).remove_policy('ghost') is False

    def test_list_policies(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick')
        store.set_policy('etd.weld')
        assert len(store.list_policies()) == 2

    def test_policy_count(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick')
        assert store.policy_count == 1


# ── SLAStore — evaluate ───────────────────────────────────────────────────────

class TestEvaluate:
    def test_no_policy_returns_none(self, tmp_path):
        assert _store(tmp_path).evaluate('etd.pick', []) is None

    def test_empty_executions(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=2000, min_success_rate=0.9)
        result = store.evaluate('etd.pick', [])
        assert result.sample_count == 0
        assert result.p95_ms is None
        assert result.success_rate is None
        assert result.compliant is True  # no data → no violation

    def test_all_success_compliant(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', min_success_rate=0.9)
        execs = _execs(*[('success', 1000)] * 10)
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is True
        assert result.success_rate == 1.0

    def test_success_rate_violation(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', min_success_rate=0.9)
        execs = _execs(('success', 1000), ('failed', 500), ('failed', 500))
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is False
        fields = [v['field'] for v in result.to_dict()['violations']]
        assert 'success_rate' in fields

    def test_latency_violation(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=1000)
        execs = _execs(*[('success', 2000)] * 5)
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is False
        fields = [v['field'] for v in result.to_dict()['violations']]
        assert 'latency_p95' in fields

    def test_both_violations(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=500, min_success_rate=0.95)
        execs = _execs(('success', 2000), ('failed', 100))
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is False
        assert len(result.violations) == 2

    def test_no_latency_target(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', min_success_rate=0.9)
        execs = _execs(*[('success', 99999)] * 5)
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is True

    def test_no_success_rate_target(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=500)
        execs = _execs(('failed', 100), ('failed', 200))
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is True  # no success rate target set

    def test_p95_computed(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=9999)
        execs = _execs(*[('success', i * 100) for i in range(1, 11)])
        result = store.evaluate('etd.pick', execs)
        assert result.p95_ms is not None
        assert result.p95_ms > 0

    def test_sample_count(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick')
        execs = _execs(('success', 100), ('success', 200), ('failed', 50))
        result = store.evaluate('etd.pick', execs)
        assert result.sample_count == 3

    def test_skill_id_in_result(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick')
        result = store.evaluate('etd.pick', [])
        assert result.skill_id == 'etd.pick'

    def test_executions_without_duration_excluded_from_latency(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=9999)
        execs = [{'status': 'success'}, {'status': 'failed'}]
        result = store.evaluate('etd.pick', execs)
        assert result.p95_ms is None

    def test_compliant_latency_within_limit(self, tmp_path):
        store = _store(tmp_path)
        store.set_policy('etd.pick', max_p95_ms=2000)
        execs = _execs(*[('success', 500)] * 10)
        result = store.evaluate('etd.pick', execs)
        assert result.compliant is True


# ── Persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_persists_policy(self, tmp_path):
        p = tmp_path / 'sla'
        SLAStore(p).set_policy('etd.pick', max_p95_ms=1500, min_success_rate=0.95)
        s2 = SLAStore(p)
        pol = s2.get_policy('etd.pick')
        assert pol is not None
        assert pol.max_p95_ms == 1500
        assert pol.min_success_rate == 0.95

    def test_creates_dir(self, tmp_path):
        s = SLAStore(tmp_path / 'a' / 'b')
        s.set_policy('etd.pick')
        assert (tmp_path / 'a' / 'b' / 'sla_policies.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'sla_policies.json').write_text('bad json')
        s = SLAStore(tmp_path)
        assert s.policy_count == 0


# ── REST API ──────────────────────────────────────────────────────────────────

import api.sla as _sla_mod


@pytest.fixture(autouse=True)
def patch_sla_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_sla_mod, '_SLA_DIR', tmp_path / 'sla')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _set(api_client, skill_id='etd.pick', max_p95_ms=2000,
         min_success_rate=0.95, window_hours=24):
    return api_client.post('/sla/policies', json={
        'skill_id': skill_id, 'max_p95_ms': max_p95_ms,
        'min_success_rate': min_success_rate, 'window_hours': window_hours,
    })


def _eval(api_client, skill_id='etd.pick', execs=None):
    if execs is None:
        execs = [{'status': 'success', 'total_duration_ms': 500}]
    return api_client.post(f'/sla/evaluate/{skill_id}',
                           json={'executions': execs})


class TestSLAAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/sla/policies')
        assert r.status_code == 200
        assert r.json()['policy_count'] == 0

    def test_set_201(self, api_client):
        assert _set(api_client).status_code == 201

    def test_set_200_update(self, api_client):
        _set(api_client)
        assert _set(api_client, max_p95_ms=1000).status_code == 200

    def test_set_has_skill_id(self, api_client):
        assert _set(api_client).json()['skill_id'] == 'etd.pick'

    def test_set_invalid_rate_422(self, api_client):
        r = api_client.post('/sla/policies', json={
            'skill_id': 'etd.pick', 'min_success_rate': 1.5,
        })
        assert r.status_code == 422

    def test_list_after_set(self, api_client):
        _set(api_client)
        _set(api_client, skill_id='etd.weld')
        assert api_client.get('/sla/policies').json()['policy_count'] == 2

    def test_get_found(self, api_client):
        _set(api_client)
        r = api_client.get('/sla/policies/etd.pick')
        assert r.status_code == 200
        assert r.json()['skill_id'] == 'etd.pick'

    def test_get_404(self, api_client):
        assert api_client.get('/sla/policies/ghost').status_code == 404

    def test_delete_200(self, api_client):
        _set(api_client)
        assert api_client.delete('/sla/policies/etd.pick').status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/sla/policies/ghost').status_code == 404

    def test_evaluate_404_no_policy(self, api_client):
        assert _eval(api_client).status_code == 404

    def test_evaluate_compliant(self, api_client):
        _set(api_client, max_p95_ms=9999, min_success_rate=0.5)
        r = _eval(api_client, execs=[{'status': 'success', 'total_duration_ms': 100}])
        assert r.status_code == 200
        assert r.json()['compliant'] is True

    def test_evaluate_violation(self, api_client):
        _set(api_client, max_p95_ms=100, min_success_rate=0.99)
        execs = [{'status': 'failed', 'total_duration_ms': 5000}]
        r = _eval(api_client, execs=execs)
        assert r.json()['compliant'] is False
        assert len(r.json()['violations']) > 0

    def test_evaluate_has_sample_count(self, api_client):
        _set(api_client)
        execs = [{'status': 'success', 'total_duration_ms': 100}] * 3
        r = _eval(api_client, execs=execs)
        assert r.json()['sample_count'] == 3
