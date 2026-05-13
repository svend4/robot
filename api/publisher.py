"""ETD Publisher Portal API router — skill submission and review endpoints.

Mount into the main FastAPI app via::

    from api.publisher import router as publisher_router
    app.include_router(publisher_router)

Endpoints
---------
POST /publisher/submit                          Submit a package for review
GET  /publisher/submissions                     List all submissions
GET  /publisher/submission/{id}                 Get one submission
POST /publisher/submission/{id}/approve         Approve (admin)
POST /publisher/submission/{id}/reject          Reject (admin)
POST /publisher/submission/{id}/revision        Request revision (admin)
POST /publisher/submission/{id}/resubmit        Re-run pipeline after fixes
GET  /publisher/stats                           Submission statistics
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from marketplace.publisher_portal import PublisherPortal, SubmissionRecord

router = APIRouter(prefix='/publisher', tags=['publisher'])

_portal = PublisherPortal(ROOT)


# ── Request / response models ─────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    package_path: str
    publisher: str


class DecisionRequest(BaseModel):
    reason: str = ''
    decided_by: str = 'admin'


class RejectRequest(BaseModel):
    reason: str
    decided_by: str = 'admin'


class RevisionRequest(BaseModel):
    reason: str
    decided_by: str = 'admin'


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post('/submit', summary='Submit a skill package for review')
def submit(req: SubmitRequest) -> Dict[str, Any]:
    """Submit a local skill package path for automated review.

    The ``ReviewPipeline`` runs immediately. Packages that pass all stages and
    do not require human review are **auto-approved**. Others enter ``in_review``
    status awaiting an admin decision.
    """
    p = Path(req.package_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f'package path not found: {req.package_path}')
    rec = _portal.submit(p, req.publisher)
    return rec.to_dict()


@router.get('/submissions', summary='List submissions')
def list_submissions(
    publisher: Optional[str] = Query(None, description='Filter by publisher'),
    status: Optional[str] = Query(None, description='Filter by status'),
    skill_id: Optional[str] = Query(None, description='Filter by skill_id'),
) -> List[Dict[str, Any]]:
    """Return all submissions, optionally filtered by publisher, status, or skill_id."""
    recs = _portal.list_submissions(publisher=publisher, status=status, skill_id=skill_id)
    return [r.to_dict() for r in recs]


@router.get('/submission/{submission_id}', summary='Get one submission')
def get_submission(submission_id: str) -> Dict[str, Any]:
    """Return the full submission record including review results."""
    rec = _portal.get_submission(submission_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f'submission {submission_id!r} not found')
    return rec.to_dict()


@router.post('/submission/{submission_id}/approve', summary='Approve a submission')
def approve(submission_id: str, req: DecisionRequest) -> Dict[str, Any]:
    """Approve a submission. Only valid when status is ``in_review`` or ``needs_revision``."""
    try:
        rec = _portal.approve(submission_id, decided_by=req.decided_by, reason=req.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail=f'submission {submission_id!r} not found')
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return rec.to_dict()


@router.post('/submission/{submission_id}/reject', summary='Reject a submission')
def reject(submission_id: str, req: RejectRequest) -> Dict[str, Any]:
    """Reject a submission. Only valid when status is ``in_review`` or ``needs_revision``."""
    try:
        rec = _portal.reject(submission_id, reason=req.reason, decided_by=req.decided_by)
    except KeyError:
        raise HTTPException(status_code=404, detail=f'submission {submission_id!r} not found')
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return rec.to_dict()


@router.post('/submission/{submission_id}/revision', summary='Request revision')
def request_revision(submission_id: str, req: RevisionRequest) -> Dict[str, Any]:
    """Request changes from the publisher. Moves submission to ``needs_revision``."""
    try:
        rec = _portal.request_revision(
            submission_id, reason=req.reason, decided_by=req.decided_by
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f'submission {submission_id!r} not found')
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return rec.to_dict()


@router.post('/submission/{submission_id}/resubmit', summary='Re-run pipeline after revision')
def resubmit(submission_id: str) -> Dict[str, Any]:
    """Re-run the review pipeline on a ``needs_revision`` submission."""
    try:
        rec = _portal.resubmit(submission_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f'submission {submission_id!r} not found')
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return rec.to_dict()


@router.get('/stats', summary='Submission statistics')
def stats() -> Dict[str, Any]:
    """Return aggregate counts by status across all submissions."""
    all_recs = _portal.list_submissions()
    by_status: Dict[str, int] = {}
    for rec in all_recs:
        by_status[rec.status] = by_status.get(rec.status, 0) + 1
    return {
        'total': len(all_recs),
        'by_status': by_status,
        'auto_approved': sum(
            1 for r in all_recs
            if r.status == 'approved' and r.decided_by == 'auto'
        ),
    }
