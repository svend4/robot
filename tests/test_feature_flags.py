"""Tests for marketplace.feature_flags and the /flags REST API."""
from __future__ import annotations

import pytest

from marketplace.feature_flags import FlagEntry, FeatureFlagStore, _make_key


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> FeatureFlagStore:
    return FeatureFlagStore(tmp_path / 'flags')


# ── _make_key ─────────────────────────────────────────────────────────────────

class TestMakeKey:
    def test_no_node(self):
        assert _make_key('etd.pick', 'ff', None) == 'etd.pick::ff::'

    def test_with_node(self):
        assert _make_key('etd.pick', 'ff', 'robot-01') == 'etd.pick::ff::robot-01'

    def test_global(self):
        assert _make_key('*', 'ff', None) == '*::ff::'


# ── FlagEntry ─────────────────────────────────────────────────────────────────

class TestFlagEntry:
    def test_defaults(self):
        e = FlagEntry(skill_id='etd.pick', flag_key='ff', enabled=True)
        assert e.node_id is None
        assert e.description == ''
        assert e.created_at
        assert e.updated_at

    def test_round_trip(self):
        e = FlagEntry(skill_id='etd.pick', flag_key='force_fb', enabled=False,
                      node_id='r1', description='test flag')
        e2 = FlagEntry.from_dict(e.to_dict())
        assert e2.skill_id == 'etd.pick'
        assert e2.flag_key == 'force_fb'
        assert e2.enabled is False
        assert e2.node_id == 'r1'
        assert e2.description == 'test flag'

    def test_to_dict_keys(self):
        keys = set(FlagEntry(skill_id='s', flag_key='k', enabled=True).to_dict())
        assert {'skill_id', 'flag_key', 'enabled', 'node_id',
                'description', 'created_at', 'updated_at'} <= keys

    def test_from_dict_defaults(self):
        e = FlagEntry.from_dict({'skill_id': 's', 'flag_key': 'k', 'enabled': True})
        assert e.node_id is None
        assert e.description == ''


# ── FeatureFlagStore — CRUD ───────────────────────────────────────────────────

class TestFlagStoreCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.flag_count == 0
        assert store.list_flags() == []

    def test_set_creates(self, tmp_path):
        store = _store(tmp_path)
        entry, created = store.set_flag('etd.pick', 'ff', True)
        assert created is True
        assert entry.enabled is True

    def test_set_updates(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        entry, created = store.set_flag('etd.pick', 'ff', False)
        assert created is False
        assert entry.enabled is False

    def test_set_updates_description(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True, description='first')
        entry, _ = store.set_flag('etd.pick', 'ff', True, description='second')
        assert entry.description == 'second'

    def test_set_empty_description_preserves(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True, description='keep')
        entry, _ = store.set_flag('etd.pick', 'ff', False)
        assert entry.description == 'keep'

    def test_get_exact(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        assert store.get_flag('etd.pick', 'ff') is not None

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get_flag('etd.pick', 'ghost') is None

    def test_get_with_node(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True, node_id='r1')
        assert store.get_flag('etd.pick', 'ff', node_id='r1') is not None
        assert store.get_flag('etd.pick', 'ff') is None

    def test_remove_existing(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        assert store.remove_flag('etd.pick', 'ff') is True
        assert store.get_flag('etd.pick', 'ff') is None

    def test_remove_unknown_false(self, tmp_path):
        assert _store(tmp_path).remove_flag('etd.pick', 'ghost') is False

    def test_remove_node_specific(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True, node_id='r1')
        assert store.remove_flag('etd.pick', 'ff', node_id='r1') is True

    def test_flag_count(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff1', True)
        store.set_flag('etd.pick', 'ff2', False)
        assert store.flag_count == 2

    def test_list_all(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff1', True)
        store.set_flag('etd.weld', 'ff1', False)
        assert len(store.list_flags()) == 2

    def test_list_filtered(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff1', True)
        store.set_flag('etd.weld', 'ff1', False)
        results = store.list_flags(skill_id='etd.pick')
        assert len(results) == 1
        assert results[0].skill_id == 'etd.pick'

    def test_list_filtered_empty(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        assert store.list_flags(skill_id='etd.unknown') == []


# ── FeatureFlagStore — resolution ────────────────────────────────────────────

class TestResolution:
    def test_default_false_when_absent(self, tmp_path):
        assert _store(tmp_path).is_enabled('etd.pick', 'ff') is False

    def test_skill_wide_enabled(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        assert store.is_enabled('etd.pick', 'ff') is True

    def test_global_fallback(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff', True)
        assert store.is_enabled('etd.pick', 'ff') is True

    def test_skill_overrides_global(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff', True)
        store.set_flag('etd.pick', 'ff', False)
        assert store.is_enabled('etd.pick', 'ff') is False

    def test_node_overrides_skill(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        store.set_flag('etd.pick', 'ff', False, node_id='r1')
        assert store.is_enabled('etd.pick', 'ff', node_id='r1') is False

    def test_node_overrides_global(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff', True)
        store.set_flag('etd.pick', 'ff', False, node_id='r1')
        assert store.is_enabled('etd.pick', 'ff', node_id='r1') is False

    def test_skill_fallback_when_no_node_entry(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        assert store.is_enabled('etd.pick', 'ff', node_id='r1') is True

    def test_global_fallback_when_no_skill_or_node_entry(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff', True)
        assert store.is_enabled('etd.pick', 'ff', node_id='r1') is True

    def test_different_skills_independent(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        store.set_flag('etd.weld', 'ff', False)
        assert store.is_enabled('etd.pick', 'ff') is True
        assert store.is_enabled('etd.weld', 'ff') is False

    def test_global_does_not_bleed_to_other_flag(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff1', True)
        assert store.is_enabled('etd.pick', 'ff2') is False


class TestResolveSource:
    def test_default(self, tmp_path):
        assert _store(tmp_path).resolve_source('etd.pick', 'ff') == 'default'

    def test_global(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff', True)
        assert store.resolve_source('etd.pick', 'ff') == 'global'

    def test_skill(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        assert store.resolve_source('etd.pick', 'ff') == 'skill'

    def test_node(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('etd.pick', 'ff', True)
        store.set_flag('etd.pick', 'ff', False, node_id='r1')
        assert store.resolve_source('etd.pick', 'ff', node_id='r1') == 'node'

    def test_skill_wins_over_global(self, tmp_path):
        store = _store(tmp_path)
        store.set_flag('*', 'ff', True)
        store.set_flag('etd.pick', 'ff', False)
        assert store.resolve_source('etd.pick', 'ff') == 'skill'


# ── Persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_persists_flags(self, tmp_path):
        p = tmp_path / 'flags'
        FeatureFlagStore(p).set_flag('etd.pick', 'ff', True, description='saved')
        s2 = FeatureFlagStore(p)
        e = s2.get_flag('etd.pick', 'ff')
        assert e is not None
        assert e.enabled is True
        assert e.description == 'saved'

    def test_persists_node_flag(self, tmp_path):
        p = tmp_path / 'flags'
        FeatureFlagStore(p).set_flag('etd.pick', 'ff', False, node_id='r1')
        s2 = FeatureFlagStore(p)
        assert s2.get_flag('etd.pick', 'ff', node_id='r1').enabled is False

    def test_creates_dir(self, tmp_path):
        s = FeatureFlagStore(tmp_path / 'a' / 'b')
        s.set_flag('etd.pick', 'ff', True)
        assert (tmp_path / 'a' / 'b' / 'feature_flags.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'feature_flags.json').write_text('not json')
        s = FeatureFlagStore(tmp_path)
        assert s.flag_count == 0


# ── REST API ──────────────────────────────────────────────────────────────────

import api.feature_flags as _flags_mod


@pytest.fixture(autouse=True)
def patch_flags_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_flags_mod, '_FLAGS_DIR', tmp_path / 'flags')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _set(api_client, skill_id='etd.pick', flag_key='ff', enabled=True,
         node_id=None, description=''):
    return api_client.post('/flags', json={
        'skill_id': skill_id, 'flag_key': flag_key, 'enabled': enabled,
        'node_id': node_id, 'description': description,
    })


class TestFlagsAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/flags')
        assert r.status_code == 200
        assert r.json()['flag_count'] == 0

    def test_set_201(self, api_client):
        assert _set(api_client).status_code == 201

    def test_set_200_update(self, api_client):
        _set(api_client)
        assert _set(api_client, enabled=False).status_code == 200

    def test_set_has_skill_id(self, api_client):
        assert _set(api_client).json()['skill_id'] == 'etd.pick'

    def test_set_has_enabled(self, api_client):
        assert _set(api_client, enabled=False).json()['enabled'] is False

    def test_list_after_set(self, api_client):
        _set(api_client)
        _set(api_client, skill_id='etd.weld', flag_key='ff2')
        assert api_client.get('/flags').json()['flag_count'] == 2

    def test_list_filter_skill(self, api_client):
        _set(api_client, skill_id='etd.pick')
        _set(api_client, skill_id='etd.weld')
        r = api_client.get('/flags?skill_id=etd.pick')
        assert r.json()['flag_count'] == 1

    def test_get_found(self, api_client):
        _set(api_client)
        r = api_client.get('/flags/etd.pick/ff')
        assert r.status_code == 200
        assert r.json()['flag_key'] == 'ff'

    def test_get_404(self, api_client):
        assert api_client.get('/flags/etd.pick/ghost').status_code == 404

    def test_get_with_node(self, api_client):
        _set(api_client, node_id='r1')
        r = api_client.get('/flags/etd.pick/ff?node_id=r1')
        assert r.status_code == 200
        assert r.json()['node_id'] == 'r1'

    def test_resolve_default_false(self, api_client):
        r = api_client.get('/flags/resolve?skill_id=etd.pick&flag_key=ff')
        assert r.status_code == 200
        assert r.json()['enabled'] is False
        assert r.json()['resolved_from'] == 'default'

    def test_resolve_skill_wide(self, api_client):
        _set(api_client, enabled=True)
        r = api_client.get('/flags/resolve?skill_id=etd.pick&flag_key=ff')
        assert r.json()['enabled'] is True
        assert r.json()['resolved_from'] == 'skill'

    def test_resolve_global(self, api_client):
        _set(api_client, skill_id='*', enabled=True)
        r = api_client.get('/flags/resolve?skill_id=etd.pick&flag_key=ff')
        assert r.json()['enabled'] is True
        assert r.json()['resolved_from'] == 'global'

    def test_resolve_node_override(self, api_client):
        _set(api_client, enabled=True)
        _set(api_client, enabled=False, node_id='r1')
        r = api_client.get('/flags/resolve?skill_id=etd.pick&flag_key=ff&node_id=r1')
        assert r.json()['enabled'] is False
        assert r.json()['resolved_from'] == 'node'

    def test_delete_200(self, api_client):
        _set(api_client)
        r = api_client.delete('/flags/etd.pick/ff')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/flags/etd.pick/ghost').status_code == 404

    def test_delete_removes_flag(self, api_client):
        _set(api_client)
        api_client.delete('/flags/etd.pick/ff')
        assert api_client.get('/flags/etd.pick/ff').status_code == 404

    def test_delete_with_node(self, api_client):
        _set(api_client, node_id='r1')
        r = api_client.delete('/flags/etd.pick/ff?node_id=r1')
        assert r.status_code == 200
