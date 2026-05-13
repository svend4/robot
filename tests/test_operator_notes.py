"""Tests for marketplace.operator_notes and the /notes REST API."""
from __future__ import annotations

import pytest

from marketplace.operator_notes import OperatorNote, NoteStore, VALID_CATEGORIES


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(tmp_path) -> NoteStore:
    return NoteStore(tmp_path / 'notes')


# ── VALID_CATEGORIES ──────────────────────────────────────────────────────────

def test_valid_categories():
    assert VALID_CATEGORIES == {'info', 'warning', 'issue', 'runbook'}


# ── OperatorNote ──────────────────────────────────────────────────────────────

class TestOperatorNote:
    def test_defaults(self):
        n = OperatorNote(note_id='n1', subject='etd.pick', text='hi')
        assert n.category == 'info'
        assert n.author == 'anonymous'
        assert n.created_at
        assert n.updated_at

    def test_round_trip(self):
        n = OperatorNote(note_id='n1', subject='etd.pick', text='check',
                         category='issue', author='ops')
        n2 = OperatorNote.from_dict(n.to_dict())
        assert n2.note_id == 'n1'
        assert n2.subject == 'etd.pick'
        assert n2.text == 'check'
        assert n2.category == 'issue'
        assert n2.author == 'ops'

    def test_to_dict_keys(self):
        keys = set(OperatorNote(note_id='x', subject='s', text='t').to_dict())
        assert {'note_id', 'subject', 'text', 'category',
                'author', 'created_at', 'updated_at'} <= keys

    def test_from_dict_defaults(self):
        n = OperatorNote.from_dict({'note_id': 'x', 'subject': 's', 'text': 't'})
        assert n.category == 'info'
        assert n.author == 'anonymous'


# ── NoteStore — CRUD ──────────────────────────────────────────────────────────

class TestNoteStoreCRUD:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.note_count == 0
        assert store.list_notes() == []

    def test_add_note(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'check torque')
        assert n.subject == 'etd.pick'
        assert n.text == 'check torque'
        assert n.note_id

    def test_add_all_fields(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'see runbook', category='runbook', author='ops')
        assert n.category == 'runbook'
        assert n.author == 'ops'

    def test_add_invalid_category(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).add_note('etd.pick', 'text', category='bogus')

    def test_all_valid_categories(self, tmp_path):
        store = _store(tmp_path)
        for cat in VALID_CATEGORIES:
            n = store.add_note('s', 'text', category=cat)
            assert n.category == cat

    def test_get_note(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'hi')
        assert store.get_note(n.note_id) is not None

    def test_get_unknown_none(self, tmp_path):
        assert _store(tmp_path).get_note('ghost') is None

    def test_update_text(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'old text')
        updated = store.update_note(n.note_id, text='new text')
        assert updated.text == 'new text'

    def test_update_category(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'text', category='info')
        updated = store.update_note(n.note_id, category='warning')
        assert updated.category == 'warning'

    def test_update_none_fields_unchanged(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'original', category='issue')
        updated = store.update_note(n.note_id)
        assert updated.text == 'original'
        assert updated.category == 'issue'

    def test_update_unknown_returns_none(self, tmp_path):
        assert _store(tmp_path).update_note('ghost') is None

    def test_update_invalid_category_raises(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'text')
        with pytest.raises(ValueError):
            store.update_note(n.note_id, category='bad')

    def test_remove_existing(self, tmp_path):
        store = _store(tmp_path)
        n = store.add_note('etd.pick', 'hi')
        assert store.remove_note(n.note_id) is True
        assert store.get_note(n.note_id) is None

    def test_remove_unknown_false(self, tmp_path):
        assert _store(tmp_path).remove_note('ghost') is False

    def test_note_count(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('a', 'x')
        store.add_note('b', 'y')
        assert store.note_count == 2

    def test_list_all(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('etd.pick', 'n1')
        store.add_note('robot-01', 'n2')
        assert len(store.list_notes()) == 2

    def test_list_filter_subject(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('etd.pick', 'n1')
        store.add_note('robot-01', 'n2')
        results = store.list_notes(subject='etd.pick')
        assert len(results) == 1
        assert results[0].subject == 'etd.pick'

    def test_list_filter_category(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('etd.pick', 'n1', category='info')
        store.add_note('etd.pick', 'n2', category='issue')
        results = store.list_notes(category='issue')
        assert len(results) == 1
        assert results[0].category == 'issue'

    def test_list_filter_both(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('etd.pick', 'a', category='info')
        store.add_note('etd.pick', 'b', category='issue')
        store.add_note('robot-01', 'c', category='info')
        results = store.list_notes(subject='etd.pick', category='info')
        assert len(results) == 1
        assert results[0].text == 'a'

    def test_subjects_sorted(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('robot-01', 'x')
        store.add_note('etd.pick', 'y')
        store.add_note('etd.weld', 'z')
        assert store.subjects() == ['etd.pick', 'etd.weld', 'robot-01']

    def test_subjects_dedup(self, tmp_path):
        store = _store(tmp_path)
        store.add_note('etd.pick', 'a')
        store.add_note('etd.pick', 'b')
        assert store.subjects() == ['etd.pick']

    def test_subjects_empty(self, tmp_path):
        assert _store(tmp_path).subjects() == []


# ── Persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_persists_notes(self, tmp_path):
        p = tmp_path / 'notes'
        n = NoteStore(p).add_note('etd.pick', 'saved text', category='runbook')
        s2 = NoteStore(p)
        n2 = s2.get_note(n.note_id)
        assert n2 is not None
        assert n2.text == 'saved text'
        assert n2.category == 'runbook'

    def test_creates_dir(self, tmp_path):
        s = NoteStore(tmp_path / 'a' / 'b')
        s.add_note('etd.pick', 'hi')
        assert (tmp_path / 'a' / 'b' / 'notes.json').exists()

    def test_corrupt_loads_empty(self, tmp_path):
        (tmp_path / 'notes.json').write_text('bad json')
        s = NoteStore(tmp_path)
        assert s.note_count == 0


# ── REST API ──────────────────────────────────────────────────────────────────

import api.operator_notes as _notes_mod


@pytest.fixture(autouse=True)
def patch_notes_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_notes_mod, '_NOTES_DIR', tmp_path / 'notes')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _add(api_client, subject='etd.pick', text='check', category='info',
         author='anonymous'):
    return api_client.post('/notes', json={
        'subject': subject, 'text': text,
        'category': category, 'author': author,
    })


class TestNotesAPI:
    def test_list_empty(self, api_client):
        r = api_client.get('/notes')
        assert r.status_code == 200
        assert r.json()['note_count'] == 0

    def test_add_201(self, api_client):
        assert _add(api_client).status_code == 201

    def test_add_has_note_id(self, api_client):
        assert 'note_id' in _add(api_client).json()

    def test_add_has_subject(self, api_client):
        assert _add(api_client).json()['subject'] == 'etd.pick'

    def test_add_invalid_category_422(self, api_client):
        r = api_client.post('/notes', json={
            'subject': 'etd.pick', 'text': 'x', 'category': 'bogus',
        })
        assert r.status_code == 422

    def test_list_after_add(self, api_client):
        _add(api_client)
        _add(api_client, subject='robot-01', text='y')
        assert api_client.get('/notes').json()['note_count'] == 2

    def test_list_filter_subject(self, api_client):
        _add(api_client, subject='etd.pick')
        _add(api_client, subject='robot-01')
        r = api_client.get('/notes?subject=etd.pick')
        assert r.json()['note_count'] == 1

    def test_list_filter_category(self, api_client):
        _add(api_client, category='info')
        _add(api_client, category='issue')
        r = api_client.get('/notes?category=issue')
        assert r.json()['note_count'] == 1

    def test_get_found(self, api_client):
        nid = _add(api_client).json()['note_id']
        r = api_client.get(f'/notes/{nid}')
        assert r.status_code == 200
        assert r.json()['note_id'] == nid

    def test_get_404(self, api_client):
        assert api_client.get('/notes/ghost').status_code == 404

    def test_update_200(self, api_client):
        nid = _add(api_client).json()['note_id']
        r = api_client.patch(f'/notes/{nid}', json={'text': 'updated'})
        assert r.status_code == 200
        assert r.json()['text'] == 'updated'

    def test_update_category(self, api_client):
        nid = _add(api_client, category='info').json()['note_id']
        r = api_client.patch(f'/notes/{nid}', json={'category': 'warning'})
        assert r.json()['category'] == 'warning'

    def test_update_404(self, api_client):
        r = api_client.patch('/notes/ghost', json={'text': 'x'})
        assert r.status_code == 404

    def test_update_bad_category_422(self, api_client):
        nid = _add(api_client).json()['note_id']
        r = api_client.patch(f'/notes/{nid}', json={'category': 'bogus'})
        assert r.status_code == 422

    def test_subjects_empty(self, api_client):
        r = api_client.get('/notes/subjects')
        assert r.status_code == 200
        assert r.json()['subject_count'] == 0

    def test_subjects_after_add(self, api_client):
        _add(api_client, subject='etd.pick')
        _add(api_client, subject='robot-01')
        r = api_client.get('/notes/subjects')
        assert set(r.json()['subjects']) == {'etd.pick', 'robot-01'}

    def test_delete_200(self, api_client):
        nid = _add(api_client).json()['note_id']
        assert api_client.delete(f'/notes/{nid}').status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/notes/ghost').status_code == 404

    def test_delete_removes_note(self, api_client):
        nid = _add(api_client).json()['note_id']
        api_client.delete(f'/notes/{nid}')
        assert api_client.get(f'/notes/{nid}').status_code == 404
