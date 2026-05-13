"""ETD Skill Maintenance Window REST API router.

Endpoints:
    GET    /maintenance                  — list windows (?skill_id= ?active=true)
    POST   /maintenance                  — schedule window (201; 422 if end<=start)
    GET    /maintenance/check            — is_in_maintenance (?skill_id=&node_id=)
    GET    /maintenance/{window_id}      — get one; 404
    DELETE /maintenance/{window_id}      — remove; 404
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

from marketplace.maintenance import MaintenanceStore

maintenance_router = APIRouter(prefix='/maintenance', tags=['maintenance'])

_MAINTENANCE_DIR = ROOT / 'maintenance_data'


def _store() -> MaintenanceStore:
    return MaintenanceStore(_MAINTENANCE_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class AddWindowRequest(BaseModel):
    skill_id: str
    start_at: str
    end_at: str
    reason: str = ''
    node_id: Optional[str] = None
    created_by: str = 'system'


# ── Routes ────────────────────────────────────────────────────────────────────

@maintenance_router.get('')
def list_windows(
    skill_id: Optional[str] = None,
    active: bool = Query(False, description='Only return currently active windows'),
) -> JSONResponse:
    """List maintenance windows."""
    store = _store()
    windows = store.list_windows(skill_id=skill_id, active_only=active)
    return JSONResponse(content={
        'window_count': len(windows),
        'windows': [w.to_dict() for w in windows],
    })


@maintenance_router.post('')
def add_window(req: AddWindowRequest) -> JSONResponse:
    """Schedule a maintenance window. 422 if end_at ≤ start_at."""
    store = _store()
    try:
        window = store.add_window(
            req.skill_id, req.start_at, req.end_at,
            reason=req.reason, node_id=req.node_id, created_by=req.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=window.to_dict(), status_code=201)


@maintenance_router.get('/check')
def check_maintenance(
    skill_id: str = Query(...),
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Check whether a skill (optionally on a node) is currently in maintenance."""
    store = _store()
    in_maint = store.is_in_maintenance(skill_id, node_id=node_id)
    return JSONResponse(content={
        'skill_id': skill_id,
        'node_id': node_id,
        'in_maintenance': in_maint,
    })


@maintenance_router.get('/{window_id}')
def get_window(window_id: str) -> JSONResponse:
    """Get a maintenance window by ID. 404 if not found."""
    store = _store()
    window = store.get_window(window_id)
    if window is None:
        raise HTTPException(status_code=404,
                            detail=f'Window not found: {window_id}')
    return JSONResponse(content=window.to_dict())


@maintenance_router.delete('/{window_id}')
def remove_window(window_id: str) -> JSONResponse:
    """Remove a maintenance window. 404 if not found."""
    store = _store()
    if not store.remove_window(window_id):
        raise HTTPException(status_code=404,
                            detail=f'Window not found: {window_id}')
    return JSONResponse(content={'deleted': window_id})
