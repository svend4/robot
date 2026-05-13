"""Tests for marketplace.skill_ratings and the /ratings REST API."""
from __future__ import annotations

import pytest

from marketplace.skill_ratings import RatingEntry, RatingStats, RatingStore


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> RatingStore:
    return RatingStore(tmp_path / 'ratings')


# ── RatingEntry ───────────────────────────────────────────────────────────────

class TestRatingEntry:
    def test_defaults(self):
        e = RatingEntry(rating_id='r1', skill_id='etd.pick', rating=4)
        assert e.comment == ''
        assert e.operator_id == 'anonymous'
        assert e.created_at

    def test_round_trip(self):
        e = RatingEntry(rating_id='r1', skill_id='etd.pick', rating=5,
                        comment='great', operator_id='ops')
        e2 = RatingEntry.from_dict(e.to_dict())
        assert e2.rating_id == 'r1'
        assert e2.skill_id == 'etd.pick'
        assert e2.rating == 5
        assert e2.comment == 'great'
        assert e2.operator_id == 'ops'

    def test_to_dict_keys(self):
        keys = set(RatingEntry(rating_id='x', skill_id='s', rating=3).to_dict())
        assert {'rating_id', 'skill_id', 'rating', 'comment',
                'operator_id', 'created_at'} <= keys

    def test_from_dict_defaults(self):
        e = RatingEntry.from_dict({'rating_id': 'x', 'skill_id': 's', 'rating': 3})
        assert e.comment == ''
        assert e.operator_id == 'anonymous'


# ── RatingStats ───────────────────────────────────────────────────────────────

class TestRatingStats:
    def test_to_dict_keys(self):
        s = RatingStats(skill_id='s', count=1, mean=4.0,
                        distribution={1: 0, 2: 0, 3: 0, 4: 1, 5: 0})
        keys = set(s.to_dict())
        assert {'skill_id', 'count', 'mean', 'distribution'} <= keys


# ── RatingStore CRUD ──────────────────────────────────────────────────────────

class TestRatingStoreCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.rating_count == 0
        assert store.list_ratings() == []

    def test_add_rating(self, tmp_path):
        store = _store(tmp_path)
        e = store.add_rating('etd.pick', 5)
        assert e.skill_id == 'etd.pick'
        assert e.rating == 5
        assert e.rating_id

    def test_add_with_comment_and_operator(self, tmp_path):
        store = _store(tmp_path)
        e = store.add_rating('etd.pick', 4, comment='good', operator_id='ops')
        assert e.comment == 'good'
        assert e.operator_id == 'ops'

    def test_add_invalid_zero(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).add_rating('etd.pick', 0)

    def test_add_invalid_six(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).add_rating('etd.pick', 6)

    def test_add_invalid_negative(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).add_rating('etd.pick', -1)

    def test_get_rating(self, tmp_path):
        store = _store(tmp_path)
        e = store.add_rating('etd.pick', 3)
        assert store.get_rating(e.rating_id) is not None

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get_rating('ghost') is None

    def test_list_all(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.weld', 3)
        assert len(store.list_ratings()) == 2

    def test_list_filtered(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.weld', 3)
        results = store.list_ratings(skill_id='etd.pick')
        assert len(results) == 1
        assert results[0].skill_id == 'etd.pick'

    def test_list_filtered_empty(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        assert store.list_ratings(skill_id='etd.weld') == []

    def test_remove_existing(self, tmp_path):
        store = _store(tmp_path)
        e = store.add_rating('etd.pick', 4)
        assert store.remove_rating(e.rating_id) is True
        assert store.get_rating(e.rating_id) is None

    def test_remove_unknown_false(self, tmp_path):
        assert _store(tmp_path).remove_rating('ghost') is False

    def test_rating_count(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.pick', 4)
        assert store.rating_count == 2

    def test_rated_skills_sorted(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.weld', 4)
        store.add_rating('etd.pick', 5)
        assert store.rated_skills() == ['etd.pick', 'etd.weld']

    def test_rated_skills_dedup(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.pick', 3)
        assert store.rated_skills() == ['etd.pick']


# ── RatingStore — stats ───────────────────────────────────────────────────────

class TestRatingStats:
    def test_stats_none_when_no_ratings(self, tmp_path):
        assert _store(tmp_path).get_stats('etd.pick') is None

    def test_stats_single_rating(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        stats = store.get_stats('etd.pick')
        assert stats.count == 1
        assert stats.mean == 5.0
        assert stats.skill_id == 'etd.pick'

    def test_stats_mean_rounded(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 4)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.pick', 3)
        stats = store.get_stats('etd.pick')
        assert stats.mean == round((4 + 5 + 3) / 3, 2)

    def test_stats_distribution_keys(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        stats = store.get_stats('etd.pick')
        assert set(stats.distribution.keys()) == {1, 2, 3, 4, 5}

    def test_stats_distribution_counts(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.pick', 3)
        stats = store.get_stats('etd.pick')
        assert stats.distribution[5] == 2
        assert stats.distribution[3] == 1
        assert stats.distribution[1] == 0

    def test_stats_independent_per_skill(self, tmp_path):
        store = _store(tmp_path)
        store.add_rating('etd.pick', 5)
        store.add_rating('etd.weld', 2)
        assert store.get_stats('etd.pick').mean == 5.0
        assert store.get_stats('etd.weld').mean == 2.0

    def test_stats_count(self, tmp_path):
        store = _store(tmp_path)
        for _ in range(3):
            store.add_rating('etd.pick', 4)
        assert store.get_stats('etd.pick').count == 3


# ── RatingStore — persistence ─────────────────────────────────────────────────

class TestPersistence:
    def test_persists_ratings(self, tmp_path):
        p = tmp_path / 'ratings'
        e = RatingStore(p).add_rating('etd.pick', 5, comment='nice')
        s2 = RatingStore(p)
        e2 = s2.get_rating(e.rating_id)
        assert e2 is not None
        assert e2.comment == 'nice'

    def test_creates_dir(self, tmp_path):
        s = RatingStore(tmp_path / 'a' / 'b')
        s.add_rating('etd.pick', 4)
        assert (tmp_path / 'a' / 'b' / 'ratings.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'ratings.json').write_text('bad json')
        s = RatingStore(tmp_path)
        assert s.rating_count == 0


# ── REST API ──────────────────────────────────────────────────────────────────

import api.skill_ratings as _ratings_mod


@pytest.fixture(autouse=True)
def patch_ratings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_ratings_mod, '_RATINGS_DIR', tmp_path / 'ratings')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _add(api_client, skill_id='etd.pick', rating=5, comment='', operator_id='anonymous'):
    return api_client.post('/ratings', json={
        'skill_id': skill_id, 'rating': rating,
        'comment': comment, 'operator_id': operator_id,
    })


class TestRatingsAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/ratings')
        assert r.status_code == 200
        assert r.json()['rating_count'] == 0

    def test_add_201(self, api_client):
        r = _add(api_client)
        assert r.status_code == 201

    def test_add_has_rating_id(self, api_client):
        r = _add(api_client)
        assert 'rating_id' in r.json()

    def test_add_has_skill_id(self, api_client):
        assert _add(api_client).json()['skill_id'] == 'etd.pick'

    def test_add_rating_zero_422(self, api_client):
        r = api_client.post('/ratings', json={'skill_id': 'etd.pick', 'rating': 0})
        assert r.status_code == 422

    def test_add_rating_six_422(self, api_client):
        r = api_client.post('/ratings', json={'skill_id': 'etd.pick', 'rating': 6})
        assert r.status_code == 422

    def test_list_after_add(self, api_client):
        _add(api_client)
        _add(api_client, skill_id='etd.weld', rating=3)
        r = api_client.get('/ratings')
        assert r.json()['rating_count'] == 2

    def test_list_filter_skill(self, api_client):
        _add(api_client, skill_id='etd.pick')
        _add(api_client, skill_id='etd.weld')
        r = api_client.get('/ratings?skill_id=etd.pick')
        assert r.json()['rating_count'] == 1
        assert r.json()['ratings'][0]['skill_id'] == 'etd.pick'

    def test_get_found(self, api_client):
        rating_id = _add(api_client).json()['rating_id']
        r = api_client.get(f'/ratings/{rating_id}')
        assert r.status_code == 200
        assert r.json()['rating_id'] == rating_id

    def test_get_404(self, api_client):
        assert api_client.get('/ratings/ghost').status_code == 404

    def test_stats_found(self, api_client):
        _add(api_client, rating=4)
        _add(api_client, rating=5)
        r = api_client.get('/ratings/stats/etd.pick')
        assert r.status_code == 200
        assert r.json()['count'] == 2
        assert r.json()['mean'] == 4.5

    def test_stats_404(self, api_client):
        assert api_client.get('/ratings/stats/etd.unknown').status_code == 404

    def test_stats_distribution(self, api_client):
        _add(api_client, rating=5)
        _add(api_client, rating=5)
        _add(api_client, rating=3)
        stats = api_client.get('/ratings/stats/etd.pick').json()
        assert stats['distribution']['5'] == 2
        assert stats['distribution']['3'] == 1

    def test_delete_200(self, api_client):
        rating_id = _add(api_client).json()['rating_id']
        r = api_client.delete(f'/ratings/{rating_id}')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/ratings/ghost').status_code == 404

    def test_delete_removes_rating(self, api_client):
        rating_id = _add(api_client).json()['rating_id']
        api_client.delete(f'/ratings/{rating_id}')
        assert api_client.get(f'/ratings/{rating_id}').status_code == 404

    def test_rated_skills(self, api_client):
        _add(api_client, skill_id='etd.pick')
        _add(api_client, skill_id='etd.weld')
        r = api_client.get('/ratings/skills')
        assert r.status_code == 200
        assert set(r.json()['skills']) == {'etd.pick', 'etd.weld'}

    def test_rated_skills_empty(self, api_client):
        r = api_client.get('/ratings/skills')
        assert r.json()['skill_count'] == 0
