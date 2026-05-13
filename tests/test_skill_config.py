"""Tests for marketplace.skill_config and the /config REST API."""
from __future__ import annotations

from pathlib import Path

import pytest

from marketplace.skill_config import (
    ConfigStore,
    SkillConfigEntry,
    _make_scope_key,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> ConfigStore:
    return ConfigStore(tmp_path / 'cfg')


# ── _make_scope_key ───────────────────────────────────────────────────────────

class TestMakeScopeKey:
    def test_default_scope(self):
        k = _make_scope_key('etd.pick', '*')
        assert 'etd.pick' in k
        assert '*' in k

    def test_station_scope(self):
        k = _make_scope_key('etd.pick', 'station:alpha')
        assert 'station:alpha' in k

    def test_different_scopes_differ(self):
        k1 = _make_scope_key('etd.pick', '*')
        k2 = _make_scope_key('etd.pick', 'station:alpha')
        assert k1 != k2

    def test_different_skills_differ(self):
        k1 = _make_scope_key('etd.pick', '*')
        k2 = _make_scope_key('etd.weld', '*')
        assert k1 != k2


# ── SkillConfigEntry ──────────────────────────────────────────────────────────

class TestSkillConfigEntry:
    def test_defaults(self):
        e = SkillConfigEntry(skill_id='etd.pick', scope='*',
                             values={'speed': 80})
        assert e.version == 1
        assert e.created_at
        assert e.updated_at

    def test_round_trip(self):
        e = SkillConfigEntry(skill_id='etd.pick', scope='station:alpha',
                             values={'speed': 50, 'retries': 2},
                             version=3)
        e2 = SkillConfigEntry.from_dict(e.to_dict())
        assert e2.skill_id == 'etd.pick'
        assert e2.scope == 'station:alpha'
        assert e2.values == {'speed': 50, 'retries': 2}
        assert e2.version == 3

    def test_to_dict_keys(self):
        e = SkillConfigEntry(skill_id='x', scope='*', values={})
        keys = set(e.to_dict())
        assert {'skill_id', 'scope', 'values', 'version',
                'created_at', 'updated_at'} <= keys

    def test_values_preserved_types(self):
        vals = {'a': 1, 'b': 3.14, 'c': True, 'd': 'str',
                'e': [1, 2], 'f': {'x': 1}}
        e = SkillConfigEntry(skill_id='x', scope='*', values=vals)
        e2 = SkillConfigEntry.from_dict(e.to_dict())
        assert e2.values == vals


# ── ConfigStore — CRUD ────────────────────────────────────────────────────────

class TestConfigStoreCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.entry_count == 0
        assert store.list_skills() == []

    def test_set_and_get(self, tmp_path):
        store = _store(tmp_path)
        entry = store.set('etd.pick', '*', {'speed': 80})
        assert entry.version == 1
        result = store.get('etd.pick', '*')
        assert result is not None
        assert result.values == {'speed': 80}

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get('ghost', '*') is None

    def test_set_increments_version(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80})
        e2 = store.set('etd.pick', '*', {'speed': 60})
        assert e2.version == 2

    def test_set_preserves_created_at(self, tmp_path):
        store = _store(tmp_path)
        e1 = store.set('etd.pick', '*', {'a': 1})
        e2 = store.set('etd.pick', '*', {'a': 2})
        assert e2.created_at == e1.created_at

    def test_remove_existing(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'a': 1})
        assert store.remove('etd.pick', '*') is True
        assert store.get('etd.pick', '*') is None

    def test_remove_unknown_false(self, tmp_path):
        assert _store(tmp_path).remove('ghost', '*') is False

    def test_remove_skill_removes_all_scopes(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'a': 1})
        store.set('etd.pick', 'station:alpha', {'a': 2})
        store.set('etd.pick', 'node:arm-1', {'a': 3})
        count = store.remove_skill('etd.pick')
        assert count == 3
        assert store.list_entries(skill_id='etd.pick') == []

    def test_remove_skill_zero_if_unknown(self, tmp_path):
        assert _store(tmp_path).remove_skill('ghost') == 0

    def test_remove_skill_leaves_other_skills(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'a': 1})
        store.set('etd.weld', '*', {'b': 2})
        store.remove_skill('etd.pick')
        assert store.get('etd.weld', '*') is not None

    def test_list_entries_all(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {})
        store.set('etd.pick', 'station:alpha', {})
        store.set('etd.weld', '*', {})
        assert len(store.list_entries()) == 3

    def test_list_entries_filtered(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {})
        store.set('etd.pick', 'station:alpha', {})
        store.set('etd.weld', '*', {})
        assert len(store.list_entries(skill_id='etd.pick')) == 2

    def test_list_skills(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {})
        store.set('etd.weld', '*', {})
        store.set('etd.pick', 'station:alpha', {})
        assert set(store.list_skills()) == {'etd.pick', 'etd.weld'}

    def test_entry_count(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.a', '*', {})
        store.set('etd.b', '*', {})
        assert store.entry_count == 2


# ── ConfigStore — scope helpers ───────────────────────────────────────────────

class TestScopeHelpers:
    def test_station_scope(self):
        assert ConfigStore.station_scope('alpha') == 'station:alpha'

    def test_node_scope(self):
        assert ConfigStore.node_scope('arm-1') == 'node:arm-1'

    def test_scope_default_constant(self):
        assert ConfigStore.SCOPE_DEFAULT == '*'


# ── ConfigStore — get_effective ───────────────────────────────────────────────

class TestGetEffective:
    def test_empty_returns_empty_dict(self, tmp_path):
        store = _store(tmp_path)
        assert store.get_effective('etd.pick') == {}

    def test_default_only(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80, 'retries': 3})
        effective = store.get_effective('etd.pick')
        assert effective == {'speed': 80, 'retries': 3}

    def test_station_overrides_default(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80, 'retries': 3})
        store.set('etd.pick', 'station:alpha', {'speed': 50})
        effective = store.get_effective('etd.pick', station_id='alpha')
        assert effective['speed'] == 50     # overridden
        assert effective['retries'] == 3    # inherited from default

    def test_node_overrides_station(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80})
        store.set('etd.pick', 'station:alpha', {'speed': 50})
        store.set('etd.pick', 'node:arm-1', {'speed': 30})
        effective = store.get_effective('etd.pick',
                                        station_id='alpha', node_id='arm-1')
        assert effective['speed'] == 30

    def test_node_overrides_default_without_station(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80})
        store.set('etd.pick', 'node:arm-1', {'speed': 20})
        effective = store.get_effective('etd.pick', node_id='arm-1')
        assert effective['speed'] == 20

    def test_station_id_not_matched_uses_default(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80})
        store.set('etd.pick', 'station:alpha', {'speed': 50})
        # Ask for station 'beta' — no override exists → falls back to default
        effective = store.get_effective('etd.pick', station_id='beta')
        assert effective['speed'] == 80

    def test_merge_adds_keys_from_both(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'a': 1, 'b': 2})
        store.set('etd.pick', 'station:alpha', {'c': 3})
        effective = store.get_effective('etd.pick', station_id='alpha')
        assert effective == {'a': 1, 'b': 2, 'c': 3}

    def test_no_station_no_node_returns_default(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*', {'speed': 80})
        store.set('etd.pick', 'station:alpha', {'speed': 50})
        effective = store.get_effective('etd.pick')
        assert effective['speed'] == 80

    def test_all_three_scopes(self, tmp_path):
        store = _store(tmp_path)
        store.set('etd.pick', '*',
                  {'speed': 80, 'retries': 3, 'timeout': 30})
        store.set('etd.pick', 'station:alpha',
                  {'speed': 60, 'station_zone': 'clean'})
        store.set('etd.pick', 'node:arm-7',
                  {'speed': 40, 'calibration': 'v2'})
        effective = store.get_effective('etd.pick',
                                        station_id='alpha', node_id='arm-7')
        assert effective['speed'] == 40         # node wins
        assert effective['retries'] == 3        # from default
        assert effective['timeout'] == 30       # from default
        assert effective['station_zone'] == 'clean'  # from station
        assert effective['calibration'] == 'v2'  # from node


# ── ConfigStore — persistence ─────────────────────────────────────────────────

class TestConfigStorePersistence:
    def test_persists(self, tmp_path):
        p = tmp_path / 'cfg'
        s1 = ConfigStore(p)
        s1.set('etd.pick', '*', {'speed': 80})
        s2 = ConfigStore(p)
        assert s2.get('etd.pick', '*').values == {'speed': 80}

    def test_creates_dir(self, tmp_path):
        s = ConfigStore(tmp_path / 'a' / 'b')
        s.set('x', '*', {})
        assert (tmp_path / 'a' / 'b' / 'skill_config.json').exists()

    def test_corrupt_file_loads_empty(self, tmp_path):
        (tmp_path / 'skill_config.json').write_text('bad')
        s = ConfigStore(tmp_path)
        assert s.entry_count == 0


# ── REST API /config ──────────────────────────────────────────────────────────

import api.skill_config as _cfg_mod


@pytest.fixture(autouse=True)
def patch_config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_cfg_mod, '_CONFIG_DIR', tmp_path / 'cfg')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _set(api_client, skill_id='etd.pick', scope='*', values=None):
    if values is None:
        values = {'speed': 80, 'retries': 3}
    return api_client.put(f'/config/skills/{skill_id}',
                          json={'scope': scope, 'values': values})


class TestConfigListAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/config/skills')
        assert r.status_code == 200
        assert r.json()['skill_count'] == 0

    def test_list_after_set(self, api_client):
        _set(api_client)
        r = api_client.get('/config/skills')
        assert r.json()['skill_count'] == 1
        assert 'etd.pick' in r.json()['skills']


class TestConfigGetEntriesAPI:
    def test_entries_empty(self, api_client):
        r = api_client.get('/config/skills/etd.pick')
        assert r.status_code == 200
        assert r.json()['entry_count'] == 0

    def test_entries_after_set(self, api_client):
        _set(api_client)
        _set(api_client, scope='station:alpha', values={'speed': 50})
        r = api_client.get('/config/skills/etd.pick')
        assert r.json()['entry_count'] == 2


class TestConfigSetAPI:
    def test_create_returns_201(self, api_client):
        r = _set(api_client)
        assert r.status_code == 201

    def test_update_returns_200(self, api_client):
        _set(api_client)
        r = _set(api_client, values={'speed': 60})
        assert r.status_code == 200

    def test_version_increments(self, api_client):
        _set(api_client)
        r = _set(api_client, values={'speed': 60})
        assert r.json()['version'] == 2

    def test_response_has_skill_id(self, api_client):
        r = _set(api_client)
        assert r.json()['skill_id'] == 'etd.pick'

    def test_scope_stored(self, api_client):
        _set(api_client, scope='station:beta', values={'x': 1})
        r = api_client.get('/config/skills/etd.pick/scope/station:beta')
        assert r.status_code == 200
        assert r.json()['values']['x'] == 1


class TestConfigDeleteSkillAPI:
    def test_delete_all_200(self, api_client):
        _set(api_client)
        _set(api_client, scope='station:alpha', values={})
        r = api_client.delete('/config/skills/etd.pick')
        assert r.status_code == 200
        assert r.json()['removed_count'] == 2

    def test_delete_unknown_zero(self, api_client):
        r = api_client.delete('/config/skills/ghost')
        assert r.json()['removed_count'] == 0


class TestConfigEffectiveAPI:
    def test_effective_empty(self, api_client):
        r = api_client.get('/config/skills/etd.pick/effective')
        assert r.status_code == 200
        assert r.json()['effective'] == {}

    def test_effective_default(self, api_client):
        _set(api_client, values={'speed': 80})
        r = api_client.get('/config/skills/etd.pick/effective')
        assert r.json()['effective']['speed'] == 80

    def test_effective_station_override(self, api_client):
        _set(api_client, values={'speed': 80, 'retries': 3})
        _set(api_client, scope='station:alpha', values={'speed': 50})
        r = api_client.get(
            '/config/skills/etd.pick/effective?station_id=alpha'
        )
        assert r.json()['effective']['speed'] == 50
        assert r.json()['effective']['retries'] == 3

    def test_effective_node_override(self, api_client):
        _set(api_client, values={'speed': 80})
        _set(api_client, scope='node:arm-1', values={'speed': 20})
        r = api_client.get(
            '/config/skills/etd.pick/effective?node_id=arm-1'
        )
        assert r.json()['effective']['speed'] == 20

    def test_effective_has_ids(self, api_client):
        r = api_client.get(
            '/config/skills/etd.pick/effective?station_id=alpha&node_id=arm-1'
        )
        data = r.json()
        assert data['station_id'] == 'alpha'
        assert data['node_id'] == 'arm-1'


class TestConfigScopeAPI:
    def test_get_scope_found(self, api_client):
        _set(api_client, scope='station:alpha', values={'x': 99})
        r = api_client.get('/config/skills/etd.pick/scope/station:alpha')
        assert r.status_code == 200
        assert r.json()['values']['x'] == 99

    def test_get_scope_404(self, api_client):
        r = api_client.get('/config/skills/etd.pick/scope/station:beta')
        assert r.status_code == 404

    def test_delete_scope_200(self, api_client):
        _set(api_client, scope='station:alpha', values={})
        r = api_client.delete('/config/skills/etd.pick/scope/station:alpha')
        assert r.status_code == 200

    def test_delete_scope_404(self, api_client):
        r = api_client.delete('/config/skills/etd.pick/scope/station:ghost')
        assert r.status_code == 404

    def test_delete_scope_leaves_other_scopes(self, api_client):
        _set(api_client)  # '*'
        _set(api_client, scope='station:alpha', values={})
        api_client.delete('/config/skills/etd.pick/scope/station:alpha')
        r = api_client.get('/config/skills/etd.pick')
        assert r.json()['entry_count'] == 1
