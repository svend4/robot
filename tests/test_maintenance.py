"""Tests for marketplace.maintenance and the /maintenance REST API."""
from __future__ import annotations

import datetime

import pytest

from marketplace.maintenance import MaintenanceWindow, MaintenanceStore


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> MaintenanceStore:
    return MaintenanceStore(tmp_path / 'maint')


# Fixed reference times for deterministic testing
_T0 = datetime.datetime(2026, 6, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
_BEFORE = _T0 - datetime.timedelta(hours=1)   # before any window
_DURING = _T0 + datetime.timedelta(hours=1)   # inside window
_AFTER  = _T0 + datetime.timedelta(hours=3)   # after window ends

_START = '2026-06-01T00:00:00+00:00'
_END   = '2026-06-01T02:00:00+00:00'


# ── MaintenanceWindow ─────────────────────────────────────────────────────────

class TestMaintenanceWindow:
    def test_defaults(self):
        w = MaintenanceWindow(window_id='w1', skill_id='etd.pick',
                              start_at=_START, end_at=_END)
        assert w.reason == ''
        assert w.node_id is None
        assert w.created_by == 'system'
        assert w.created_at

    def test_round_trip(self):
        w = MaintenanceWindow(window_id='w1', skill_id='etd.pick',
                              start_at=_START, end_at=_END,
                              reason='upgrade', node_id='r1', created_by='ops')
        w2 = MaintenanceWindow.from_dict(w.to_dict())
        assert w2.window_id == 'w1'
        assert w2.skill_id == 'etd.pick'
        assert w2.reason == 'upgrade'
        assert w2.node_id == 'r1'
        assert w2.created_by == 'ops'

    def test_to_dict_keys(self):
        keys = set(MaintenanceWindow(
            window_id='x', skill_id='s', start_at=_START, end_at=_END,
        ).to_dict())
        assert {'window_id', 'skill_id', 'start_at', 'end_at', 'reason',
                'node_id', 'created_by', 'created_at'} <= keys

    def test_from_dict_defaults(self):
        w = MaintenanceWindow.from_dict({
            'window_id': 'x', 'skill_id': 's',
            'start_at': _START, 'end_at': _END,
        })
        assert w.reason == ''
        assert w.node_id is None

    def test_is_active_before(self):
        w = MaintenanceWindow(window_id='w', skill_id='s', start_at=_START, end_at=_END)
        assert w.is_active(_BEFORE) is False

    def test_is_active_during(self):
        w = MaintenanceWindow(window_id='w', skill_id='s', start_at=_START, end_at=_END)
        assert w.is_active(_DURING) is True

    def test_is_active_at_start(self):
        w = MaintenanceWindow(window_id='w', skill_id='s', start_at=_START, end_at=_END)
        assert w.is_active(_T0) is True

    def test_is_active_at_end(self):
        end = datetime.datetime(2026, 6, 1, 2, 0, 0, tzinfo=datetime.timezone.utc)
        w = MaintenanceWindow(window_id='w', skill_id='s', start_at=_START, end_at=_END)
        assert w.is_active(end) is False   # half-open [start, end)

    def test_is_active_after(self):
        w = MaintenanceWindow(window_id='w', skill_id='s', start_at=_START, end_at=_END)
        assert w.is_active(_AFTER) is False


# ── MaintenanceStore — CRUD ───────────────────────────────────────────────────

class TestMaintenanceStoreCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.window_count == 0
        assert store.list_windows() == []

    def test_add_window(self, tmp_path):
        store = _store(tmp_path)
        w = store.add_window('etd.pick', _START, _END)
        assert w.skill_id == 'etd.pick'
        assert w.window_id

    def test_add_with_all_fields(self, tmp_path):
        store = _store(tmp_path)
        w = store.add_window('etd.pick', _START, _END, reason='upgrade',
                             node_id='r1', created_by='ops')
        assert w.reason == 'upgrade'
        assert w.node_id == 'r1'
        assert w.created_by == 'ops'

    def test_add_invalid_end_before_start(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).add_window('etd.pick', _END, _START)

    def test_add_invalid_end_equals_start(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).add_window('etd.pick', _START, _START)

    def test_get_window(self, tmp_path):
        store = _store(tmp_path)
        w = store.add_window('etd.pick', _START, _END)
        assert store.get_window(w.window_id) is not None

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get_window('ghost') is None

    def test_remove_existing(self, tmp_path):
        store = _store(tmp_path)
        w = store.add_window('etd.pick', _START, _END)
        assert store.remove_window(w.window_id) is True
        assert store.get_window(w.window_id) is None

    def test_remove_unknown_false(self, tmp_path):
        assert _store(tmp_path).remove_window('ghost') is False

    def test_window_count(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        store.add_window('etd.weld', _START, _END)
        assert store.window_count == 2

    def test_list_all(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        store.add_window('etd.weld', _START, _END)
        assert len(store.list_windows()) == 2

    def test_list_filtered(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        store.add_window('etd.weld', _START, _END)
        results = store.list_windows(skill_id='etd.pick')
        assert len(results) == 1
        assert results[0].skill_id == 'etd.pick'

    def test_list_active_only(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        past_end = '2026-01-01T00:00:00+00:00'
        past_start = '2025-01-01T00:00:00+00:00'
        store.add_window('etd.weld', past_start, past_end)
        results = store.list_windows(active_only=True, _now=_DURING)
        assert len(results) == 1
        assert results[0].skill_id == 'etd.pick'

    def test_active_windows(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        assert len(store.active_windows(_now=_DURING)) == 1
        assert len(store.active_windows(_now=_AFTER)) == 0


# ── MaintenanceStore — is_in_maintenance ────────────────────────────────────

class TestIsInMaintenance:
    def test_false_when_no_windows(self, tmp_path):
        assert _store(tmp_path).is_in_maintenance('etd.pick') is False

    def test_false_before_window(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        assert store.is_in_maintenance('etd.pick', _now=_BEFORE) is False

    def test_true_during_window(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        assert store.is_in_maintenance('etd.pick', _now=_DURING) is True

    def test_false_after_window(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        assert store.is_in_maintenance('etd.pick', _now=_AFTER) is False

    def test_false_different_skill(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        assert store.is_in_maintenance('etd.weld', _now=_DURING) is False

    def test_global_wildcard_matches_any_skill(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('*', _START, _END)
        assert store.is_in_maintenance('etd.pick', _now=_DURING) is True
        assert store.is_in_maintenance('etd.weld', _now=_DURING) is True

    def test_node_specific_matches(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END, node_id='r1')
        assert store.is_in_maintenance('etd.pick', node_id='r1', _now=_DURING) is True

    def test_node_specific_no_match_other_node(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END, node_id='r1')
        assert store.is_in_maintenance('etd.pick', node_id='r2', _now=_DURING) is False

    def test_no_node_window_matches_any_node(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)
        assert store.is_in_maintenance('etd.pick', node_id='r1', _now=_DURING) is True

    def test_no_node_arg_matches_node_none_window(self, tmp_path):
        store = _store(tmp_path)
        store.add_window('etd.pick', _START, _END)  # node_id=None
        assert store.is_in_maintenance('etd.pick', _now=_DURING) is True

    def test_multiple_windows_any_match(self, tmp_path):
        store = _store(tmp_path)
        past = '2025-01-01T00:00:00+00:00'
        past_end = '2025-06-01T00:00:00+00:00'
        store.add_window('etd.pick', past, past_end)      # expired
        store.add_window('etd.pick', _START, _END)        # active
        assert store.is_in_maintenance('etd.pick', _now=_DURING) is True


# ── Persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_persists_windows(self, tmp_path):
        p = tmp_path / 'maint'
        w = MaintenanceStore(p).add_window('etd.pick', _START, _END, reason='fw')
        s2 = MaintenanceStore(p)
        w2 = s2.get_window(w.window_id)
        assert w2 is not None
        assert w2.reason == 'fw'

    def test_creates_dir(self, tmp_path):
        s = MaintenanceStore(tmp_path / 'a' / 'b')
        s.add_window('etd.pick', _START, _END)
        assert (tmp_path / 'a' / 'b' / 'maintenance.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'maintenance.json').write_text('bad json')
        s = MaintenanceStore(tmp_path)
        assert s.window_count == 0


# ── REST API ──────────────────────────────────────────────────────────────────

import api.maintenance as _maint_mod


@pytest.fixture(autouse=True)
def patch_maint_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_maint_mod, '_MAINTENANCE_DIR', tmp_path / 'maint')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _add(api_client, skill_id='etd.pick', start_at=_START, end_at=_END,
         reason='', node_id=None):
    return api_client.post('/maintenance', json={
        'skill_id': skill_id, 'start_at': start_at, 'end_at': end_at,
        'reason': reason, 'node_id': node_id,
    })


class TestMaintenanceAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/maintenance')
        assert r.status_code == 200
        assert r.json()['window_count'] == 0

    def test_add_201(self, api_client):
        assert _add(api_client).status_code == 201

    def test_add_has_window_id(self, api_client):
        assert 'window_id' in _add(api_client).json()

    def test_add_has_skill_id(self, api_client):
        assert _add(api_client).json()['skill_id'] == 'etd.pick'

    def test_add_invalid_422(self, api_client):
        r = api_client.post('/maintenance', json={
            'skill_id': 'etd.pick', 'start_at': _END, 'end_at': _START,
        })
        assert r.status_code == 422

    def test_list_after_add(self, api_client):
        _add(api_client)
        _add(api_client, skill_id='etd.weld')
        assert api_client.get('/maintenance').json()['window_count'] == 2

    def test_list_filter_skill(self, api_client):
        _add(api_client, skill_id='etd.pick')
        _add(api_client, skill_id='etd.weld')
        r = api_client.get('/maintenance?skill_id=etd.pick')
        assert r.json()['window_count'] == 1

    def test_get_found(self, api_client):
        wid = _add(api_client).json()['window_id']
        r = api_client.get(f'/maintenance/{wid}')
        assert r.status_code == 200
        assert r.json()['window_id'] == wid

    def test_get_404(self, api_client):
        assert api_client.get('/maintenance/ghost').status_code == 404

    def test_check_not_in_maintenance(self, api_client):
        r = api_client.get('/maintenance/check?skill_id=etd.pick')
        assert r.status_code == 200
        assert r.json()['in_maintenance'] is False

    def test_delete_200(self, api_client):
        wid = _add(api_client).json()['window_id']
        assert api_client.delete(f'/maintenance/{wid}').status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/maintenance/ghost').status_code == 404

    def test_delete_removes_window(self, api_client):
        wid = _add(api_client).json()['window_id']
        api_client.delete(f'/maintenance/{wid}')
        assert api_client.get(f'/maintenance/{wid}').status_code == 404
