"""ETD Skill Rating System REST API router.

Endpoints:
    GET    /ratings                     — list all ratings (?skill_id= filter)
    POST   /ratings                     — add a rating (201)
    GET    /ratings/stats/{skill_id}    — aggregate stats; 404 if no ratings
    GET    /ratings/{rating_id}         — get one rating; 404
    DELETE /ratings/{rating_id}         — remove a rating; 404
    GET    /ratings/skills              — list skill IDs that have ratings
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
from pydantic import BaseModel, field_validator

from marketplace.skill_ratings import RatingStore

ratings_router = APIRouter(prefix='/ratings', tags=['skill-ratings'])

_RATINGS_DIR = ROOT / 'skill_ratings_data'


def _store() -> RatingStore:
    return RatingStore(_RATINGS_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class AddRatingRequest(BaseModel):
    skill_id: str
    rating: int
    comment: str = ''
    operator_id: str = 'anonymous'

    @field_validator('rating')
    @classmethod
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError('rating must be between 1 and 5')
        return v


# ── Routes ────────────────────────────────────────────────────────────────────

@ratings_router.get('')
def list_ratings(skill_id: Optional[str] = None) -> JSONResponse:
    """List all ratings, optionally filtered by skill_id."""
    store = _store()
    entries = store.list_ratings(skill_id=skill_id)
    return JSONResponse(content={
        'rating_count': len(entries),
        'ratings': [e.to_dict() for e in entries],
    })


@ratings_router.post('')
def add_rating(req: AddRatingRequest) -> JSONResponse:
    """Add a rating for a skill. Returns 201 on success."""
    store = _store()
    try:
        entry = store.add_rating(
            req.skill_id,
            req.rating,
            comment=req.comment,
            operator_id=req.operator_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=entry.to_dict(), status_code=201)


@ratings_router.get('/skills')
def rated_skills() -> JSONResponse:
    """Return a sorted list of skill IDs that have at least one rating."""
    store = _store()
    skills = store.rated_skills()
    return JSONResponse(content={'skill_count': len(skills), 'skills': skills})


@ratings_router.get('/stats/{skill_id}')
def rating_stats(skill_id: str) -> JSONResponse:
    """Return aggregate rating stats for a skill. 404 if no ratings exist."""
    store = _store()
    stats = store.get_stats(skill_id)
    if stats is None:
        raise HTTPException(status_code=404,
                            detail=f'No ratings for skill: {skill_id}')
    return JSONResponse(content=stats.to_dict())


@ratings_router.get('/{rating_id}')
def get_rating(rating_id: str) -> JSONResponse:
    """Get a single rating by ID. 404 if not found."""
    store = _store()
    entry = store.get_rating(rating_id)
    if entry is None:
        raise HTTPException(status_code=404,
                            detail=f'Rating not found: {rating_id}')
    return JSONResponse(content=entry.to_dict())


@ratings_router.delete('/{rating_id}')
def remove_rating(rating_id: str) -> JSONResponse:
    """Delete a rating. 404 if not found."""
    store = _store()
    if not store.remove_rating(rating_id):
        raise HTTPException(status_code=404,
                            detail=f'Rating not found: {rating_id}')
    return JSONResponse(content={'deleted': rating_id})
