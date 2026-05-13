"""Tests for marketplace.ab_testing and the /ab REST API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketplace.ab_testing import (
    ABAnalyzer,
    ABExperiment,
    ABExperimentStore,
    ABVariant,
    VariantResult,
)
from marketplace.telemetry_analytics import TelemetryStore, ExecutionRecord


# ── fixtures & helpers ────────────────────────────────────────────────────────

def _two_variants():
    return [
        ABVariant('etd.pick', '0.1.0', 0.5, 'control'),
        ABVariant('etd.pick', '0.2.0', 0.5, 'treatment'),
    ]


def _exp(name='test', **kwargs) -> ABExperiment:
    return ABExperiment.make(name=name, variants=_two_variants(), **kwargs)


@pytest.fixture()
def store(tmp_path) -> ABExperimentStore:
    return ABExperimentStore(tmp_path / 'experiments.json')


@pytest.fixture()
def tel_store(tmp_path) -> TelemetryStore:
    return TelemetryStore(tmp_path / 'executions.jsonl')


# ── ABVariant ─────────────────────────────────────────────────────────────────

class TestABVariant:
    def test_to_dict_keys(self):
        v = ABVariant('etd.pick', '0.1.0', 0.5, 'control')
        d = v.to_dict()
        assert set(d) == {'skill_id', 'version', 'weight', 'label'}

    def test_round_trip(self):
        v = ABVariant('etd.pick', '0.1.0', 0.7, 'control')
        v2 = ABVariant.from_dict(v.to_dict())
        assert v2.skill_id == 'etd.pick'
        assert v2.weight == 0.7
        assert v2.label == 'control'

    def test_defaults(self):
        v = ABVariant.from_dict({'skill_id': 'a', 'version': '1.0'})
        assert v.weight == 1.0
        assert v.label == ''


# ── ABExperiment ──────────────────────────────────────────────────────────────

class TestABExperiment:
    def test_make_fills_id(self):
        exp = _exp()
        assert exp.experiment_id
        assert exp.created_at
        assert exp.status == 'active'

    def test_to_dict_keys(self):
        d = _exp().to_dict()
        assert set(d) >= {'experiment_id', 'name', 'variants', 'status',
                          'created_at', 'concluded_at', 'winner_label'}

    def test_round_trip(self):
        exp = _exp(name='my-exp')
        exp2 = ABExperiment.from_dict(exp.to_dict())
        assert exp2.name == 'my-exp'
        assert len(exp2.variants) == 2

    def test_get_variant_found(self):
        exp = _exp()
        v = exp.get_variant('control')
        assert v is not None
        assert v.label == 'control'

    def test_get_variant_not_found(self):
        assert _exp().get_variant('ghost') is None

    def test_route_returns_variant(self):
        exp = _exp()
        chosen = exp.route()
        assert chosen in exp.variants

    def test_route_respects_zero_weight(self):
        exp = ABExperiment.make(name='x', variants=[
            ABVariant('a', '1.0', 0.0, 'never'),
            ABVariant('b', '1.0', 1.0, 'always'),
        ])
        for _ in range(20):
            assert exp.route().label == 'always'

    def test_route_raises_when_paused(self):
        exp = _exp()
        exp.pause()
        with pytest.raises(ValueError, match='paused'):
            exp.route()

    def test_route_raises_when_concluded(self):
        exp = _exp()
        exp.conclude()
        with pytest.raises(ValueError, match='concluded'):
            exp.route()

    def test_route_raises_all_zero_weights(self):
        exp = ABExperiment.make(name='x', variants=[
            ABVariant('a', '1.0', 0.0, 'x'),
            ABVariant('b', '1.0', 0.0, 'y'),
        ])
        with pytest.raises(ValueError, match='positive weight'):
            exp.route()

    def test_pause_transitions(self):
        exp = _exp()
        exp.pause()
        assert exp.status == 'paused'

    def test_pause_twice_raises(self):
        exp = _exp()
        exp.pause()
        with pytest.raises(ValueError):
            exp.pause()

    def test_resume_transitions(self):
        exp = _exp()
        exp.pause()
        exp.resume()
        assert exp.status == 'active'

    def test_resume_active_raises(self):
        with pytest.raises(ValueError):
            _exp().resume()

    def test_conclude_sets_fields(self):
        exp = _exp()
        exp.conclude(winner_label='control')
        assert exp.status == 'concluded'
        assert exp.winner_label == 'control'
        assert exp.concluded_at is not None

    def test_conclude_twice_raises(self):
        exp = _exp()
        exp.conclude()
        with pytest.raises(ValueError, match='already concluded'):
            exp.conclude()

    def test_conclude_no_winner(self):
        exp = _exp()
        exp.conclude()
        assert exp.winner_label is None


# ── ABExperimentStore ─────────────────────────────────────────────────────────

class TestABExperimentStore:
    def test_empty_count(self, store):
        assert store.experiment_count == 0

    def test_save_and_get(self, store):
        exp = _exp()
        store.save(exp)
        assert store.get(exp.experiment_id) is not None

    def test_get_unknown_returns_none(self, store):
        assert store.get('ghost-id') is None

    def test_list_all(self, store):
        store.save(_exp('a'))
        store.save(_exp('b'))
        assert len(store.list_experiments()) == 2

    def test_list_filter_status(self, store):
        a = _exp('a')
        b = _exp('b')
        b.pause()
        store.save(a)
        store.save(b)
        assert len(store.list_experiments(status='active')) == 1
        assert len(store.list_experiments(status='paused')) == 1

    def test_delete_removes(self, store):
        exp = _exp()
        store.save(exp)
        store.delete(exp.experiment_id)
        assert store.get(exp.experiment_id) is None

    def test_delete_unknown_returns_false(self, store):
        assert store.delete('ghost') is False

    def test_persistence(self, tmp_path):
        path = tmp_path / 'exp.json'
        s1 = ABExperimentStore(path)
        exp = _exp(name='persist-test')
        s1.save(exp)
        s2 = ABExperimentStore(path)
        loaded = s2.get(exp.experiment_id)
        assert loaded is not None
        assert loaded.name == 'persist-test'

    def test_save_updates_existing(self, store):
        exp = _exp()
        store.save(exp)
        exp.pause()
        store.save(exp)
        assert store.get(exp.experiment_id).status == 'paused'

    def test_list_sorted_newest_first(self, store):
        a = _exp('a'); a.created_at = '2026-01-01T00:00:00+00:00'
        b = _exp('b'); b.created_at = '2026-06-01T00:00:00+00:00'
        store.save(a); store.save(b)
        lst = store.list_experiments()
        assert lst[0].created_at > lst[-1].created_at

    def test_creates_parent_dirs(self, tmp_path):
        s = ABExperimentStore(tmp_path / 'a' / 'b' / 'exp.json')
        s.save(_exp())
        assert (tmp_path / 'a' / 'b' / 'exp.json').exists()

    def test_corrupt_file_loads_empty(self, tmp_path):
        path = tmp_path / 'exp.json'
        path.write_text('not-json')
        s = ABExperimentStore(path)
        assert s.experiment_count == 0


# ── ABAnalyzer ────────────────────────────────────────────────────────────────

class TestABAnalyzer:
    def _seed_telemetry(self, store, skill_id, n_ok, n_fail, base_duration=1000):
        for i in range(n_ok):
            store.record(ExecutionRecord.make(
                skill_id=skill_id, node_id='r01', station_id='ws',
                status='success', total_duration_ms=base_duration + i * 10,
            ))
        for i in range(n_fail):
            store.record(ExecutionRecord.make(
                skill_id=skill_id, node_id='r01', station_id='ws',
                status='failed', total_duration_ms=base_duration,
            ))

    def test_compare_structure(self, tel_store):
        exp = _exp()
        cmp = ABAnalyzer(tel_store).compare(exp)
        assert 'experiment_id' in cmp
        assert 'variants' in cmp
        assert len(cmp['variants']) == 2

    def test_compare_no_data_zero_counts(self, tel_store):
        exp = _exp()
        cmp = ABAnalyzer(tel_store).compare(exp)
        for v in cmp['variants']:
            assert v['execution_count'] == 0

    def test_compare_with_data(self, tel_store):
        self._seed_telemetry(tel_store, 'etd.pick', n_ok=8, n_fail=2)
        exp = _exp()
        cmp = ABAnalyzer(tel_store).compare(exp)
        control = next(v for v in cmp['variants'] if v['label'] == 'control')
        assert control['execution_count'] == 10
        assert abs(control['success_rate'] - 0.8) < 0.01

    def test_recommend_none_no_data(self, tel_store):
        assert ABAnalyzer(tel_store).recommend_winner(_exp()) is None

    def test_recommend_higher_success_rate_wins(self, tel_store):
        self._seed_telemetry(tel_store, 'etd.pick', n_ok=9, n_fail=1)
        # treatment variant uses same skill_id in this simple test
        # use a 3-variant experiment where all map to same skill
        exp = ABExperiment.make(name='x', variants=[
            ABVariant('etd.pick', '0.1.0', 1.0, 'control'),
            ABVariant('etd.inspect', '0.1.0', 1.0, 'treatment'),
        ])
        # seed inspect with lower success rate
        self._seed_telemetry(tel_store, 'etd.inspect', n_ok=3, n_fail=7)
        winner = ABAnalyzer(tel_store).recommend_winner(exp)
        assert winner == 'control'

    def test_recommend_lower_duration_breaks_tie(self, tel_store):
        self._seed_telemetry(tel_store, 'etd.pick', n_ok=5, n_fail=0, base_duration=2000)
        self._seed_telemetry(tel_store, 'etd.inspect', n_ok=5, n_fail=0, base_duration=500)
        exp = ABExperiment.make(name='x', variants=[
            ABVariant('etd.pick', '0.1.0', 1.0, 'slow'),
            ABVariant('etd.inspect', '0.1.0', 1.0, 'fast'),
        ])
        assert ABAnalyzer(tel_store).recommend_winner(exp) == 'fast'

    def test_variant_result_to_dict(self, tel_store):
        self._seed_telemetry(tel_store, 'etd.pick', n_ok=5, n_fail=0)
        exp = _exp()
        cmp = ABAnalyzer(tel_store).compare(exp)
        control = cmp['variants'][0]
        assert 'p95_ms' in control
        assert 'mean_duration_ms' in control


# ── REST API /ab ──────────────────────────────────────────────────────────────

import api.ab_testing as _ab_mod


@pytest.fixture(autouse=True)
def patch_ab_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(_ab_mod, '_AB_STORE_PATH', tmp_path / 'experiments.json')
    monkeypatch.setattr(_ab_mod, '_TEL_STORE_PATH', tmp_path / 'executions.jsonl')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _create_body(**kwargs):
    body = {
        'name': 'speed trial',
        'variants': [
            {'skill_id': 'etd.pick', 'version': '0.1.0',
             'weight': 0.5, 'label': 'control'},
            {'skill_id': 'etd.pick', 'version': '0.2.0',
             'weight': 0.5, 'label': 'treatment'},
        ],
    }
    body.update(kwargs)
    return body


class TestABApiCreate:
    def test_create_201(self, api_client):
        r = api_client.post('/ab/experiments', json=_create_body())
        assert r.status_code == 201

    def test_create_has_id(self, api_client):
        data = api_client.post('/ab/experiments', json=_create_body()).json()
        assert 'experiment_id' in data
        assert data['status'] == 'active'

    def test_create_one_variant_422(self, api_client):
        body = _create_body()
        body['variants'] = body['variants'][:1]
        r = api_client.post('/ab/experiments', json=body)
        assert r.status_code == 422


class TestABApiList:
    def test_list_200(self, api_client):
        r = api_client.get('/ab/experiments')
        assert r.status_code == 200

    def test_list_empty(self, api_client):
        data = api_client.get('/ab/experiments').json()
        assert data['count'] == 0

    def test_list_after_create(self, api_client):
        api_client.post('/ab/experiments', json=_create_body())
        data = api_client.get('/ab/experiments').json()
        assert data['count'] == 1

    def test_list_filter_status(self, api_client):
        api_client.post('/ab/experiments', json=_create_body())
        data = api_client.get('/ab/experiments?status=active').json()
        assert data['count'] == 1
        data2 = api_client.get('/ab/experiments?status=paused').json()
        assert data2['count'] == 0


class TestABApiGet:
    def test_get_found(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        r = api_client.get(f'/ab/experiments/{exp_id}')
        assert r.status_code == 200
        assert r.json()['experiment_id'] == exp_id

    def test_get_404(self, api_client):
        r = api_client.get('/ab/experiments/ghost-id')
        assert r.status_code == 404


class TestABApiDelete:
    def test_delete_200(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        r = api_client.delete(f'/ab/experiments/{exp_id}')
        assert r.status_code == 200
        assert r.json()['deleted'] == exp_id

    def test_delete_404(self, api_client):
        r = api_client.delete('/ab/experiments/ghost-id')
        assert r.status_code == 404

    def test_delete_then_get_404(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        api_client.delete(f'/ab/experiments/{exp_id}')
        assert api_client.get(f'/ab/experiments/{exp_id}').status_code == 404


class TestABApiLifecycle:
    def _create(self, api_client) -> str:
        return api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']

    def test_pause_200(self, api_client):
        exp_id = self._create(api_client)
        r = api_client.put(f'/ab/experiments/{exp_id}/pause')
        assert r.status_code == 200
        assert r.json()['status'] == 'paused'

    def test_pause_404(self, api_client):
        r = api_client.put('/ab/experiments/ghost/pause')
        assert r.status_code == 404

    def test_pause_conflict(self, api_client):
        exp_id = self._create(api_client)
        api_client.put(f'/ab/experiments/{exp_id}/pause')
        r = api_client.put(f'/ab/experiments/{exp_id}/pause')
        assert r.status_code == 409

    def test_resume_200(self, api_client):
        exp_id = self._create(api_client)
        api_client.put(f'/ab/experiments/{exp_id}/pause')
        r = api_client.put(f'/ab/experiments/{exp_id}/resume')
        assert r.status_code == 200
        assert r.json()['status'] == 'active'

    def test_resume_conflict(self, api_client):
        exp_id = self._create(api_client)
        r = api_client.put(f'/ab/experiments/{exp_id}/resume')
        assert r.status_code == 409

    def test_conclude_200(self, api_client):
        exp_id = self._create(api_client)
        r = api_client.post(f'/ab/experiments/{exp_id}/conclude',
                             json={'winner_label': 'control'})
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'concluded'
        assert data['winner_label'] == 'control'

    def test_conclude_twice_409(self, api_client):
        exp_id = self._create(api_client)
        api_client.post(f'/ab/experiments/{exp_id}/conclude', json={})
        r = api_client.post(f'/ab/experiments/{exp_id}/conclude', json={})
        assert r.status_code == 409


class TestABApiRoute:
    def test_route_200(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        r = api_client.get(f'/ab/experiments/{exp_id}/route')
        assert r.status_code == 200
        data = r.json()
        assert 'chosen' in data
        assert data['chosen']['skill_id'] == 'etd.pick'

    def test_route_paused_409(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        api_client.put(f'/ab/experiments/{exp_id}/pause')
        r = api_client.get(f'/ab/experiments/{exp_id}/route')
        assert r.status_code == 409


class TestABApiResults:
    def test_results_200(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        r = api_client.get(f'/ab/experiments/{exp_id}/results')
        assert r.status_code == 200

    def test_results_structure(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        data = api_client.get(f'/ab/experiments/{exp_id}/results').json()
        assert 'variants' in data
        assert len(data['variants']) == 2

    def test_results_404(self, api_client):
        r = api_client.get('/ab/experiments/ghost/results')
        assert r.status_code == 404


class TestABApiRecommend:
    def test_recommend_200(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        r = api_client.get(f'/ab/experiments/{exp_id}/recommend')
        assert r.status_code == 200

    def test_recommend_no_data_none(self, api_client):
        exp_id = api_client.post('/ab/experiments', json=_create_body()).json()['experiment_id']
        data = api_client.get(f'/ab/experiments/{exp_id}/recommend').json()
        assert data['recommended_winner'] is None

    def test_recommend_404(self, api_client):
        r = api_client.get('/ab/experiments/ghost/recommend')
        assert r.status_code == 404
