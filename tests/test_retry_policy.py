"""Tests for marketplace.retry_policy and the /retry REST API."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from marketplace.retry_policy import (
    EXPONENTIAL,
    FIXED,
    LINEAR,
    RetryConfig,
    RetryDecision,
    RetryEngine,
    RetryPolicyStore,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _engine(tmp_path, default_config=None) -> RetryEngine:
    return RetryEngine(data_dir=tmp_path / 'retry', default_config=default_config)


# ── RetryConfig ───────────────────────────────────────────────────────────────

class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.backoff == EXPONENTIAL
        assert cfg.base_delay_ms == 500
        assert cfg.max_delay_ms == 30_000
        assert cfg.jitter_ms == 100
        assert set(cfg.retryable_statuses) == {'failed', 'aborted'}

    def test_round_trip(self):
        cfg = RetryConfig(
            max_attempts=5, backoff=LINEAR, base_delay_ms=200,
            max_delay_ms=10_000, jitter_ms=50,
            retryable_statuses=['failed'],
        )
        cfg2 = RetryConfig.from_dict(cfg.to_dict())
        assert cfg2.max_attempts == 5
        assert cfg2.backoff == LINEAR
        assert cfg2.base_delay_ms == 200
        assert cfg2.jitter_ms == 50
        assert cfg2.retryable_statuses == ['failed']

    def test_from_dict_defaults(self):
        cfg = RetryConfig.from_dict({})
        assert cfg.max_attempts == 3
        assert cfg.backoff == EXPONENTIAL

    def test_to_dict_keys(self):
        keys = set(RetryConfig().to_dict())
        assert keys == {'max_attempts', 'backoff', 'base_delay_ms',
                        'max_delay_ms', 'jitter_ms', 'retryable_statuses'}

    def test_invalid_backoff_raises(self):
        with pytest.raises(ValueError):
            RetryConfig(backoff='random_walk')

    def test_max_attempts_zero_raises(self):
        with pytest.raises(ValueError):
            RetryConfig(max_attempts=0)

    def test_negative_base_delay_raises(self):
        with pytest.raises(ValueError):
            RetryConfig(base_delay_ms=-1)

    def test_is_retryable_true(self):
        cfg = RetryConfig(retryable_statuses=['failed', 'aborted'])
        assert cfg.is_retryable('failed') is True
        assert cfg.is_retryable('aborted') is True

    def test_is_retryable_false(self):
        cfg = RetryConfig(retryable_statuses=['failed'])
        assert cfg.is_retryable('success') is False
        assert cfg.is_retryable('timeout') is False


class TestDelayForAttempt:
    def _rng(self) -> random.Random:
        """Deterministic RNG with jitter=0 override."""
        rng = random.Random(42)
        return rng

    def _cfg(self, backoff, base=100, jitter=0, max_delay=100_000):
        return RetryConfig(backoff=backoff, base_delay_ms=base,
                           jitter_ms=jitter, max_delay_ms=max_delay)

    def test_first_attempt_no_delay(self):
        cfg = self._cfg(FIXED)
        assert cfg.delay_for_attempt(1) == 0

    def test_fixed_constant(self):
        cfg = self._cfg(FIXED, base=200, jitter=0)
        assert cfg.delay_for_attempt(2) == 200
        assert cfg.delay_for_attempt(3) == 200
        assert cfg.delay_for_attempt(10) == 200

    def test_linear_grows(self):
        cfg = self._cfg(LINEAR, base=100, jitter=0)
        assert cfg.delay_for_attempt(2) == 100   # 100 * 1
        assert cfg.delay_for_attempt(3) == 200   # 100 * 2
        assert cfg.delay_for_attempt(4) == 300   # 100 * 3

    def test_exponential_doubles(self):
        cfg = self._cfg(EXPONENTIAL, base=100, jitter=0)
        assert cfg.delay_for_attempt(2) == 100   # 100 * 2^0
        assert cfg.delay_for_attempt(3) == 200   # 100 * 2^1
        assert cfg.delay_for_attempt(4) == 400   # 100 * 2^2
        assert cfg.delay_for_attempt(5) == 800   # 100 * 2^3

    def test_capped_at_max_delay(self):
        cfg = self._cfg(EXPONENTIAL, base=1000, jitter=0, max_delay=500)
        assert cfg.delay_for_attempt(2) <= 500
        assert cfg.delay_for_attempt(10) <= 500

    def test_jitter_non_negative(self):
        cfg = RetryConfig(backoff=FIXED, base_delay_ms=100, jitter_ms=50)
        rng = random.Random(42)
        for _ in range(20):
            d = cfg.delay_for_attempt(2, _rng=rng)
            assert d >= 100
            assert d <= 150

    def test_jitter_zero_no_addition(self):
        cfg = self._cfg(FIXED, base=100, jitter=0)
        assert cfg.delay_for_attempt(2) == 100


# ── RetryPolicyStore ──────────────────────────────────────────────────────────

class TestRetryPolicyStore:
    @pytest.fixture()
    def store(self, tmp_path) -> RetryPolicyStore:
        return RetryPolicyStore(tmp_path / 'retry')

    def test_empty(self, store):
        assert store.policy_count == 0

    def test_set_and_get(self, store):
        cfg = RetryConfig(max_attempts=5)
        store.set('etd.pick', cfg)
        result = store.get('etd.pick')
        assert result is not None
        assert result.max_attempts == 5

    def test_get_unknown_none(self, store):
        assert store.get('ghost') is None

    def test_list_skills(self, store):
        store.set('etd.a', RetryConfig())
        store.set('etd.b', RetryConfig())
        assert set(store.list_skills()) == {'etd.a', 'etd.b'}

    def test_remove_existing(self, store):
        store.set('etd.pick', RetryConfig())
        assert store.remove('etd.pick') is True
        assert store.get('etd.pick') is None

    def test_remove_unknown_false(self, store):
        assert store.remove('ghost') is False

    def test_update_replaces(self, store):
        store.set('etd.pick', RetryConfig(max_attempts=3))
        store.set('etd.pick', RetryConfig(max_attempts=7))
        assert store.get('etd.pick').max_attempts == 7

    def test_persists(self, tmp_path):
        p = tmp_path / 'retry'
        s1 = RetryPolicyStore(p)
        s1.set('etd.pick', RetryConfig(backoff=LINEAR, max_attempts=4))
        s2 = RetryPolicyStore(p)
        cfg = s2.get('etd.pick')
        assert cfg.backoff == LINEAR
        assert cfg.max_attempts == 4

    def test_creates_dir(self, tmp_path):
        s = RetryPolicyStore(tmp_path / 'a' / 'b')
        s.set('x', RetryConfig())
        assert (tmp_path / 'a' / 'b' / 'retry_policies.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        p = tmp_path
        (p / 'retry_policies.json').write_text('bad')
        s = RetryPolicyStore(p)
        assert s.policy_count == 0


# ── RetryEngine ───────────────────────────────────────────────────────────────

class TestRetryEngineConfig:
    def test_default_config_returned_when_no_policy(self, tmp_path):
        engine = _engine(tmp_path)
        cfg = engine.get_config('etd.pick')
        assert cfg.max_attempts == 3  # default

    def test_explicit_policy_returned(self, tmp_path):
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', RetryConfig(max_attempts=10))
        assert engine.get_config('etd.pick').max_attempts == 10

    def test_remove_policy_true(self, tmp_path):
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', RetryConfig())
        assert engine.remove_policy('etd.pick') is True

    def test_remove_policy_false_unknown(self, tmp_path):
        engine = _engine(tmp_path)
        assert engine.remove_policy('ghost') is False

    def test_list_policies_empty(self, tmp_path):
        assert _engine(tmp_path).list_policies() == {}

    def test_list_policies_populated(self, tmp_path):
        engine = _engine(tmp_path)
        engine.set_policy('etd.a', RetryConfig())
        engine.set_policy('etd.b', RetryConfig())
        assert set(engine.list_policies()) == {'etd.a', 'etd.b'}

    def test_custom_default_config(self, tmp_path):
        default = RetryConfig(max_attempts=7, backoff=FIXED)
        engine = _engine(tmp_path, default_config=default)
        cfg = engine.get_config('anything')
        assert cfg.max_attempts == 7
        assert cfg.backoff == FIXED


class TestShouldRetry:
    def _rng(self):
        return random.Random(0)  # jitter reproducible

    def test_success_not_retried(self, tmp_path):
        engine = _engine(tmp_path)
        d = engine.should_retry('etd.pick', attempt=1, last_status='success')
        assert d.retry is False
        assert d.reason == 'not_retryable_status'

    def test_failed_retried(self, tmp_path):
        engine = _engine(tmp_path)
        d = engine.should_retry('etd.pick', attempt=1, last_status='failed',
                                _rng=self._rng())
        assert d.retry is True
        assert d.reason == 'ok_to_retry'

    def test_aborted_retried(self, tmp_path):
        engine = _engine(tmp_path)
        d = engine.should_retry('etd.pick', attempt=1, last_status='aborted',
                                _rng=self._rng())
        assert d.retry is True

    def test_max_attempts_reached(self, tmp_path):
        cfg = RetryConfig(max_attempts=3, jitter_ms=0)
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', cfg)
        # attempt=3 (last allowed), next would be 4 > max_attempts=3
        d = engine.should_retry('etd.pick', attempt=3, last_status='failed')
        assert d.retry is False
        assert d.reason == 'max_attempts_reached'

    def test_attempt_within_limit_retried(self, tmp_path):
        cfg = RetryConfig(max_attempts=5, jitter_ms=0)
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', cfg)
        d = engine.should_retry('etd.pick', attempt=2, last_status='failed')
        assert d.retry is True
        assert d.next_attempt == 3

    def test_attempt_and_next_attempt_fields(self, tmp_path):
        engine = _engine(tmp_path)
        d = engine.should_retry('etd.pick', attempt=2, last_status='failed',
                                _rng=self._rng())
        assert d.attempt == 2
        assert d.next_attempt == 3

    def test_max_attempts_in_result(self, tmp_path):
        cfg = RetryConfig(max_attempts=5, jitter_ms=0)
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', cfg)
        d = engine.should_retry('etd.pick', attempt=1, last_status='failed')
        assert d.max_attempts == 5

    def test_delay_zero_on_non_retry(self, tmp_path):
        engine = _engine(tmp_path)
        d = engine.should_retry('etd.pick', attempt=1, last_status='success')
        assert d.delay_ms == 0

    def test_delay_positive_on_retry(self, tmp_path):
        cfg = RetryConfig(max_attempts=3, backoff=FIXED, base_delay_ms=200,
                          jitter_ms=0)
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', cfg)
        d = engine.should_retry('etd.pick', attempt=1, last_status='failed')
        assert d.delay_ms == 200

    def test_exponential_delay_grows(self, tmp_path):
        cfg = RetryConfig(max_attempts=5, backoff=EXPONENTIAL, base_delay_ms=100,
                          jitter_ms=0)
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', cfg)
        d2 = engine.should_retry('etd.pick', attempt=1, last_status='failed')
        d3 = engine.should_retry('etd.pick', attempt=2, last_status='failed')
        assert d3.delay_ms > d2.delay_ms

    def test_custom_retryable_statuses(self, tmp_path):
        cfg = RetryConfig(retryable_statuses=['timeout'], max_attempts=3)
        engine = _engine(tmp_path)
        engine.set_policy('etd.pick', cfg)
        assert engine.should_retry('etd.pick', 1, 'timeout').retry is True
        assert engine.should_retry('etd.pick', 1, 'failed').retry is False

    def test_to_dict_keys(self, tmp_path):
        engine = _engine(tmp_path)
        d = engine.should_retry('etd.pick', 1, 'failed', _rng=self._rng())
        keys = set(d.to_dict())
        assert {'retry', 'reason', 'attempt', 'next_attempt',
                'delay_ms', 'max_attempts'} <= keys


# ── REST API /retry ───────────────────────────────────────────────────────────

import api.retry_policy as _retry_mod


@pytest.fixture(autouse=True)
def patch_retry_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_retry_mod, '_RETRY_DIR', tmp_path / 'retry')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _set_policy(api_client, skill_id='etd.pick', max_attempts=3,
                backoff='exponential'):
    return api_client.put(f'/retry/policies/{skill_id}', json={
        'max_attempts': max_attempts,
        'backoff': backoff,
        'base_delay_ms': 200,
        'max_delay_ms': 5000,
        'jitter_ms': 0,
        'retryable_statuses': ['failed', 'aborted'],
    })


class TestRetryConfigAPI:
    def test_get_default_config(self, api_client):
        r = api_client.get('/retry/config')
        assert r.status_code == 200
        data = r.json()
        assert data['max_attempts'] == 3
        assert data['backoff'] == 'exponential'


class TestRetryListAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/retry/policies')
        assert r.status_code == 200
        assert r.json()['policy_count'] == 0

    def test_list_after_set(self, api_client):
        _set_policy(api_client)
        r = api_client.get('/retry/policies')
        assert r.json()['policy_count'] == 1
        assert r.json()['policies'][0]['skill_id'] == 'etd.pick'


class TestRetryGetAPI:
    def test_get_explicit_policy(self, api_client):
        _set_policy(api_client, max_attempts=7)
        r = api_client.get('/retry/policies/etd.pick')
        assert r.status_code == 200
        data = r.json()
        assert data['explicit'] is True
        assert data['config']['max_attempts'] == 7

    def test_get_default_when_none_set(self, api_client):
        r = api_client.get('/retry/policies/unknown.skill')
        assert r.status_code == 200
        assert r.json()['explicit'] is False
        assert r.json()['config']['max_attempts'] == 3

    def test_get_has_skill_id(self, api_client):
        r = api_client.get('/retry/policies/etd.weld')
        assert r.json()['skill_id'] == 'etd.weld'


class TestRetrySetAPI:
    def test_create_returns_201(self, api_client):
        r = _set_policy(api_client)
        assert r.status_code == 201

    def test_update_returns_200(self, api_client):
        _set_policy(api_client)
        r = _set_policy(api_client, max_attempts=5)
        assert r.status_code == 200

    def test_invalid_backoff_422(self, api_client):
        r = api_client.put('/retry/policies/etd.pick', json={
            'max_attempts': 3, 'backoff': 'random',
            'base_delay_ms': 100, 'max_delay_ms': 1000,
            'jitter_ms': 0, 'retryable_statuses': ['failed'],
        })
        assert r.status_code == 422

    def test_policy_stored(self, api_client):
        _set_policy(api_client, max_attempts=8)
        r = api_client.get('/retry/policies/etd.pick')
        assert r.json()['config']['max_attempts'] == 8


class TestRetryDeleteAPI:
    def test_delete_existing(self, api_client):
        _set_policy(api_client)
        r = api_client.delete('/retry/policies/etd.pick')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        r = api_client.delete('/retry/policies/ghost')
        assert r.status_code == 404

    def test_deleted_returns_default(self, api_client):
        _set_policy(api_client, max_attempts=9)
        api_client.delete('/retry/policies/etd.pick')
        r = api_client.get('/retry/policies/etd.pick')
        assert r.json()['explicit'] is False


class TestRetryAdviseAPI:
    def test_advise_success_no_retry(self, api_client):
        r = api_client.post('/retry/advise', json={
            'skill_id': 'etd.pick', 'attempt': 1, 'last_status': 'success',
        })
        assert r.status_code == 200
        assert r.json()['retry'] is False
        assert r.json()['reason'] == 'not_retryable_status'

    def test_advise_failed_retry(self, api_client):
        _set_policy(api_client, max_attempts=3)
        r = api_client.post('/retry/advise', json={
            'skill_id': 'etd.pick', 'attempt': 1, 'last_status': 'failed',
        })
        assert r.json()['retry'] is True
        assert r.json()['reason'] == 'ok_to_retry'
        assert r.json()['next_attempt'] == 2

    def test_advise_max_attempts_stop(self, api_client):
        _set_policy(api_client, max_attempts=3)
        r = api_client.post('/retry/advise', json={
            'skill_id': 'etd.pick', 'attempt': 3, 'last_status': 'failed',
        })
        assert r.json()['retry'] is False
        assert r.json()['reason'] == 'max_attempts_reached'

    def test_advise_response_has_all_fields(self, api_client):
        r = api_client.post('/retry/advise', json={
            'skill_id': 'etd.pick', 'attempt': 1, 'last_status': 'failed',
        })
        data = r.json()
        assert {'retry', 'reason', 'attempt', 'next_attempt',
                'delay_ms', 'max_attempts'} <= set(data)

    def test_advise_uses_explicit_policy(self, api_client):
        _set_policy(api_client, max_attempts=10, backoff='fixed')
        r = api_client.post('/retry/advise', json={
            'skill_id': 'etd.pick', 'attempt': 5, 'last_status': 'failed',
        })
        assert r.json()['retry'] is True
        assert r.json()['max_attempts'] == 10
