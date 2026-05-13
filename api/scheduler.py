"""ETD Skill Execution Scheduler REST API router.

Endpoints:
    POST /scheduler/jobs                    — create a scheduled job
    GET  /scheduler/jobs                    — list jobs (filters: status, skill_id, node_id)
    GET  /scheduler/jobs/{job_id}           — get one; 404 if unknown
    DELETE /scheduler/jobs/{job_id}         — remove; 404 if unknown
    PUT  /scheduler/jobs/{job_id}/pause     — pause active job; 409 if not active
    PUT  /scheduler/jobs/{job_id}/resume    — resume paused job; 409 if not paused
    GET  /scheduler/due                     — jobs due to run right now
    POST /scheduler/jobs/{job_id}/run       — record a run result
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

from marketplace.scheduler import SkillScheduler

router = APIRouter(prefix='/scheduler', tags=['scheduler'])

_SCHED_DIR = ROOT / 'scheduler'


def _sched() -> SkillScheduler:
    return SkillScheduler(_SCHED_DIR)


def _get_or_404(sched: SkillScheduler, job_id: str):
    job = sched.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f'Job not found: {job_id}')
    return job


# ── Models ────────────────────────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    skill_id: str
    node_id: str
    station_id: str = 'default'
    schedule_type: str = 'interval'   # 'interval' | 'once'
    interval_minutes: int = 60
    run_at: Optional[str] = None      # ISO datetime for 'once' jobs
    metadata: Optional[Dict[str, Any]] = None


class RecordRunRequest(BaseModel):
    success: bool
    duration_ms: int = 0
    error: str = ''


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post('/jobs', status_code=201)
def create_job(req: CreateJobRequest) -> JSONResponse:
    """Create a new scheduled job."""
    sched = _sched()
    try:
        job = sched.add_job(
            skill_id=req.skill_id,
            node_id=req.node_id,
            station_id=req.station_id,
            schedule_type=req.schedule_type,
            interval_minutes=req.interval_minutes,
            run_at=req.run_at,
            metadata=req.metadata or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=job.to_dict(), status_code=201)


@router.get('/jobs')
def list_jobs(
    status: Optional[str] = Query(None),
    skill_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
) -> JSONResponse:
    """List scheduled jobs with optional filters."""
    sched = _sched()
    jobs = sched.list_jobs(status=status, skill_id=skill_id, node_id=node_id)
    return JSONResponse(content={
        'count': len(jobs),
        'jobs': [j.to_dict() for j in jobs],
    })


@router.get('/jobs/{job_id}')
def get_job(job_id: str) -> JSONResponse:
    """Get one scheduled job by ID."""
    return JSONResponse(content=_get_or_404(_sched(), job_id).to_dict())


@router.delete('/jobs/{job_id}')
def remove_job(job_id: str) -> JSONResponse:
    """Remove a scheduled job."""
    sched = _sched()
    _get_or_404(sched, job_id)
    sched.remove_job(job_id)
    return JSONResponse(content={'removed': job_id})


@router.put('/jobs/{job_id}/pause')
def pause_job(job_id: str) -> JSONResponse:
    """Pause an active scheduled job."""
    sched = _sched()
    job = _get_or_404(sched, job_id)
    if not sched.pause_job(job_id):
        raise HTTPException(status_code=409,
                            detail=f'Job {job_id!r} is not active (status={job.status!r}).')
    return JSONResponse(content=sched.get_job(job_id).to_dict())


@router.put('/jobs/{job_id}/resume')
def resume_job(job_id: str) -> JSONResponse:
    """Resume a paused scheduled job."""
    sched = _sched()
    job = _get_or_404(sched, job_id)
    if not sched.resume_job(job_id):
        raise HTTPException(status_code=409,
                            detail=f'Job {job_id!r} is not paused (status={job.status!r}).')
    return JSONResponse(content=sched.get_job(job_id).to_dict())


@router.get('/due')
def due_jobs() -> JSONResponse:
    """Return jobs that are due to run right now."""
    sched = _sched()
    jobs = sched.due_jobs()
    return JSONResponse(content={
        'count': len(jobs),
        'jobs': [j.to_dict() for j in jobs],
    })


@router.post('/jobs/{job_id}/run')
def record_run(job_id: str, req: RecordRunRequest) -> JSONResponse:
    """Record a completed execution for a scheduled job."""
    sched = _sched()
    _get_or_404(sched, job_id)
    result = sched.record_run(
        job_id=job_id,
        success=req.success,
        duration_ms=req.duration_ms,
        error=req.error,
    )
    return JSONResponse(content=result.to_dict())
