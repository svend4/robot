"""Tests for marketplace.bulkhead and the /bulkhead REST API."""
from __future__ import annotations

import pytest

from marketplace.bulkhead import (
    AcquireResult,
    Bulkhead,
    BulkheadConfig,
    BulkheadState,
    BulkheadStore,
    _make_key,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _bh(tmp_path, default_config=None) -> Bulkhead:
    return Bulkhead(data_dir=tmp_path / 'bulkhead', default_config=default_config)


# ── _make_key ─────────────────────────────────────────────────────────────────

class TestMakeKey:
    def test_wildcard_node(self):
        assert _make_key('etd.pick', '*') == 'etd.pick'

    def test_specific_node(self):
        assert _make_key('etd.pick', 'arm-1') == 'etd.pick:arm-1'


# ── BulkheadConfig ────────────────────────────────────────────────────────────

class TestBulkheadConfig:
    def test_defaults(self):
        cfg = BulkheadConfig()
        assert cfg.max_concurrent == 10

    def test_custom(self):
        cfg = BulkheadConfig(max_concurrent=3)
        assert cfg.max_concurrent == 3

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            BulkheadConfig(max_concurrent=0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            BulkheadConfig(max_concurrent=-1)

    def test_round_trip(self):
        cfg = BulkheadConfig(max_concurrent=5)
        cfg2 = BulkheadConfig.from_dict(cfg.to_dict())
        assert cfg2.max_concurrent == 5

    def test_from_dict_defaults(self):
        cfg = BulkheadConfig.from_dict({})
        assert cfg.max_concurrent == 10

    def test_to_dict_key(self):
        assert 'max_concurrent' in BulkheadConfig().to_dict()


# ── BulkheadState ─────────────────────────────────────────────────────────────

class TestBulkheadState:
    def test_defaults(self):
        s = BulkheadState(key='k', skill_id='etd.pick', node_id='*')
        assert s.active_count == 0
        assert s.total_acquired == 0
        assert s.total_released == 0
        assert s.total_rejected == 0

    def test_round_trip(self):
        s = BulkheadState(key='k', skill_id='etd.pick', node_id='*',
                          active_count=3, total_acquired=10,
                          total_released=7, total_rejected=1)
        s2 = BulkheadState.from_dict(s.to_dict())
        assert s2.active_count == 3
        assert s2.total_acquired == 10
        assert s2.total_rejected == 1

    def test_to_dict_keys(self):
        keys = set(BulkheadState(key='k', skill_id='x', node_id='*').to_dict())
        assert {'key', 'skill_id', 'node_id', 'active_count',
                'total_acquired', 'total_released', 'total_rejected'} <= keys


# ── AcquireResult ─────────────────────────────────────────────────────────────

class TestAcquireResult:
    def test_to_dict_keys(self):
        r = AcquireResult(acquired=True, reason='ok', skill_id='x',
                          node_id='*', active_count=1, max_concurrent=5)
        keys = set(r.to_dict())
        assert {'acquired', 'reason', 'skill_id', 'node_id',
                'active_count', 'max_concurrent'} <= keys


# ── BulkheadStore ─────────────────────────────────────────────────────────────

class TestBulkheadStore:
    @pytest.fixture()
    def store(self, tmp_path) -> BulkheadStore:
        return BulkheadStore(tmp_path / 'bh')

    def test_empty(self, store):
        assert store.list_states() == []
        assert store.list_configs() == {}

    def test_get_or_create(self, store):
        s = store.get_or_create_state('etd.pick', '*')
        assert s.state_count if hasattr(s, 'state_count') else True
        assert s.active_count == 0

    def test_save_and_get_state(self, store):
        s = store.get_or_create_state('etd.pick', '*')
        s.active_count = 3
        store.save_state(s)
        s2 = store.get_state('etd.pick', '*')
        assert s2.active_count == 3

    def test_get_unknown_none(self, store):
        assert store.get_state('ghost', '*') is None

    def test_remove_state(self, store):
        s = store.get_or_create_state('etd.pick', '*')
        store.save_state(s)
        assert store.remove_state('etd.pick', '*') is True
        assert store.get_state('etd.pick', '*') is None

    def test_remove_unknown_false(self, store):
        assert store.remove_state('ghost', '*') is False

    def test_list_states(self, store):
        store.save_state(store.get_or_create_state('etd.a', '*'))
        store.save_state(store.get_or_create_state('etd.b', '*'))
        assert len(store.list_states()) == 2

    def test_set_get_config(self, store):
        store.set_config('etd.pick', BulkheadConfig(max_concurrent=3))
        cfg = store.get_config('etd.pick')
        assert cfg.max_concurrent == 3

    def test_get_config_unknown_none(self, store):
        assert store.get_config('ghost') is None

    def test_remove_config(self, store):
        store.set_config('etd.pick', BulkheadConfig())
        assert store.remove_config('etd.pick') is True
        assert store.get_config('etd.pick') is None

    def test_remove_config_unknown_false(self, store):
        assert store.remove_config('ghost') is False

    def test_persists(self, tmp_path):
        p = tmp_path / 'bh'
        s1 = BulkheadStore(p)
        state = s1.get_or_create_state('etd.pick', '*')
        state.active_count = 4
        s1.save_state(state)
        s1.set_config('etd.pick', BulkheadConfig(max_concurrent=6))
        s2 = BulkheadStore(p)
        assert s2.get_state('etd.pick', '*').active_count == 4
        assert s2.get_config('etd.pick').max_concurrent == 6

    def test_creates_dir(self, tmp_path):
        s = BulkheadStore(tmp_path / 'a' / 'b')
        s.set_config('x', BulkheadConfig())
        assert (tmp_path / 'a' / 'b' / 'bulkhead.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'bulkhead.json').write_text('bad')
        s = BulkheadStore(tmp_path)
        assert s.list_states() == []
        assert s.list_configs() == {}


# ── Bulkhead — acquire ────────────────────────────────────────────────────────

class TestAcquire:
    def test_acquire_fresh(self, tmp_path):
        bh = _bh(tmp_path)
        r = bh.acquire('etd.pick')
        assert r.acquired is True
        assert r.reason == 'ok'
        assert r.active_count == 1

    def test_acquire_increments_active(self, tmp_path):
        bh = _bh(tmp_path)
        for i in range(3):
            r = bh.acquire('etd.pick')
            assert r.active_count == i + 1

    def test_acquire_rejects_at_capacity(self, tmp_path):
        cfg = BulkheadConfig(max_concurrent=2)
        bh = _bh(tmp_path, default_config=cfg)
        bh.acquire('etd.pick')
        bh.acquire('etd.pick')
        r = bh.acquire('etd.pick')
        assert r.acquired is False
        assert r.reason == 'capacity_exceeded'
        assert r.active_count == 2

    def test_acquire_returns_max_concurrent(self, tmp_path):
        cfg = BulkheadConfig(max_concurrent=5)
        bh = _bh(tmp_path, default_config=cfg)
        r = bh.acquire('etd.pick')
        assert r.max_concurrent == 5

    def test_acquire_increments_total_acquired(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        bh.acquire('etd.pick')
        assert bh.get_state('etd.pick').total_acquired == 2

    def test_reject_increments_total_rejected(self, tmp_path):
        cfg = BulkheadConfig(max_concurrent=1)
        bh = _bh(tmp_path, default_config=cfg)
        bh.acquire('etd.pick')
        bh.acquire('etd.pick')  # rejected
        assert bh.get_state('etd.pick').total_rejected == 1

    def test_per_skill_config_respected(self, tmp_path):
        bh = _bh(tmp_path)
        bh.set_config('etd.pick', BulkheadConfig(max_concurrent=1))
        bh.acquire('etd.pick')
        r = bh.acquire('etd.pick')
        assert r.acquired is False

    def test_node_specific_independent(self, tmp_path):
        cfg = BulkheadConfig(max_concurrent=1)
        bh = _bh(tmp_path, default_config=cfg)
        bh.acquire('etd.pick', node_id='arm-1')
        r_arm1 = bh.acquire('etd.pick', node_id='arm-1')
        r_arm2 = bh.acquire('etd.pick', node_id='arm-2')
        assert r_arm1.acquired is False
        assert r_arm2.acquired is True

    def test_different_skills_independent(self, tmp_path):
        cfg = BulkheadConfig(max_concurrent=1)
        bh = _bh(tmp_path, default_config=cfg)
        bh.acquire('etd.pick')
        r = bh.acquire('etd.weld')
        assert r.acquired is True

    def test_skill_id_in_result(self, tmp_path):
        bh = _bh(tmp_path)
        r = bh.acquire('etd.weld')
        assert r.skill_id == 'etd.weld'


# ── Bulkhead — release ────────────────────────────────────────────────────────

class TestRelease:
    def test_release_decrements(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        bh.acquire('etd.pick')
        bh.release('etd.pick')
        assert bh.get_state('etd.pick').active_count == 1

    def test_release_returns_true(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        assert bh.release('etd.pick') is True

    def test_release_increments_total_released(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        bh.release('etd.pick')
        assert bh.get_state('etd.pick').total_released == 1

    def test_release_unknown_false(self, tmp_path):
        bh = _bh(tmp_path)
        assert bh.release('ghost') is False

    def test_release_at_zero_false(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        bh.release('etd.pick')
        assert bh.release('etd.pick') is False

    def test_release_frees_capacity(self, tmp_path):
        cfg = BulkheadConfig(max_concurrent=1)
        bh = _bh(tmp_path, default_config=cfg)
        bh.acquire('etd.pick')
        bh.release('etd.pick')
        r = bh.acquire('etd.pick')
        assert r.acquired is True


# ── Bulkhead — reset ──────────────────────────────────────────────────────────

class TestReset:
    def test_reset_clears_active(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        bh.acquire('etd.pick')
        assert bh.reset('etd.pick') is True
        assert bh.get_state('etd.pick').active_count == 0

    def test_reset_unknown_false(self, tmp_path):
        bh = _bh(tmp_path)
        assert bh.reset('ghost') is False

    def test_reset_preserves_totals(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.pick')
        bh.acquire('etd.pick')
        bh.reset('etd.pick')
        s = bh.get_state('etd.pick')
        assert s.total_acquired == 2
        assert s.active_count == 0


# ── Bulkhead — misc ───────────────────────────────────────────────────────────

class TestMisc:
    def test_list_states_empty(self, tmp_path):
        assert _bh(tmp_path).list_states() == []

    def test_list_states_after_acquire(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.a')
        bh.acquire('etd.b')
        assert len(bh.list_states()) == 2

    def test_state_count(self, tmp_path):
        bh = _bh(tmp_path)
        bh.acquire('etd.a')
        bh.acquire('etd.b')
        assert bh.state_count == 2

    def test_get_config_default(self, tmp_path):
        bh = _bh(tmp_path)
        assert bh.get_config('any').max_concurrent == 10

    def test_remove_config_unknown_false(self, tmp_path):
        assert _bh(tmp_path).remove_config('ghost') is False

    def test_list_configs_empty(self, tmp_path):
        assert _bh(tmp_path).list_configs() == {}

    def test_persists_across_instances(self, tmp_path):
        bh1 = _bh(tmp_path)
        bh1.set_config('etd.pick', BulkheadConfig(max_concurrent=4))
        bh1.acquire('etd.pick')
        bh2 = _bh(tmp_path)
        assert bh2.get_config('etd.pick').max_concurrent == 4
        assert bh2.get_state('etd.pick').active_count == 1


# ── REST API /bulkhead ────────────────────────────────────────────────────────

import api.bulkhead as _bh_mod


@pytest.fixture(autouse=True)
def patch_bulkhead_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_bh_mod, '_BULKHEAD_DIR', tmp_path / 'bulkhead')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestBulkheadStatesAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/bulkhead/states')
        assert r.status_code == 200
        assert r.json()['state_count'] == 0

    def test_list_after_acquire(self, api_client):
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.get('/bulkhead/states')
        assert r.json()['state_count'] == 1

    def test_get_404(self, api_client):
        r = api_client.get('/bulkhead/states/ghost')
        assert r.status_code == 404

    def test_get_after_acquire(self, api_client):
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.get('/bulkhead/states/etd.pick')
        assert r.status_code == 200
        assert r.json()['active_count'] == 1

    def test_delete_state_200(self, api_client):
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.delete('/bulkhead/states/etd.pick')
        assert r.status_code == 200

    def test_delete_state_404(self, api_client):
        r = api_client.delete('/bulkhead/states/ghost')
        assert r.status_code == 404


class TestBulkheadAcquireAPI:
    def test_acquire_200(self, api_client):
        r = api_client.post('/bulkhead/acquire',
                            json={'skill_id': 'etd.pick'})
        assert r.status_code == 200
        assert r.json()['acquired'] is True

    def test_acquire_increments_active(self, api_client):
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        assert r.json()['active_count'] == 2

    def test_acquire_rejected_at_capacity(self, api_client):
        api_client.put('/bulkhead/configs/etd.pick',
                       json={'max_concurrent': 1})
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        assert r.json()['acquired'] is False
        assert r.json()['reason'] == 'capacity_exceeded'


class TestBulkheadReleaseAPI:
    def test_release_200(self, api_client):
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.post('/bulkhead/release', json={'skill_id': 'etd.pick'})
        assert r.status_code == 200
        assert r.json()['released'] is True

    def test_release_nothing_false(self, api_client):
        r = api_client.post('/bulkhead/release', json={'skill_id': 'etd.pick'})
        assert r.json()['released'] is False

    def test_release_frees_capacity(self, api_client):
        api_client.put('/bulkhead/configs/etd.pick', json={'max_concurrent': 1})
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        api_client.post('/bulkhead/release', json={'skill_id': 'etd.pick'})
        r = api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        assert r.json()['acquired'] is True


class TestBulkheadResetAPI:
    def test_reset_404(self, api_client):
        r = api_client.post('/bulkhead/reset/ghost')
        assert r.status_code == 404

    def test_reset_200(self, api_client):
        api_client.post('/bulkhead/acquire', json={'skill_id': 'etd.pick'})
        r = api_client.post('/bulkhead/reset/etd.pick')
        assert r.status_code == 200
        assert r.json()['active_count'] == 0


class TestBulkheadConfigAPI:
    def test_get_default_config(self, api_client):
        r = api_client.get('/bulkhead/config')
        assert r.status_code == 200
        assert r.json()['max_concurrent'] == 10

    def test_list_configs_empty(self, api_client):
        r = api_client.get('/bulkhead/configs')
        assert r.status_code == 200
        assert r.json()['config_count'] == 0

    def test_set_config_201(self, api_client):
        r = api_client.put('/bulkhead/configs/etd.pick',
                           json={'max_concurrent': 3})
        assert r.status_code == 201

    def test_set_config_200_on_update(self, api_client):
        api_client.put('/bulkhead/configs/etd.pick', json={'max_concurrent': 3})
        r = api_client.put('/bulkhead/configs/etd.pick', json={'max_concurrent': 5})
        assert r.status_code == 200

    def test_set_config_422_invalid(self, api_client):
        r = api_client.put('/bulkhead/configs/etd.pick',
                           json={'max_concurrent': 0})
        assert r.status_code == 422

    def test_delete_config_200(self, api_client):
        api_client.put('/bulkhead/configs/etd.pick', json={'max_concurrent': 3})
        r = api_client.delete('/bulkhead/configs/etd.pick')
        assert r.status_code == 200

    def test_delete_config_404(self, api_client):
        r = api_client.delete('/bulkhead/configs/ghost')
        assert r.status_code == 404

    def test_list_after_set(self, api_client):
        api_client.put('/bulkhead/configs/etd.pick', json={'max_concurrent': 3})
        r = api_client.get('/bulkhead/configs')
        assert r.json()['config_count'] == 1
