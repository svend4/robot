"""ETD Skill Configuration Store REST API router.

Endpoints:
    GET    /config/skills                               — list all skills with config
    GET    /config/skills/{skill_id}                    — list all entries for skill
    PUT    /config/skills/{skill_id}                    — set/update one scope entry
    DELETE /config/skills/{skill_id}                    — remove ALL entries for skill
    GET    /config/skills/{skill_id}/effective          — merged effective config
    GET    /config/skills/{skill_id}/scope/{scope}      — get one scope entry; 404
    DELETE /config/skills/{skill_id}/scope/{scope}      — remove one scope; 404
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.skill_config import ConfigStore

router = APIRouter(prefix='/config', tags=['skill-config'])

_CONFIG_DIR = ROOT / 'skill_configs'


def _store() -> ConfigStore:
    return ConfigStore(_CONFIG_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class SetConfigRequest(BaseModel):
    scope: str = '*'
    values: Dict[str, Any]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/skills')
def list_skills() -> JSONResponse:
    """List all skills that have at least one configuration entry."""
    store = _store()
    skills = store.list_skills()
    return JSONResponse(content={
        'skill_count': len(skills),
        'skills': skills,
    })


@router.get('/skills/{skill_id}')
def get_skill_entries(skill_id: str) -> JSONResponse:
    """List all scope entries for a skill."""
    store = _store()
    entries = store.list_entries(skill_id=skill_id)
    return JSONResponse(content={
        'skill_id': skill_id,
        'entry_count': len(entries),
        'entries': [e.to_dict() for e in entries],
    })


@router.put('/skills/{skill_id}')
def set_config(skill_id: str, req: SetConfigRequest) -> JSONResponse:
    """Set or update the configuration for (skill_id, scope).

    Returns 201 on create, 200 on update.
    """
    store = _store()
    existed = store.get(skill_id, req.scope) is not None
    entry = store.set(skill_id, req.scope, req.values)
    return JSONResponse(
        content=entry.to_dict(),
        status_code=200 if existed else 201,
    )


@router.delete('/skills/{skill_id}')
def remove_skill_config(skill_id: str) -> JSONResponse:
    """Remove ALL configuration entries for a skill."""
    store = _store()
    count = store.remove_skill(skill_id)
    return JSONResponse(content={'skill_id': skill_id, 'removed_count': count})


@router.get('/skills/{skill_id}/effective')
def get_effective(
    skill_id: str,
    station_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Return the merged effective configuration for a skill.

    Merge order: default (*) < station override < node override.
    """
    store = _store()
    effective = store.get_effective(skill_id, station_id=station_id,
                                    node_id=node_id)
    return JSONResponse(content={
        'skill_id': skill_id,
        'station_id': station_id,
        'node_id': node_id,
        'effective': effective,
    })


@router.get('/skills/{skill_id}/scope/{scope:path}')
def get_scope_entry(skill_id: str, scope: str) -> JSONResponse:
    """Get one (skill_id, scope) entry. 404 if not found."""
    store = _store()
    entry = store.get(skill_id, scope)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f'No config for skill={skill_id} scope={scope}',
        )
    return JSONResponse(content=entry.to_dict())


@router.delete('/skills/{skill_id}/scope/{scope:path}')
def remove_scope_entry(skill_id: str, scope: str) -> JSONResponse:
    """Remove one (skill_id, scope) entry. 404 if not found."""
    store = _store()
    if not store.remove(skill_id, scope):
        raise HTTPException(
            status_code=404,
            detail=f'No config for skill={skill_id} scope={scope}',
        )
    return JSONResponse(content={'skill_id': skill_id, 'scope': scope,
                                  'removed': True})
