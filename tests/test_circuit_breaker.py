"""Tests for marketplace.circuit_breaker and the /circuit REST API."""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from marketplace.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerStore,
    _make_key,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _ago(seconds: int) -> datetime.datetime:
    return _now() - datetime.timedelta(seconds=seconds)


def _future(seconds: int) -> datetime.datetime:
    return _now() + datetime.timedelta(seconds=seconds)


def _cb(tmp_path, config=None) -> CircuitBreaker:
    return CircuitBreaker(data_dir=tmp_path / 'circuits', config=config)


# ── _make_key ─────────────────────────────────────────────────────────────────

class TestMakeKey:
    def test_wildcard_node(self):
        assert _make_key('etd.pick', '*') == 'etd.pick'

    def test_specific_node(self):
        assert _make_key('etd.pick', 'robot-1') == 'etd.pick:robot-1'


# ── CircuitBreakerConfig ──────────────────────────────────────────────────────

class TestCircuitBreakerConfig:
    def test_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.failure_rate_threshold == 0.5
        assert cfg.min_executions == 3
        assert cfg.reset_timeout_seconds == 60
        assert cfg.half_open_max_calls == 2

    def test_round_trip(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=3, failure_rate_threshold=0.4,
            min_executions=5, reset_timeout_seconds=30, half_open_max_calls=1,
        )
        cfg2 = CircuitBreakerConfig.from_dict(cfg.to_dict())
        assert cfg2.failure_threshold == 3
        assert cfg2.failure_rate_threshold == 0.4
        assert cfg2.reset_timeout_seconds == 30
        assert cfg2.half_open_max_calls == 1

    def test_from_dict_defaults(self):
        cfg = CircuitBreakerConfig.from_dict({})
        assert cfg.failure_threshold == 5

    def test_to_dict_keys(self):
        keys = set(CircuitBreakerConfig().to_dict())
        assert keys == {'failure_threshold', 'failure_rate_threshold',
                        'min_executions', 'reset_timeout_seconds',
                        'half_open_max_calls'}


# ── CircuitBreakerState ───────────────────────────────────────────────────────

class TestCircuitBreakerState:
    def test_defaults(self):
        s = CircuitBreakerState(key='k', skill_id='etd.pick', node_id='*')
        assert s.state == 'closed'
        assert s.failure_count == 0
        assert s.total_calls == 0
        assert s.failure_rate == 0.0

    def test_failure_rate(self):
        s = CircuitBreakerState(key='k', skill_id='etd.pick', node_id='*',
                                failure_count=3, total_calls=10)
        assert s.failure_rate == 0.3

    def test_failure_rate_zero_calls(self):
        s = CircuitBreakerState(key='k', skill_id='etd.pick', node_id='*')
        assert s.failure_rate == 0.0

    def test_round_trip(self):
        s = CircuitBreakerState(
            key='etd.pick', skill_id='etd.pick', node_id='*',
            state='open', failure_count=5, success_count=2,
            half_open_successes=0, total_calls=7,
            opened_at='2025-01-01T00:00:00+00:00',
            last_failure_at='2025-01-01T00:00:01+00:00',
        )
        s2 = CircuitBreakerState.from_dict(s.to_dict())
        assert s2.state == 'open'
        assert s2.failure_count == 5
        assert s2.opened_at == '2025-01-01T00:00:00+00:00'

    def test_to_dict_keys(self):
        s = CircuitBreakerState(key='k', skill_id='x', node_id='*')
        keys = set(s.to_dict())
        assert {'key', 'skill_id', 'node_id', 'state', 'failure_count',
                'success_count', 'total_calls', 'opened_at'} <= keys


# ── CircuitBreakerStore ───────────────────────────────────────────────────────

class TestCircuitBreakerStore:
    @pytest.fixture()
    def store(self, tmp_path) -> CircuitBreakerStore:
        return CircuitBreakerStore(tmp_path / 'circuits')

    def test_empty(self, store):
        assert store.breaker_count == 0

    def test_get_or_create(self, store):
        s = store.get_or_create('etd.pick')
        assert s.state == 'closed'
        assert s.skill_id == 'etd.pick'

    def test_save_and_get(self, store):
        s = store.get_or_create('etd.pick')
        s.failure_count = 3
        store.save(s)
        s2 = store.get('etd.pick')
        assert s2 is not None
        assert s2.failure_count == 3

    def test_get_unknown_none(self, store):
        assert store.get('ghost') is None

    def test_remove_existing(self, store):
        store.get_or_create('etd.pick')
        store.save(store.get_or_create('etd.pick'))
        assert store.remove('etd.pick') is True
        assert store.get('etd.pick') is None

    def test_remove_unknown_false(self, store):
        assert store.remove('ghost') is False

    def test_list_states(self, store):
        store.save(store.get_or_create('etd.a'))
        store.save(store.get_or_create('etd.b'))
        assert len(store.list_states()) == 2

    def test_persists(self, tmp_path):
        p = tmp_path / 'circuits'
        s1 = CircuitBreakerStore(p)
        state = s1.get_or_create('etd.pick')
        state.failure_count = 7
        s1.save(state)
        s2 = CircuitBreakerStore(p)
        assert s2.get('etd.pick').failure_count == 7

    def test_corrupt_loads_empty(self, tmp_path):
        p = tmp_path
        (p / 'circuits.json').write_text('bad')
        s = CircuitBreakerStore(p)
        assert s.breaker_count == 0


# ── CircuitBreaker — closed state ─────────────────────────────────────────────

class TestClosedState:
    def test_allow_on_fresh_circuit(self, tmp_path):
        cb = _cb(tmp_path)
        r = cb.allow_execution('etd.pick')
        assert r.allowed is True
        assert r.state == 'closed'
        assert r.reason == 'ok'

    def test_failures_below_threshold_stay_closed(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=5, min_executions=10)
        cb = _cb(tmp_path, cfg)
        for _ in range(4):
            cb.record_failure('etd.pick')
        assert cb.get_state('etd.pick').state == 'closed'

    def test_opens_at_failure_threshold(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=3, min_executions=10)
        cb = _cb(tmp_path, cfg)
        for _ in range(3):
            cb.record_failure('etd.pick')
        assert cb.get_state('etd.pick').state == 'open'

    def test_opens_by_failure_rate(self, tmp_path):
        cfg = CircuitBreakerConfig(
            failure_threshold=100,   # high threshold so count won't trigger
            failure_rate_threshold=0.5,
            min_executions=4,
        )
        cb = _cb(tmp_path, cfg)
        for _ in range(2):
            cb.record_success('etd.pick')
        for _ in range(2):
            cb.record_failure('etd.pick')
        assert cb.get_state('etd.pick').state == 'open'

    def test_rate_check_skipped_below_min_executions(self, tmp_path):
        cfg = CircuitBreakerConfig(
            failure_threshold=100,
            failure_rate_threshold=0.1,  # would fire at 10% if min met
            min_executions=10,
        )
        cb = _cb(tmp_path, cfg)
        cb.record_success('etd.pick')
        cb.record_failure('etd.pick')  # 50% rate but only 2 calls
        assert cb.get_state('etd.pick').state == 'closed'

    def test_success_increments_counts(self, tmp_path):
        cb = _cb(tmp_path)
        cb.record_success('etd.pick')
        s = cb.get_state('etd.pick')
        assert s.success_count == 1
        assert s.total_calls == 1
        assert s.last_success_at is not None

    def test_failure_increments_counts(self, tmp_path):
        cb = _cb(tmp_path)
        cb.record_failure('etd.pick')
        s = cb.get_state('etd.pick')
        assert s.failure_count == 1
        assert s.total_calls == 1
        assert s.last_failure_at is not None


# ── CircuitBreaker — open state ───────────────────────────────────────────────

class TestOpenState:
    def test_rejects_when_open(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        r = cb.allow_execution('etd.pick')
        assert r.allowed is False
        assert r.reason == 'open'
        assert r.state == 'open'

    def test_opened_at_set(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        assert cb.get_state('etd.pick').opened_at is not None

    def test_transitions_to_half_open_after_timeout(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1, reset_timeout_seconds=10)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        # Simulate timeout elapsed by passing a future _now
        r = cb.allow_execution('etd.pick', _now=_future(11))
        assert r.state == 'half_open'
        assert r.allowed is True

    def test_stays_open_before_timeout(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1, reset_timeout_seconds=60)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        r = cb.allow_execution('etd.pick', _now=_future(30))
        assert r.state == 'open'
        assert r.allowed is False

    def test_node_specific_circuit(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick', node_id='arm-1')
        r_arm1 = cb.allow_execution('etd.pick', node_id='arm-1')
        r_arm2 = cb.allow_execution('etd.pick', node_id='arm-2')
        assert r_arm1.allowed is False
        assert r_arm2.allowed is True


# ── CircuitBreaker — half_open state ─────────────────────────────────────────

class TestHalfOpenState:
    def _open_and_advance(self, tmp_path, half_open_max=2):
        cfg = CircuitBreakerConfig(
            failure_threshold=1, reset_timeout_seconds=10,
            half_open_max_calls=half_open_max,
        )
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        # Advance time past timeout
        cb.allow_execution('etd.pick', _now=_future(11))
        return cb

    def test_closes_after_enough_successes(self, tmp_path):
        cb = self._open_and_advance(tmp_path, half_open_max=2)
        cb.record_success('etd.pick')
        cb.record_success('etd.pick')
        assert cb.get_state('etd.pick').state == 'closed'

    def test_reopens_on_failure(self, tmp_path):
        cb = self._open_and_advance(tmp_path)
        cb.record_failure('etd.pick')
        assert cb.get_state('etd.pick').state == 'open'

    def test_quota_exceeded_blocks(self, tmp_path):
        cfg = CircuitBreakerConfig(
            failure_threshold=1, reset_timeout_seconds=10,
            half_open_max_calls=1,
        )
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        # Enter half_open; first call allowed, second blocked
        r1 = cb.allow_execution('etd.pick', _now=_future(11))
        r2 = cb.allow_execution('etd.pick', _now=_future(11))
        assert r1.allowed is True
        assert r2.allowed is False
        assert r2.reason == 'half_open_quota_exceeded'

    def test_remaining_half_open_decrements(self, tmp_path):
        cfg = CircuitBreakerConfig(
            failure_threshold=1, reset_timeout_seconds=10,
            half_open_max_calls=3,
        )
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        r = cb.allow_execution('etd.pick', _now=_future(11))
        assert r.remaining_half_open == 3

    def test_failure_count_reset_on_close(self, tmp_path):
        cb = self._open_and_advance(tmp_path, half_open_max=2)
        cb.record_success('etd.pick')
        cb.record_success('etd.pick')
        s = cb.get_state('etd.pick')
        assert s.state == 'closed'
        assert s.failure_count == 0
        assert s.opened_at is None


# ── CircuitBreaker — reset ────────────────────────────────────────────────────

class TestReset:
    def test_reset_open_to_closed(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        assert cb.get_state('etd.pick').state == 'open'
        assert cb.reset('etd.pick') is True
        assert cb.get_state('etd.pick').state == 'closed'

    def test_reset_clears_failure_count(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        cb.reset('etd.pick')
        s = cb.get_state('etd.pick')
        assert s.failure_count == 0
        assert s.opened_at is None

    def test_reset_unknown_returns_false(self, tmp_path):
        cb = _cb(tmp_path)
        assert cb.reset('ghost') is False

    def test_reset_sets_last_state_change(self, tmp_path):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = _cb(tmp_path, cfg)
        cb.record_failure('etd.pick')
        cb.reset('etd.pick')
        assert cb.get_state('etd.pick').last_state_change_at is not None


# ── CircuitBreaker — misc ─────────────────────────────────────────────────────

class TestMisc:
    def test_list_breakers_empty(self, tmp_path):
        cb = _cb(tmp_path)
        assert cb.list_breakers() == []

    def test_list_breakers_after_activity(self, tmp_path):
        cb = _cb(tmp_path)
        cb.record_success('etd.pick')
        cb.record_failure('etd.weld')
        assert len(cb.list_breakers()) == 2

    def test_remove_existing(self, tmp_path):
        cb = _cb(tmp_path)
        cb.record_success('etd.pick')
        assert cb.remove('etd.pick') is True
        assert cb.get_state('etd.pick') is None

    def test_remove_unknown_false(self, tmp_path):
        assert _cb(tmp_path).remove('ghost') is False

    def test_breaker_count(self, tmp_path):
        cb = _cb(tmp_path)
        cb.record_success('etd.a')
        cb.record_success('etd.b')
        assert cb.breaker_count == 2

    def test_set_per_skill_config(self, tmp_path):
        cb = _cb(tmp_path)
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb.set_config('etd.pick', cfg)
        assert cb.get_config('etd.pick').failure_threshold == 1

    def test_default_config_unaffected(self, tmp_path):
        cb = _cb(tmp_path)
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb.set_config('etd.pick', cfg)
        assert cb.get_config('etd.weld').failure_threshold == 5  # default

    def test_persists_across_instances(self, tmp_path):
        cb1 = _cb(tmp_path)
        for _ in range(5):
            cb1.record_failure('etd.pick')
        cb2 = _cb(tmp_path)
        assert cb2.get_state('etd.pick').state == 'open'


# ── REST API /circuit ─────────────────────────────────────────────────────────

import api.circuit_breaker as _cb_mod


@pytest.fixture(autouse=True)
def patch_circuit_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_cb_mod, '_CIRCUIT_DIR', tmp_path / 'circuits')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestCircuitListAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/circuit/breakers')
        assert r.status_code == 200
        assert r.json()['breaker_count'] == 0

    def test_list_after_failure(self, api_client):
        api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        r = api_client.get('/circuit/breakers')
        assert r.json()['breaker_count'] == 1


class TestCircuitGetAPI:
    def test_get_creates_closed(self, api_client):
        r = api_client.get('/circuit/breakers/etd.pick')
        assert r.status_code == 200
        assert r.json()['state'] == 'closed'

    def test_get_shows_current_state(self, api_client):
        for _ in range(5):
            api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        r = api_client.get('/circuit/breakers/etd.pick')
        assert r.json()['state'] == 'open'


class TestCircuitDeleteAPI:
    def test_delete_existing(self, api_client):
        api_client.post('/circuit/success', json={'skill_id': 'etd.pick'})
        r = api_client.delete('/circuit/breakers/etd.pick')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        r = api_client.delete('/circuit/breakers/ghost')
        assert r.status_code == 404


class TestCircuitCheckAPI:
    def test_check_allows_fresh(self, api_client):
        r = api_client.post('/circuit/check', json={'skill_id': 'etd.pick'})
        assert r.status_code == 200
        assert r.json()['allowed'] is True

    def test_check_rejects_open(self, api_client):
        for _ in range(5):
            api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        r = api_client.post('/circuit/check', json={'skill_id': 'etd.pick'})
        assert r.json()['allowed'] is False
        assert r.json()['state'] == 'open'

    def test_check_has_skill_id(self, api_client):
        r = api_client.post('/circuit/check', json={'skill_id': 'etd.weld'})
        assert r.json()['skill_id'] == 'etd.weld'


class TestCircuitSuccessAPI:
    def test_success_200(self, api_client):
        r = api_client.post('/circuit/success', json={'skill_id': 'etd.pick'})
        assert r.status_code == 200

    def test_success_increments(self, api_client):
        api_client.post('/circuit/success', json={'skill_id': 'etd.pick'})
        api_client.post('/circuit/success', json={'skill_id': 'etd.pick'})
        r = api_client.get('/circuit/breakers/etd.pick')
        assert r.json()['success_count'] == 2


class TestCircuitFailureAPI:
    def test_failure_200(self, api_client):
        r = api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        assert r.status_code == 200

    def test_opens_after_threshold(self, api_client):
        for _ in range(5):
            api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        r = api_client.get('/circuit/breakers/etd.pick')
        assert r.json()['state'] == 'open'

    def test_failure_count_in_response(self, api_client):
        for _ in range(3):
            r = api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        assert r.json()['failure_count'] == 3


class TestCircuitResetAPI:
    def test_reset_404(self, api_client):
        r = api_client.post('/circuit/reset/ghost')
        assert r.status_code == 404

    def test_reset_open_to_closed(self, api_client):
        for _ in range(5):
            api_client.post('/circuit/failure', json={'skill_id': 'etd.pick'})
        r = api_client.post('/circuit/reset/etd.pick')
        assert r.status_code == 200
        assert r.json()['state'] == 'closed'


class TestCircuitConfigAPI:
    def test_get_default_config(self, api_client):
        r = api_client.get('/circuit/config')
        assert r.status_code == 200
        data = r.json()
        assert data['failure_threshold'] == 5
        assert data['reset_timeout_seconds'] == 60

    def test_set_skill_config(self, api_client):
        r = api_client.put('/circuit/config/etd.pick', json={
            'failure_threshold': 2,
            'failure_rate_threshold': 0.3,
            'min_executions': 5,
            'reset_timeout_seconds': 30,
            'half_open_max_calls': 1,
        })
        assert r.status_code == 200
        data = r.json()
        assert data['skill_id'] == 'etd.pick'
        assert data['config']['failure_threshold'] == 2
