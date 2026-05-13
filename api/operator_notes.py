"""ETD Operator Notes REST API router.

Endpoints:
    GET    /notes                  — list notes (?subject= ?category=)
    POST   /notes                  — add note (201; 422 unknown category)
    GET    /notes/subjects         — sorted list of subjects that have notes
    GET    /notes/{note_id}        — get one; 404
    PATCH  /notes/{note_id}        — update text/category; 404; 422 bad category
    DELETE /notes/{note_id}        — remove; 404
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.operator_notes import NoteStore, VALID_CATEGORIES

notes_router = APIRouter(prefix='/notes', tags=['operator-notes'])

_NOTES_DIR = ROOT / 'operator_notes_data'


def _store() -> NoteStore:
    return NoteStore(_NOTES_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class AddNoteRequest(BaseModel):
    subject: str
    text: str
    category: str = 'info'
    author: str = 'anonymous'


class UpdateNoteRequest(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@notes_router.get('')
def list_notes(
    subject: Optional[str] = None,
    category: Optional[str] = None,
) -> JSONResponse:
    """List notes, optionally filtered by subject and/or category."""
    store = _store()
    notes = store.list_notes(subject=subject, category=category)
    return JSONResponse(content={
        'note_count': len(notes),
        'notes': [n.to_dict() for n in notes],
    })


@notes_router.post('')
def add_note(req: AddNoteRequest) -> JSONResponse:
    """Add an operator note. 422 for unknown category."""
    store = _store()
    try:
        note = store.add_note(req.subject, req.text,
                              category=req.category, author=req.author)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=note.to_dict(), status_code=201)


@notes_router.get('/subjects')
def list_subjects() -> JSONResponse:
    """Return a sorted list of subjects that have at least one note."""
    store = _store()
    subj = store.subjects()
    return JSONResponse(content={'subject_count': len(subj), 'subjects': subj})


@notes_router.get('/{note_id}')
def get_note(note_id: str) -> JSONResponse:
    """Get a note by ID. 404 if not found."""
    store = _store()
    note = store.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f'Note not found: {note_id}')
    return JSONResponse(content=note.to_dict())


@notes_router.patch('/{note_id}')
def update_note(note_id: str, req: UpdateNoteRequest) -> JSONResponse:
    """Update a note's text and/or category. 404 if not found; 422 bad category."""
    store = _store()
    try:
        note = store.update_note(note_id, text=req.text, category=req.category)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if note is None:
        raise HTTPException(status_code=404, detail=f'Note not found: {note_id}')
    return JSONResponse(content=note.to_dict())


@notes_router.delete('/{note_id}')
def remove_note(note_id: str) -> JSONResponse:
    """Delete a note. 404 if not found."""
    store = _store()
    if not store.remove_note(note_id):
        raise HTTPException(status_code=404, detail=f'Note not found: {note_id}')
    return JSONResponse(content={'deleted': note_id})
