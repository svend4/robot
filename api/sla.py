"""ETD Skill SLA Tracker REST API router.

Endpoints:
    GET    /sla/policies                  — list all SLA policies
    POST   /sla/policies                  — set policy (201 new / 200 update; 422)
    GET    /sla/policies/{skill_id}       — get one; 404
    DELETE /sla/policies/{skill_id}       — remove; 404
    POST   /sla/evaluate/{skill_id}       — evaluate executions against policy; 404
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from marketplace.sla import SLAStore

sla_router = APIRouter(prefix='/sla', tags=['sla'])

_SLA_DIR = ROOT / 'sla_data'


def _store() -> SLAStore:
    return SLAStore(_SLA_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class SetPolicyRequest(BaseModel):
    skill_id: str
    max_p95_ms: Optional[int] = None
    min_success_rate: Optional[float] = None
    window_hours: int = 24

    @field_validator('min_success_rate')
    @classmethod
    def rate_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError('min_success_rate must be between 0.0 and 1.0')
        return v


class EvaluateRequest(BaseModel):
    executions: List[Dict[str, Any]]


# ── Routes ────────────────────────────────────────────────────────────────────

@sla_router.get('/policies')
def list_policies() -> JSONResponse:
    """List all SLA policies."""
    store = _store()
    policies = store.list_policies()
    return JSONResponse(content={
        'policy_count': len(policies),
        'policies': [p.to_dict() for p in policies],
    })


@sla_router.post('/policies')
def set_policy(req: SetPolicyRequest) -> JSONResponse:
    """Create or update an SLA policy. 201 on create, 200 on update."""
    store = _store()
    try:
        policy, created = store.set_policy(
            req.skill_id,
            max_p95_ms=req.max_p95_ms,
            min_success_rate=req.min_success_rate,
            window_hours=req.window_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=policy.to_dict(), status_code=201 if created else 200)


@sla_router.get('/policies/{skill_id}')
def get_policy(skill_id: str) -> JSONResponse:
    """Get an SLA policy by skill ID. 404 if not found."""
    store = _store()
    policy = store.get_policy(skill_id)
    if policy is None:
        raise HTTPException(status_code=404,
                            detail=f'No SLA policy for skill: {skill_id}')
    return JSONResponse(content=policy.to_dict())


@sla_router.delete('/policies/{skill_id}')
def remove_policy(skill_id: str) -> JSONResponse:
    """Remove an SLA policy. 404 if not found."""
    store = _store()
    if not store.remove_policy(skill_id):
        raise HTTPException(status_code=404,
                            detail=f'No SLA policy for skill: {skill_id}')
    return JSONResponse(content={'deleted': skill_id})


@sla_router.post('/evaluate/{skill_id}')
def evaluate(skill_id: str, req: EvaluateRequest) -> JSONResponse:
    """Evaluate executions against the skill's SLA policy. 404 if no policy."""
    store = _store()
    result = store.evaluate(skill_id, req.executions)
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f'No SLA policy for skill: {skill_id}')
    return JSONResponse(content=result.to_dict())
