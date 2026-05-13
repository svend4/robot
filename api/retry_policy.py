"""ETD Skill Retry Policy REST API router.

Endpoints:
    GET  /retry/policies               — list all per-skill policies
    GET  /retry/policies/{skill_id}    — get policy; returns default if none set
    PUT  /retry/policies/{skill_id}    — set per-skill policy (201 on create)
    DELETE /retry/policies/{skill_id}  — remove; 404
    POST /retry/advise                 — should_retry decision for skill + attempt
    GET  /retry/config                 — default retry config
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.retry_policy import (
    EXPONENTIAL,
    RetryConfig,
    RetryEngine,
)

router = APIRouter(prefix='/retry', tags=['retry-policy'])

_RETRY_DIR = ROOT / 'retry'


def _engine() -> RetryEngine:
    return RetryEngine(data_dir=_RETRY_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class PolicyRequest(BaseModel):
    max_attempts: int = 3
    backoff: str = EXPONENTIAL
    base_delay_ms: int = 500
    max_delay_ms: int = 30_000
    jitter_ms: int = 100
    retryable_statuses: List[str] = ['failed', 'aborted']


class AdviseRequest(BaseModel):
    skill_id: str
    attempt: int
    last_status: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/config')
def get_default_config() -> JSONResponse:
    """Return the default (fallback) retry configuration."""
    return JSONResponse(content=RetryConfig().to_dict())


@router.get('/policies')
def list_policies() -> JSONResponse:
    """List all skills that have an explicit retry policy."""
    engine = _engine()
    policies = engine.list_policies()
    return JSONResponse(content={
        'policy_count': len(policies),
        'policies': [
            {'skill_id': s, 'config': c.to_dict()}
            for s, c in policies.items()
        ],
    })


@router.get('/policies/{skill_id}')
def get_policy(skill_id: str) -> JSONResponse:
    """Return the retry policy for a skill (default config if none registered)."""
    engine = _engine()
    cfg = engine.get_config(skill_id)
    explicit = engine._store.get(skill_id) is not None
    return JSONResponse(content={
        'skill_id': skill_id,
        'explicit': explicit,
        'config': cfg.to_dict(),
    })


@router.put('/policies/{skill_id}')
def set_policy(skill_id: str, req: PolicyRequest) -> JSONResponse:
    """Set or replace the retry policy for a skill."""
    try:
        cfg = RetryConfig(
            max_attempts=req.max_attempts,
            backoff=req.backoff,
            base_delay_ms=req.base_delay_ms,
            max_delay_ms=req.max_delay_ms,
            jitter_ms=req.jitter_ms,
            retryable_statuses=req.retryable_statuses,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    engine = _engine()
    existed = engine._store.get(skill_id) is not None
    engine.set_policy(skill_id, cfg)
    return JSONResponse(
        content={'skill_id': skill_id, 'config': cfg.to_dict()},
        status_code=200 if existed else 201,
    )


@router.delete('/policies/{skill_id}')
def remove_policy(skill_id: str) -> JSONResponse:
    """Remove the explicit retry policy for a skill. 404 if not found."""
    engine = _engine()
    if not engine.remove_policy(skill_id):
        raise HTTPException(status_code=404,
                            detail=f'No retry policy for: {skill_id}')
    return JSONResponse(content={'removed': skill_id})


@router.post('/advise')
def advise(req: AdviseRequest) -> JSONResponse:
    """Return a retry decision for a given skill, attempt, and outcome status."""
    engine = _engine()
    decision = engine.should_retry(
        req.skill_id, req.attempt, req.last_status,
    )
    return JSONResponse(content=decision.to_dict())
