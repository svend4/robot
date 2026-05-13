"""ETD Skill Feature Flag System REST API router.

Endpoints:
    GET    /flags                          — list all flags (?skill_id= filter)
    POST   /flags                          — set a flag (201 new / 200 update)
    GET    /flags/resolve                  — resolve with cascade (?skill_id=&flag_key=&node_id=)
    GET    /flags/{skill_id}/{flag_key}    — exact entry (?node_id=); 404
    DELETE /flags/{skill_id}/{flag_key}    — remove (?node_id=); 404
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.feature_flags import FeatureFlagStore

flags_router = APIRouter(prefix='/flags', tags=['feature-flags'])

_FLAGS_DIR = ROOT / 'feature_flags_data'


def _store() -> FeatureFlagStore:
    return FeatureFlagStore(_FLAGS_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class SetFlagRequest(BaseModel):
    skill_id: str
    flag_key: str
    enabled: bool
    node_id: Optional[str] = None
    description: str = ''


# ── Routes ────────────────────────────────────────────────────────────────────

@flags_router.get('')
def list_flags(skill_id: Optional[str] = None) -> JSONResponse:
    """List all flags, optionally filtered by skill_id."""
    store = _store()
    entries = store.list_flags(skill_id=skill_id)
    return JSONResponse(content={
        'flag_count': len(entries),
        'flags': [e.to_dict() for e in entries],
    })


@flags_router.post('')
def set_flag(req: SetFlagRequest) -> JSONResponse:
    """Create or update a flag. Returns 201 on create, 200 on update."""
    store = _store()
    entry, created = store.set_flag(
        req.skill_id, req.flag_key, req.enabled,
        node_id=req.node_id, description=req.description,
    )
    return JSONResponse(content=entry.to_dict(), status_code=201 if created else 200)


@flags_router.get('/resolve')
def resolve_flag(
    skill_id: str = Query(...),
    flag_key: str = Query(...),
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Resolve a flag with the full cascade. Returns enabled state and resolution source."""
    store = _store()
    enabled = store.is_enabled(skill_id, flag_key, node_id=node_id)
    source = store.resolve_source(skill_id, flag_key, node_id=node_id)
    return JSONResponse(content={
        'skill_id': skill_id,
        'flag_key': flag_key,
        'node_id': node_id,
        'enabled': enabled,
        'resolved_from': source,
    })


@flags_router.get('/{skill_id}/{flag_key}')
def get_flag(
    skill_id: str,
    flag_key: str,
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Get an exact flag entry. 404 if not found."""
    store = _store()
    entry = store.get_flag(skill_id, flag_key, node_id=node_id)
    if entry is None:
        raise HTTPException(status_code=404,
                            detail=f'Flag not found: {skill_id}/{flag_key}')
    return JSONResponse(content=entry.to_dict())


@flags_router.delete('/{skill_id}/{flag_key}')
def remove_flag(
    skill_id: str,
    flag_key: str,
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Remove an exact flag entry. 404 if not found."""
    store = _store()
    if not store.remove_flag(skill_id, flag_key, node_id=node_id):
        raise HTTPException(status_code=404,
                            detail=f'Flag not found: {skill_id}/{flag_key}')
    return JSONResponse(content={'deleted': f'{skill_id}/{flag_key}',
                                 'node_id': node_id})
