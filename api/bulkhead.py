"""ETD Skill Bulkhead REST API router.

Endpoints:
    GET  /bulkhead/states                 — list all bulkhead states
    GET  /bulkhead/states/{skill_id}      — get state for one skill; 404
    DELETE /bulkhead/states/{skill_id}    — remove state; 404
    POST /bulkhead/acquire                — acquire a concurrency slot
    POST /bulkhead/release                — release a concurrency slot
    POST /bulkhead/reset/{skill_id}       — reset active_count to 0; 404
    GET  /bulkhead/configs                — list all per-skill configs
    GET  /bulkhead/config                 — default config
    PUT  /bulkhead/configs/{skill_id}     — set per-skill config (201/200)
    DELETE /bulkhead/configs/{skill_id}   — remove per-skill config; 404
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.bulkhead import Bulkhead, BulkheadConfig

router = APIRouter(prefix='/bulkhead', tags=['bulkhead'])

_BULKHEAD_DIR = ROOT / 'bulkhead'


def _bh() -> Bulkhead:
    return Bulkhead(data_dir=_BULKHEAD_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class SlotRef(BaseModel):
    skill_id: str
    node_id: str = '*'


class ConfigRequest(BaseModel):
    max_concurrent: int = 10


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/states')
def list_states() -> JSONResponse:
    """List all bulkhead states."""
    bh = _bh()
    states = bh.list_states()
    return JSONResponse(content={
        'state_count': len(states),
        'states': [s.to_dict() for s in states],
    })


@router.get('/states/{skill_id}')
def get_state(skill_id: str, node_id: str = '*') -> JSONResponse:
    """Get bulkhead state for one skill. 404 if never used."""
    bh = _bh()
    state = bh.get_state(skill_id, node_id)
    if state is None:
        raise HTTPException(status_code=404,
                            detail=f'No bulkhead state for: {skill_id}')
    return JSONResponse(content=state.to_dict())


@router.delete('/states/{skill_id}')
def remove_state(skill_id: str, node_id: str = '*') -> JSONResponse:
    """Remove the bulkhead state record. 404 if not found."""
    bh = _bh()
    if not bh._store.remove_state(skill_id, node_id):
        raise HTTPException(status_code=404,
                            detail=f'No bulkhead state for: {skill_id}')
    return JSONResponse(content={'removed': skill_id})


@router.post('/acquire')
def acquire(req: SlotRef) -> JSONResponse:
    """Attempt to acquire a concurrency slot for a skill."""
    bh = _bh()
    result = bh.acquire(req.skill_id, req.node_id)
    return JSONResponse(content=result.to_dict())


@router.post('/release')
def release(req: SlotRef) -> JSONResponse:
    """Release a previously acquired concurrency slot. Returns released flag."""
    bh = _bh()
    released = bh.release(req.skill_id, req.node_id)
    return JSONResponse(content={
        'released': released,
        'skill_id': req.skill_id,
        'node_id': req.node_id,
    })


@router.post('/reset/{skill_id}')
def reset(skill_id: str, node_id: str = '*') -> JSONResponse:
    """Reset active_count to 0. 404 if bulkhead state not found."""
    bh = _bh()
    if not bh.reset(skill_id, node_id):
        raise HTTPException(status_code=404,
                            detail=f'No bulkhead state for: {skill_id}')
    state = bh.get_state(skill_id, node_id)
    return JSONResponse(content=state.to_dict())


@router.get('/config')
def get_default_config() -> JSONResponse:
    """Return the default bulkhead configuration."""
    return JSONResponse(content=BulkheadConfig().to_dict())


@router.get('/configs')
def list_configs() -> JSONResponse:
    """List all per-skill bulkhead configurations."""
    bh = _bh()
    configs = bh.list_configs()
    return JSONResponse(content={
        'config_count': len(configs),
        'configs': [
            {'skill_id': s, 'config': c.to_dict()}
            for s, c in configs.items()
        ],
    })


@router.put('/configs/{skill_id}')
def set_config(skill_id: str, req: ConfigRequest) -> JSONResponse:
    """Set or replace the bulkhead config for a skill."""
    try:
        cfg = BulkheadConfig(max_concurrent=req.max_concurrent)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    bh = _bh()
    existed = bh._store.get_config(skill_id) is not None
    bh.set_config(skill_id, cfg)
    return JSONResponse(
        content={'skill_id': skill_id, 'config': cfg.to_dict()},
        status_code=200 if existed else 201,
    )


@router.delete('/configs/{skill_id}')
def remove_config(skill_id: str) -> JSONResponse:
    """Remove per-skill bulkhead config. 404 if not found."""
    bh = _bh()
    if not bh.remove_config(skill_id):
        raise HTTPException(status_code=404,
                            detail=f'No bulkhead config for: {skill_id}')
    return JSONResponse(content={'removed': skill_id})
