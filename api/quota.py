"""ETD Execution Quota REST API router.

Endpoints:
    POST /quota/policies                  — create or update a policy
    GET  /quota/policies                  — list all policies
    GET  /quota/policies/{skill_id}       — get policy for a skill (node_id=*)
    DELETE /quota/policies/{skill_id}     — remove policy (node_id=*)
    POST /quota/check                     — check if execution is allowed
    GET  /quota/usage                     — rolling-window usage summary
    POST /quota/record                    — record one execution
    DELETE /quota/usage                   — clear usage counters
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.quota_manager import QuotaManager, QuotaPolicy

router = APIRouter(prefix='/quota', tags=['quota'])

_QUOTA_DIR = ROOT / 'quota'


def _mgr() -> QuotaManager:
    return QuotaManager(_QUOTA_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class PolicyRequest(BaseModel):
    skill_id: str
    node_id: str = '*'
    max_per_hour: Optional[int] = None
    max_per_day: Optional[int] = None
    burst_allowance: int = 0
    enabled: bool = True


class CheckRequest(BaseModel):
    skill_id: str
    node_id: str = '*'


class RecordRequest(BaseModel):
    skill_id: str
    node_id: str = '*'
    timestamp: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post('/policies', status_code=201)
def set_policy(req: PolicyRequest) -> JSONResponse:
    """Create or update a quota policy."""
    mgr = _mgr()
    policy = QuotaPolicy(
        skill_id=req.skill_id,
        node_id=req.node_id,
        max_per_hour=req.max_per_hour,
        max_per_day=req.max_per_day,
        burst_allowance=req.burst_allowance,
        enabled=req.enabled,
    )
    mgr.set_policy(policy)
    return JSONResponse(content=policy.to_dict(), status_code=201)


@router.get('/policies')
def list_policies() -> JSONResponse:
    """List all quota policies."""
    mgr = _mgr()
    policies = mgr.list_policies()
    return JSONResponse(content={
        'count': len(policies),
        'policies': [p.to_dict() for p in policies],
    })


@router.get('/policies/{skill_id:path}')
def get_policy(skill_id: str,
               node_id: str = Query('*')) -> JSONResponse:
    """Get a specific quota policy."""
    mgr = _mgr()
    policy = mgr.get_policy(skill_id, node_id)
    if policy is None:
        raise HTTPException(status_code=404,
                            detail=f'No policy for skill: {skill_id}')
    return JSONResponse(content=policy.to_dict())


@router.delete('/policies/{skill_id:path}')
def remove_policy(skill_id: str,
                  node_id: str = Query('*')) -> JSONResponse:
    """Remove a quota policy."""
    mgr = _mgr()
    removed = mgr.remove_policy(skill_id, node_id)
    if not removed:
        raise HTTPException(status_code=404,
                            detail=f'No policy for skill: {skill_id}')
    return JSONResponse(content={'removed': skill_id, 'node_id': node_id})


@router.post('/check')
def check_quota(req: CheckRequest) -> JSONResponse:
    """Check whether an execution would be allowed under the current policy."""
    mgr = _mgr()
    result = mgr.check(req.skill_id, req.node_id)
    return JSONResponse(content=result.to_dict())


@router.get('/usage')
def get_usage(
    skill_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Return rolling-window usage counters, optionally filtered."""
    mgr = _mgr()
    rows = mgr.usage(skill_id=skill_id, node_id=node_id)
    return JSONResponse(content={'count': len(rows), 'usage': rows})


@router.post('/record', status_code=201)
def record_execution(req: RecordRequest) -> JSONResponse:
    """Record one execution for quota tracking."""
    mgr = _mgr()
    mgr.record(req.skill_id, req.node_id, timestamp=req.timestamp)
    return JSONResponse(
        content={'recorded': True, 'skill_id': req.skill_id,
                 'node_id': req.node_id},
        status_code=201,
    )


@router.delete('/usage')
def clear_usage(
    skill_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """Clear usage counters (all, or filtered by skill/node)."""
    mgr = _mgr()
    cleared = mgr.clear_usage(skill_id=skill_id, node_id=node_id)
    return JSONResponse(content={'cleared': cleared})
