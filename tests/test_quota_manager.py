"""Tests for marketplace.quota_manager and the /quota REST API."""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from marketplace.quota_manager import QuotaManager, QuotaPolicy, QuotaCheckResult


# ── helpers ───────────────────────────────────────────────────────────────────

UTC = datetime.timezone.utc


def _now() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def _ts(dt: datetime.datetime) -> str:
    return dt.isoformat(timespec='seconds')


@pytest.fixture()
def mgr(tmp_path) -> QuotaManager:
    return QuotaManager(tmp_path / 'quota')


def _policy(skill_id='etd.pick', node_id='*', max_per_hour=None,
             max_per_day=None, burst=0, enabled=True) -> QuotaPolicy:
    return QuotaPolicy(
        skill_id=skill_id, node_id=node_id,
        max_per_hour=max_per_hour, max_per_day=max_per_day,
        burst_allowance=burst, enabled=enabled,
    )


# ── QuotaPolicy ───────────────────────────────────────────────────────────────

class TestQuotaPolicy:
    def test_to_dict_keys(self):
        p = _policy()
        d = p.to_dict()
        assert set(d) >= {'skill_id', 'node_id', 'max_per_hour',
                          'max_per_day', 'burst_allowance', 'enabled'}

    def test_round_trip(self):
        p = _policy(skill_id='etd.inspect', max_per_hour=10, max_per_day=100, burst=5)
        p2 = QuotaPolicy.from_dict(p.to_dict())
        assert p2.skill_id == 'etd.inspect'
        assert p2.max_per_hour == 10
        assert p2.burst_allowance == 5

    def test_specificity_both_wildcard(self):
        assert _policy(skill_id='*', node_id='*').specificity == 0

    def test_specificity_skill_only(self):
        assert _policy(skill_id='etd.pick', node_id='*').specificity == 2

    def test_specificity_node_only(self):
        assert _policy(skill_id='*', node_id='r01').specificity == 1

    def test_specificity_both_exact(self):
        assert _policy(skill_id='etd.pick', node_id='r01').specificity == 3

    def test_defaults(self):
        p = QuotaPolicy.from_dict({'skill_id': 'x', 'version': '1.0'})
        assert p.node_id == '*'
        assert p.burst_allowance == 0
        assert p.enabled is True


# ── QuotaManager — policy CRUD ────────────────────────────────────────────────

class TestQuotaManagerPolicies:
    def test_empty_list(self, mgr):
        assert mgr.list_policies() == []

    def test_set_and_get(self, mgr):
        p = _policy(max_per_hour=60)
        mgr.set_policy(p)
        got = mgr.get_policy('etd.pick')
        assert got is not None
        assert got.max_per_hour == 60

    def test_get_unknown_none(self, mgr):
        assert mgr.get_policy('ghost.skill') is None

    def test_list_returns_all(self, mgr):
        mgr.set_policy(_policy('etd.pick'))
        mgr.set_policy(_policy('etd.inspect'))
        assert len(mgr.list_policies()) == 2

    def test_remove_existing(self, mgr):
        mgr.set_policy(_policy())
        assert mgr.remove_policy('etd.pick') is True
        assert mgr.get_policy('etd.pick') is None

    def test_remove_unknown_false(self, mgr):
        assert mgr.remove_policy('ghost') is False

    def test_update_replaces(self, mgr):
        mgr.set_policy(_policy(max_per_hour=10))
        mgr.set_policy(_policy(max_per_hour=20))
        assert mgr.get_policy('etd.pick').max_per_hour == 20

    def test_persists_policies(self, tmp_path):
        m1 = QuotaManager(tmp_path / 'q')
        m1.set_policy(_policy(max_per_hour=30))
        m2 = QuotaManager(tmp_path / 'q')
        assert m2.get_policy('etd.pick').max_per_hour == 30

    def test_creates_dir(self, tmp_path):
        m = QuotaManager(tmp_path / 'a' / 'b' / 'c')
        m.set_policy(_policy())
        assert (tmp_path / 'a' / 'b' / 'c' / 'policies.json').exists()


# ── QuotaManager — check ──────────────────────────────────────────────────────

class TestQuotaManagerCheck:
    def test_no_policy_allowed(self, mgr):
        r = mgr.check('etd.pick')
        assert r.allowed is True
        assert r.reason == 'no_policy'

    def test_disabled_policy_blocked(self, mgr):
        mgr.set_policy(_policy(enabled=False))
        r = mgr.check('etd.pick')
        assert r.allowed is False
        assert r.reason == 'disabled'

    def test_under_hourly_limit_allowed(self, mgr):
        mgr.set_policy(_policy(max_per_hour=5))
        now = _now()
        for i in range(4):
            mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(minutes=i)))
        r = mgr.check('etd.pick', _now=now)
        assert r.allowed is True
        assert r.used_last_hour == 4

    def test_at_hourly_limit_blocked(self, mgr):
        mgr.set_policy(_policy(max_per_hour=3))
        now = _now()
        for i in range(3):
            mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(minutes=i)))
        r = mgr.check('etd.pick', _now=now)
        assert r.allowed is False
        assert r.reason == 'hourly_limit'
        assert r.remaining_hour == 0

    def test_burst_extends_hourly_limit(self, mgr):
        mgr.set_policy(_policy(max_per_hour=3, burst=2))
        now = _now()
        for i in range(4):
            mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(minutes=i)))
        r = mgr.check('etd.pick', _now=now)
        assert r.allowed is True  # 4 < 3+2=5

    def test_hourly_window_excludes_old(self, mgr):
        mgr.set_policy(_policy(max_per_hour=2))
        now = _now()
        # 3 executions but 2 are >1h old
        mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(hours=2)))
        mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(hours=2)))
        mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(minutes=30)))
        r = mgr.check('etd.pick', _now=now)
        assert r.used_last_hour == 1
        assert r.allowed is True

    def test_daily_limit_blocked(self, mgr):
        mgr.set_policy(_policy(max_per_day=5))
        now = _now()
        for i in range(5):
            mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(hours=i)))
        r = mgr.check('etd.pick', _now=now)
        assert r.allowed is False
        assert r.reason == 'daily_limit'

    def test_daily_window_excludes_old(self, mgr):
        mgr.set_policy(_policy(max_per_day=3))
        now = _now()
        mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(hours=25)))
        mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(hours=12)))
        r = mgr.check('etd.pick', _now=now)
        assert r.used_last_day == 1
        assert r.allowed is True

    def test_remaining_counts(self, mgr):
        mgr.set_policy(_policy(max_per_hour=10, max_per_day=100))
        now = _now()
        for i in range(3):
            mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(minutes=i)))
        r = mgr.check('etd.pick', _now=now)
        assert r.remaining_hour == 7
        assert r.remaining_day == 97

    def test_no_hourly_limit_remaining_none(self, mgr):
        mgr.set_policy(_policy(max_per_day=100))
        r = mgr.check('etd.pick')
        assert r.remaining_hour is None

    def test_no_daily_limit_remaining_none(self, mgr):
        mgr.set_policy(_policy(max_per_hour=10))
        r = mgr.check('etd.pick')
        assert r.remaining_day is None

    def test_policy_matched_field(self, mgr):
        mgr.set_policy(_policy(skill_id='etd.pick'))
        r = mgr.check('etd.pick')
        assert r.policy_matched == 'etd.pick'

    def test_wildcard_policy_matches_any_skill(self, mgr):
        mgr.set_policy(_policy(skill_id='*', max_per_hour=2))
        now = _now()
        mgr.record('etd.inspect', timestamp=_ts(now - datetime.timedelta(minutes=1)))
        mgr.record('etd.inspect', timestamp=_ts(now - datetime.timedelta(minutes=2)))
        r = mgr.check('etd.inspect', _now=now)
        assert r.allowed is False

    def test_specific_policy_overrides_wildcard(self, mgr):
        mgr.set_policy(_policy(skill_id='*', max_per_hour=1))
        mgr.set_policy(_policy(skill_id='etd.pick', max_per_hour=100))
        now = _now()
        for i in range(50):
            mgr.record('etd.pick', timestamp=_ts(now - datetime.timedelta(minutes=i)))
        r = mgr.check('etd.pick', _now=now)
        assert r.allowed is True
        assert r.policy_matched == 'etd.pick'

    def test_node_specific_policy(self, mgr):
        mgr.set_policy(_policy(skill_id='etd.pick', node_id='r01', max_per_hour=2))
        now = _now()
        mgr.record('etd.pick', 'r01', timestamp=_ts(now - datetime.timedelta(minutes=1)))
        mgr.record('etd.pick', 'r01', timestamp=_ts(now - datetime.timedelta(minutes=2)))
        r = mgr.check('etd.pick', 'r01', _now=now)
        assert r.allowed is False

    def test_check_result_to_dict(self, mgr):
        mgr.set_policy(_policy(max_per_hour=10))
        r = mgr.check('etd.pick')
        d = r.to_dict()
        assert 'allowed' in d
        assert 'reason' in d
        assert 'remaining_hour' in d


# ── QuotaManager — record & usage ─────────────────────────────────────────────

class TestQuotaManagerUsage:
    def test_record_increments_count(self, mgr):
        now = _now()
        mgr.record('etd.pick', timestamp=_ts(now))
        rows = mgr.usage(skill_id='etd.pick')
        assert rows[0]['used_last_hour'] == 1

    def test_usage_empty(self, mgr):
        assert mgr.usage() == []

    def test_usage_filter_skill(self, mgr):
        now = _now()
        mgr.record('etd.pick', timestamp=_ts(now))
        mgr.record('etd.inspect', timestamp=_ts(now))
        rows = mgr.usage(skill_id='etd.pick')
        assert len(rows) == 1
        assert rows[0]['skill_id'] == 'etd.pick'

    def test_usage_filter_node(self, mgr):
        now = _now()
        mgr.record('etd.pick', 'r01', timestamp=_ts(now))
        mgr.record('etd.pick', 'r02', timestamp=_ts(now))
        rows = mgr.usage(node_id='r01')
        assert all(r['node_id'] == 'r01' for r in rows)

    def test_usage_persists(self, tmp_path):
        m1 = QuotaManager(tmp_path / 'q')
        m1.record('etd.pick')
        m2 = QuotaManager(tmp_path / 'q')
        rows = m2.usage(skill_id='etd.pick')
        assert rows[0]['total_recorded'] >= 1

    def test_clear_all(self, mgr):
        mgr.record('etd.pick')
        mgr.record('etd.inspect')
        cleared = mgr.clear_usage()
        assert cleared == 2
        assert mgr.usage() == []

    def test_clear_by_skill(self, mgr):
        mgr.record('etd.pick')
        mgr.record('etd.inspect')
        mgr.clear_usage(skill_id='etd.pick')
        rows = mgr.usage()
        assert all(r['skill_id'] != 'etd.pick' for r in rows)

    def test_clear_returns_count(self, mgr):
        mgr.record('etd.pick', 'r01')
        mgr.record('etd.pick', 'r02')
        assert mgr.clear_usage(skill_id='etd.pick') == 2


# ── REST API /quota ───────────────────────────────────────────────────────────

import api.quota as _quota_mod


@pytest.fixture(autouse=True)
def patch_quota_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_quota_mod, '_QUOTA_DIR', tmp_path / 'quota')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestQuotaApiPolicies:
    def test_create_201(self, api_client):
        r = api_client.post('/quota/policies', json={
            'skill_id': 'etd.pick', 'max_per_hour': 60,
        })
        assert r.status_code == 201

    def test_create_has_skill_id(self, api_client):
        data = api_client.post('/quota/policies', json={
            'skill_id': 'etd.pick', 'max_per_hour': 60,
        }).json()
        assert data['skill_id'] == 'etd.pick'

    def test_list_200(self, api_client):
        r = api_client.get('/quota/policies')
        assert r.status_code == 200

    def test_list_empty(self, api_client):
        data = api_client.get('/quota/policies').json()
        assert data['count'] == 0

    def test_list_after_create(self, api_client):
        api_client.post('/quota/policies', json={'skill_id': 'etd.pick'})
        data = api_client.get('/quota/policies').json()
        assert data['count'] == 1

    def test_get_found(self, api_client):
        api_client.post('/quota/policies', json={
            'skill_id': 'etd.pick', 'max_per_hour': 10,
        })
        r = api_client.get('/quota/policies/etd.pick')
        assert r.status_code == 200
        assert r.json()['max_per_hour'] == 10

    def test_get_404(self, api_client):
        r = api_client.get('/quota/policies/ghost.skill')
        assert r.status_code == 404

    def test_delete_200(self, api_client):
        api_client.post('/quota/policies', json={'skill_id': 'etd.pick'})
        r = api_client.delete('/quota/policies/etd.pick')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        r = api_client.delete('/quota/policies/ghost.skill')
        assert r.status_code == 404


class TestQuotaApiCheck:
    def test_check_no_policy_allowed(self, api_client):
        data = api_client.post('/quota/check', json={'skill_id': 'etd.pick'}).json()
        assert data['allowed'] is True
        assert data['reason'] == 'no_policy'

    def test_check_structure(self, api_client):
        data = api_client.post('/quota/check', json={'skill_id': 'etd.pick'}).json()
        assert 'used_last_hour' in data
        assert 'remaining_hour' in data

    def test_check_after_record_blocks(self, api_client):
        api_client.post('/quota/policies', json={
            'skill_id': 'etd.pick', 'max_per_hour': 2,
        })
        api_client.post('/quota/record', json={'skill_id': 'etd.pick'})
        api_client.post('/quota/record', json={'skill_id': 'etd.pick'})
        data = api_client.post('/quota/check', json={'skill_id': 'etd.pick'}).json()
        assert data['allowed'] is False
        assert data['reason'] == 'hourly_limit'


class TestQuotaApiRecord:
    def test_record_201(self, api_client):
        r = api_client.post('/quota/record', json={'skill_id': 'etd.pick'})
        assert r.status_code == 201

    def test_record_appears_in_usage(self, api_client):
        api_client.post('/quota/record', json={'skill_id': 'etd.pick', 'node_id': 'r01'})
        data = api_client.get('/quota/usage?skill_id=etd.pick').json()
        assert data['count'] == 1
        assert data['usage'][0]['used_last_hour'] == 1


class TestQuotaApiUsage:
    def test_usage_200(self, api_client):
        r = api_client.get('/quota/usage')
        assert r.status_code == 200

    def test_usage_empty(self, api_client):
        data = api_client.get('/quota/usage').json()
        assert data['count'] == 0

    def test_usage_filter(self, api_client):
        api_client.post('/quota/record', json={'skill_id': 'etd.pick'})
        api_client.post('/quota/record', json={'skill_id': 'etd.inspect'})
        data = api_client.get('/quota/usage?skill_id=etd.pick').json()
        assert data['count'] == 1

    def test_clear_usage(self, api_client):
        api_client.post('/quota/record', json={'skill_id': 'etd.pick'})
        r = api_client.delete('/quota/usage')
        assert r.status_code == 200
        assert r.json()['cleared'] >= 1
        data = api_client.get('/quota/usage').json()
        assert data['count'] == 0
