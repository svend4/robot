"""ETD Skill Tag System REST API router.

Endpoints (tags):
    GET    /tags                         — list all tags
    POST   /tags                         — create tag (201; 200 if exists)
    GET    /tags/{tag_id}                — get one tag; 404
    PATCH  /tags/{tag_id}                — update color/description; 404
    DELETE /tags/{tag_id}                — delete + remove from all skills; 404

Endpoints (taggings — skill ↔ tag mappings):
    GET    /taggings/by-tag/{tag_id}     — skills that have this tag
    GET    /taggings/{skill_id}          — tags on a skill
    POST   /taggings/{skill_id}/{tag_id} — tag a skill (201); 404 unknown tag
    DELETE /taggings/{skill_id}/{tag_id} — untag; 404 if not tagged
    GET    /taggings                     — all skill→tag mappings
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

from marketplace.skill_tags import TagStore

tags_router = APIRouter(prefix='/tags', tags=['skill-tags'])
taggings_router = APIRouter(prefix='/taggings', tags=['skill-tags'])

_TAGS_DIR = ROOT / 'skill_tags'


def _store() -> TagStore:
    return TagStore(_TAGS_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class CreateTagRequest(BaseModel):
    tag_id: str
    color: Optional[str] = None
    description: str = ''


class UpdateTagRequest(BaseModel):
    color: Optional[str] = None
    description: Optional[str] = None


# ── Tag routes ────────────────────────────────────────────────────────────────

@tags_router.get('')
def list_tags() -> JSONResponse:
    """List all defined tags."""
    store = _store()
    tags = store.list_tags()
    return JSONResponse(content={
        'tag_count': len(tags),
        'tags': [t.to_dict() for t in tags],
    })


@tags_router.post('')
def create_tag(req: CreateTagRequest) -> JSONResponse:
    """Create a tag. Returns 201 on create, 200 if already exists."""
    store = _store()
    existed = store.get_tag(req.tag_id) is not None
    entry = store.create_tag(req.tag_id, color=req.color,
                             description=req.description)
    return JSONResponse(
        content=entry.to_dict(),
        status_code=200 if existed else 201,
    )


@tags_router.get('/{tag_id}')
def get_tag(tag_id: str) -> JSONResponse:
    """Get a tag by ID. 404 if not found."""
    store = _store()
    entry = store.get_tag(tag_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f'Tag not found: {tag_id}')
    return JSONResponse(content=entry.to_dict())


@tags_router.patch('/{tag_id}')
def update_tag(tag_id: str, req: UpdateTagRequest) -> JSONResponse:
    """Update a tag's color and/or description. 404 if not found."""
    store = _store()
    entry = store.update_tag(tag_id, color=req.color,
                             description=req.description)
    if entry is None:
        raise HTTPException(status_code=404, detail=f'Tag not found: {tag_id}')
    return JSONResponse(content=entry.to_dict())


@tags_router.delete('/{tag_id}')
def delete_tag(tag_id: str) -> JSONResponse:
    """Delete a tag and remove it from all skill mappings. 404 if not found."""
    store = _store()
    if not store.delete_tag(tag_id):
        raise HTTPException(status_code=404, detail=f'Tag not found: {tag_id}')
    return JSONResponse(content={'deleted': tag_id})


# ── Tagging routes ────────────────────────────────────────────────────────────

@taggings_router.get('')
def list_all_taggings() -> JSONResponse:
    """Return all skill→tag mappings."""
    store = _store()
    mappings = store.list_skill_tags()
    return JSONResponse(content={
        'tagged_skill_count': len(mappings),
        'mappings': mappings,
    })


@taggings_router.get('/by-tag/{tag_id}')
def skills_by_tag(tag_id: str) -> JSONResponse:
    """List skills that have a given tag. 404 if tag is unknown."""
    store = _store()
    if store.get_tag(tag_id) is None:
        raise HTTPException(status_code=404, detail=f'Tag not found: {tag_id}')
    skills = store.get_skills_by_tag(tag_id)
    return JSONResponse(content={
        'tag_id': tag_id,
        'skill_count': len(skills),
        'skills': skills,
    })


@taggings_router.get('/{skill_id}')
def skill_tags(skill_id: str) -> JSONResponse:
    """List tags applied to a skill."""
    store = _store()
    tags = store.get_skill_tags(skill_id)
    return JSONResponse(content={
        'skill_id': skill_id,
        'tag_count': len(tags),
        'tags': tags,
    })


@taggings_router.post('/{skill_id}/{tag_id}')
def tag_skill(skill_id: str, tag_id: str) -> JSONResponse:
    """Apply a tag to a skill. 201 on new; 200 if already tagged. 404 unknown tag."""
    store = _store()
    try:
        added = store.tag_skill(skill_id, tag_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f'Tag not found: {tag_id}')
    return JSONResponse(
        content={'skill_id': skill_id, 'tag_id': tag_id, 'added': added},
        status_code=201 if added else 200,
    )


@taggings_router.delete('/{skill_id}/{tag_id}')
def untag_skill(skill_id: str, tag_id: str) -> JSONResponse:
    """Remove a tag from a skill. 404 if the mapping does not exist."""
    store = _store()
    if not store.untag_skill(skill_id, tag_id):
        raise HTTPException(
            status_code=404,
            detail=f'Skill {skill_id!r} does not have tag {tag_id!r}',
        )
    return JSONResponse(content={'skill_id': skill_id, 'tag_id': tag_id,
                                  'removed': True})
