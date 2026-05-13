"""ETD Circuit Breaker REST API router.

Endpoints:
    GET  /circuit/breakers                — list all circuit breaker states
    GET  /circuit/breakers/{skill_id}     — get state for one skill; creates if absent
    DELETE /circuit/breakers/{skill_id}   — remove a circuit breaker; 404
    POST /circuit/check                   — check if execution is allowed
    POST /circuit/success                 — record a successful execution
    POST /circuit/failure                 — record a failed execution
    POST /circuit/reset/{skill_id}        — manually reset to closed; 404
    GET  /circuit/config                  — get default config
    PUT  /circuit/config/{skill_id}       — set per-skill config
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

from marketplace.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)

router = APIRouter(prefix='/circuit', tags=['circuit-breaker'])

_CIRCUIT_DIR = ROOT / 'circuits'


def _cb() -> CircuitBreaker:
    return CircuitBreaker(data_dir=_CIRCUIT_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class ExecutionRef(BaseModel):
    skill_id: str
    node_id: str = '*'


class ConfigRequest(BaseModel):
    failure_threshold: int = 5
    failure_rate_threshold: float = 0.5
    min_executions: int = 3
    reset_timeout_seconds: int = 60
    half_open_max_calls: int = 2


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/breakers')
def list_breakers() -> JSONResponse:
    """List all known circuit breaker states."""
    cb = _cb()
    states = cb.list_breakers()
    return JSONResponse(content={
        'breaker_count': len(states),
        'breakers': [s.to_dict() for s in states],
    })


@router.get('/breakers/{skill_id}')
def get_breaker(skill_id: str, node_id: str = '*') -> JSONResponse:
    """Get circuit breaker state for one skill (creates a closed one if absent)."""
    cb = _cb()
    state = cb._store.get_or_create(skill_id, node_id)
    cb._store.save(state)
    return JSONResponse(content=state.to_dict())


@router.delete('/breakers/{skill_id}')
def remove_breaker(skill_id: str, node_id: str = '*') -> JSONResponse:
    """Remove a circuit breaker record. 404 if not found."""
    cb = _cb()
    if not cb.remove(skill_id, node_id):
        raise HTTPException(status_code=404,
                            detail=f'No circuit breaker for: {skill_id}')
    return JSONResponse(content={'removed': skill_id})


@router.post('/check')
def check_execution(req: ExecutionRef) -> JSONResponse:
    """Check whether an execution is allowed without recording the call."""
    cb = _cb()
    result = cb.allow_execution(req.skill_id, req.node_id)
    return JSONResponse(content=result.to_dict())


@router.post('/success')
def record_success(req: ExecutionRef) -> JSONResponse:
    """Record a successful execution."""
    cb = _cb()
    state = cb.record_success(req.skill_id, req.node_id)
    return JSONResponse(content=state.to_dict())


@router.post('/failure')
def record_failure(req: ExecutionRef) -> JSONResponse:
    """Record a failed execution."""
    cb = _cb()
    state = cb.record_failure(req.skill_id, req.node_id)
    return JSONResponse(content=state.to_dict())


@router.post('/reset/{skill_id}')
def reset_circuit(skill_id: str, node_id: str = '*') -> JSONResponse:
    """Manually reset a circuit to closed. 404 if circuit not found."""
    cb = _cb()
    if not cb.reset(skill_id, node_id):
        raise HTTPException(status_code=404,
                            detail=f'No circuit breaker for: {skill_id}')
    state = cb.get_state(skill_id, node_id)
    return JSONResponse(content=state.to_dict())


@router.get('/config')
def get_default_config() -> JSONResponse:
    """Return the default circuit breaker configuration."""
    return JSONResponse(content=CircuitBreakerConfig().to_dict())


@router.put('/config/{skill_id}', status_code=200)
def set_skill_config(skill_id: str, req: ConfigRequest) -> JSONResponse:
    """Set a per-skill circuit breaker configuration."""
    cfg = CircuitBreakerConfig(
        failure_threshold=req.failure_threshold,
        failure_rate_threshold=req.failure_rate_threshold,
        min_executions=req.min_executions,
        reset_timeout_seconds=req.reset_timeout_seconds,
        half_open_max_calls=req.half_open_max_calls,
    )
    return JSONResponse(content={'skill_id': skill_id, 'config': cfg.to_dict()})
