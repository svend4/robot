"""Tests for marketplace.skill_tags and the /tags + /taggings REST API."""
from __future__ import annotations

import pytest

from marketplace.skill_tags import TagEntry, TagStore


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> TagStore:
    return TagStore(tmp_path / 'tags')


# ── TagEntry ──────────────────────────────────────────────────────────────────

class TestTagEntry:
    def test_defaults(self):
        e = TagEntry(tag_id='safety')
        assert e.color is None
        assert e.description == ''
        assert e.created_at

    def test_round_trip(self):
        e = TagEntry(tag_id='prod', color='green', description='live')
        e2 = TagEntry.from_dict(e.to_dict())
        assert e2.tag_id == 'prod'
        assert e2.color == 'green'
        assert e2.description == 'live'

    def test_to_dict_keys(self):
        keys = set(TagEntry(tag_id='x').to_dict())
        assert {'tag_id', 'color', 'description', 'created_at'} <= keys

    def test_from_dict_defaults(self):
        e = TagEntry.from_dict({'tag_id': 'x'})
        assert e.color is None
        assert e.description == ''


# ── TagStore — tag CRUD ───────────────────────────────────────────────────────

class TestTagCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.tag_count == 0
        assert store.list_tags() == []

    def test_create_tag(self, tmp_path):
        store = _store(tmp_path)
        entry = store.create_tag('safety', color='red', description='careful')
        assert entry.tag_id == 'safety'
        assert entry.color == 'red'

    def test_create_idempotent(self, tmp_path):
        store = _store(tmp_path)
        e1 = store.create_tag('safety')
        e2 = store.create_tag('safety', color='blue')  # already exists
        assert e2.created_at == e1.created_at
        assert e2.color is None  # original preserved

    def test_get_tag(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('prod')
        assert store.get_tag('prod') is not None

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get_tag('ghost') is None

    def test_update_color(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('prod', color='green')
        entry = store.update_tag('prod', color='blue')
        assert entry.color == 'blue'

    def test_update_description(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('prod', description='old')
        entry = store.update_tag('prod', description='new')
        assert entry.description == 'new'

    def test_update_none_fields_unchanged(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('prod', color='red', description='live')
        entry = store.update_tag('prod')  # no changes
        assert entry.color == 'red'
        assert entry.description == 'live'

    def test_update_unknown_returns_none(self, tmp_path):
        assert _store(tmp_path).update_tag('ghost') is None

    def test_delete_existing(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('prod')
        assert store.delete_tag('prod') is True
        assert store.get_tag('prod') is None

    def test_delete_unknown_false(self, tmp_path):
        assert _store(tmp_path).delete_tag('ghost') is False

    def test_delete_removes_from_mappings(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('safety')
        store.tag_skill('etd.pick', 'safety')
        store.delete_tag('safety')
        assert 'safety' not in store.get_skill_tags('etd.pick')

    def test_list_tags(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('a')
        store.create_tag('b')
        ids = {t.tag_id for t in store.list_tags()}
        assert ids == {'a', 'b'}

    def test_tag_count(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('a')
        store.create_tag('b')
        assert store.tag_count == 2


# ── TagStore — skill ↔ tag mappings ──────────────────────────────────────────

class TestMappings:
    def _setup(self, tmp_path):
        store = _store(tmp_path)
        store.create_tag('safety')
        store.create_tag('production')
        store.create_tag('maintenance')
        return store

    def test_tag_skill_returns_true_on_new(self, tmp_path):
        store = self._setup(tmp_path)
        assert store.tag_skill('etd.pick', 'safety') is True

    def test_tag_skill_returns_false_on_duplicate(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        assert store.tag_skill('etd.pick', 'safety') is False

    def test_tag_skill_raises_on_unknown_tag(self, tmp_path):
        store = _store(tmp_path)
        with pytest.raises(KeyError):
            store.tag_skill('etd.pick', 'nonexistent')

    def test_untag_skill_existing(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        assert store.untag_skill('etd.pick', 'safety') is True
        assert 'safety' not in store.get_skill_tags('etd.pick')

    def test_untag_skill_not_tagged_false(self, tmp_path):
        store = self._setup(tmp_path)
        assert store.untag_skill('etd.pick', 'safety') is False

    def test_get_skill_tags_sorted(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        store.tag_skill('etd.pick', 'production')
        tags = store.get_skill_tags('etd.pick')
        assert tags == sorted(tags)
        assert set(tags) == {'safety', 'production'}

    def test_get_skill_tags_empty(self, tmp_path):
        assert _store(tmp_path).get_skill_tags('etd.pick') == []

    def test_get_skills_by_tag_sorted(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.weld', 'safety')
        store.tag_skill('etd.pick', 'safety')
        skills = store.get_skills_by_tag('safety')
        assert skills == sorted(skills)
        assert set(skills) == {'etd.weld', 'etd.pick'}

    def test_get_skills_by_tag_empty(self, tmp_path):
        store = self._setup(tmp_path)
        assert store.get_skills_by_tag('maintenance') == []

    def test_multiple_tags_per_skill(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        store.tag_skill('etd.pick', 'production')
        store.tag_skill('etd.pick', 'maintenance')
        assert len(store.get_skill_tags('etd.pick')) == 3

    def test_list_skill_tags(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        store.tag_skill('etd.weld', 'production')
        mappings = store.list_skill_tags()
        assert 'etd.pick' in mappings
        assert 'safety' in mappings['etd.pick']

    def test_list_skill_tags_excludes_empty(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        store.untag_skill('etd.pick', 'safety')
        mappings = store.list_skill_tags()
        assert 'etd.pick' not in mappings

    def test_tagged_skill_count(self, tmp_path):
        store = self._setup(tmp_path)
        store.tag_skill('etd.pick', 'safety')
        store.tag_skill('etd.weld', 'safety')
        assert store.tagged_skill_count() == 2


# ── TagStore — persistence ────────────────────────────────────────────────────

class TestPersistence:
    def test_persists_tags(self, tmp_path):
        p = tmp_path / 'tags'
        TagStore(p).create_tag('prod', color='green')
        s2 = TagStore(p)
        assert s2.get_tag('prod').color == 'green'

    def test_persists_mappings(self, tmp_path):
        p = tmp_path / 'tags'
        s1 = TagStore(p)
        s1.create_tag('safety')
        s1.tag_skill('etd.pick', 'safety')
        s2 = TagStore(p)
        assert 'safety' in s2.get_skill_tags('etd.pick')

    def test_creates_dir(self, tmp_path):
        s = TagStore(tmp_path / 'a' / 'b')
        s.create_tag('x')
        assert (tmp_path / 'a' / 'b' / 'tags.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'tags.json').write_text('bad json')
        s = TagStore(tmp_path)
        assert s.tag_count == 0


# ── REST API /tags ────────────────────────────────────────────────────────────

import api.skill_tags as _tags_mod


@pytest.fixture(autouse=True)
def patch_tags_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_tags_mod, '_TAGS_DIR', tmp_path / 'tags')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _create(api_client, tag_id='safety', color=None, description=''):
    return api_client.post('/tags', json={
        'tag_id': tag_id, 'color': color, 'description': description,
    })


class TestTagsAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/tags')
        assert r.status_code == 200
        assert r.json()['tag_count'] == 0

    def test_create_201(self, api_client):
        r = _create(api_client)
        assert r.status_code == 201

    def test_create_idempotent_200(self, api_client):
        _create(api_client)
        r = _create(api_client)
        assert r.status_code == 200

    def test_create_has_tag_id(self, api_client):
        assert _create(api_client).json()['tag_id'] == 'safety'

    def test_list_after_create(self, api_client):
        _create(api_client)
        _create(api_client, tag_id='production')
        r = api_client.get('/tags')
        assert r.json()['tag_count'] == 2

    def test_get_found(self, api_client):
        _create(api_client, color='red')
        r = api_client.get('/tags/safety')
        assert r.status_code == 200
        assert r.json()['color'] == 'red'

    def test_get_404(self, api_client):
        assert api_client.get('/tags/ghost').status_code == 404

    def test_update_200(self, api_client):
        _create(api_client, color='red')
        r = api_client.patch('/tags/safety', json={'color': 'blue'})
        assert r.status_code == 200
        assert r.json()['color'] == 'blue'

    def test_update_404(self, api_client):
        r = api_client.patch('/tags/ghost', json={'color': 'red'})
        assert r.status_code == 404

    def test_delete_200(self, api_client):
        _create(api_client)
        r = api_client.delete('/tags/safety')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/tags/ghost').status_code == 404

    def test_delete_removes_from_skills(self, api_client):
        _create(api_client)
        api_client.post('/taggings/etd.pick/safety')
        api_client.delete('/tags/safety')
        r = api_client.get('/taggings/etd.pick')
        assert 'safety' not in r.json()['tags']


class TestTaggingsAPI:
    def test_list_all_empty(self, api_client):
        r = api_client.get('/taggings')
        assert r.status_code == 200
        assert r.json()['tagged_skill_count'] == 0

    def test_skill_tags_empty(self, api_client):
        r = api_client.get('/taggings/etd.pick')
        assert r.status_code == 200
        assert r.json()['tag_count'] == 0

    def test_tag_skill_201(self, api_client):
        _create(api_client)
        r = api_client.post('/taggings/etd.pick/safety')
        assert r.status_code == 201
        assert r.json()['added'] is True

    def test_tag_skill_200_duplicate(self, api_client):
        _create(api_client)
        api_client.post('/taggings/etd.pick/safety')
        r = api_client.post('/taggings/etd.pick/safety')
        assert r.status_code == 200
        assert r.json()['added'] is False

    def test_tag_skill_404_unknown_tag(self, api_client):
        r = api_client.post('/taggings/etd.pick/ghost')
        assert r.status_code == 404

    def test_untag_skill_200(self, api_client):
        _create(api_client)
        api_client.post('/taggings/etd.pick/safety')
        r = api_client.delete('/taggings/etd.pick/safety')
        assert r.status_code == 200

    def test_untag_skill_404(self, api_client):
        _create(api_client)
        r = api_client.delete('/taggings/etd.pick/safety')
        assert r.status_code == 404

    def test_skills_by_tag_200(self, api_client):
        _create(api_client)
        api_client.post('/taggings/etd.pick/safety')
        api_client.post('/taggings/etd.weld/safety')
        r = api_client.get('/taggings/by-tag/safety')
        assert r.status_code == 200
        assert set(r.json()['skills']) == {'etd.pick', 'etd.weld'}

    def test_skills_by_tag_404_unknown(self, api_client):
        r = api_client.get('/taggings/by-tag/ghost')
        assert r.status_code == 404

    def test_list_all_after_tagging(self, api_client):
        _create(api_client)
        api_client.post('/taggings/etd.pick/safety')
        r = api_client.get('/taggings')
        assert r.json()['tagged_skill_count'] == 1
        assert 'etd.pick' in r.json()['mappings']
