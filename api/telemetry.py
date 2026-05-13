"""ETD Telemetry Analytics REST API router.

Endpoints:
    POST /telemetry/executions          — record one execution
    GET  /telemetry/executions          — query recorded executions
    GET  /telemetry/stats/{skill_id}    — aggregated stats for a skill
    GET  /telemetry/report              — full fleet telemetry report
    GET  /telemetry/anomalies           — z-score anomaly detection
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

from marketplace.telemetry_analytics import (
    TelemetryAnalyzer,
    TelemetryStore,
    ExecutionRecord,
)

router = APIRouter(prefix='/telemetry', tags=['telemetry'])

_STORE_PATH = ROOT / 'telemetry' / 'executions.jsonl'


def _store() -> TelemetryStore:
    return TelemetryStore(_STORE_PATH)


# ── Models ────────────────────────────────────────────────────────────────────

class RecordExecutionRequest(BaseModel):
    skill_id: str
    node_id: str
    station_id: str = 'default'
    status: str = 'success'          # 'success' | 'failed' | 'aborted'
    total_duration_ms: int = 0
    failure_reason: str = ''
    execution_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post('/executions', status_code=201)
def record_execution(req: RecordExecutionRequest) -> JSONResponse:
    """Record one skill execution in the telemetry store."""
    store = _store()
    if req.execution_id and req.started_at and req.completed_at:
        rec = ExecutionRecord(
            execution_id=req.execution_id,
            skill_id=req.skill_id,
            node_id=req.node_id,
            station_id=req.station_id,
            started_at=req.started_at,
            completed_at=req.completed_at,
            status=req.status,
            total_duration_ms=req.total_duration_ms,
            failure_reason=req.failure_reason,
        )
    else:
        rec = ExecutionRecord.make(
            skill_id=req.skill_id,
            node_id=req.node_id,
            station_id=req.station_id,
            status=req.status,
            total_duration_ms=req.total_duration_ms,
            failure_reason=req.failure_reason,
        )
    store.record(rec)
    return JSONResponse(content=rec.to_dict(), status_code=201)


@router.get('/executions')
def list_executions(
    skill_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """Query execution records with optional filters."""
    store = _store()
    records = store.query(
        skill_id=skill_id,
        node_id=node_id,
        status=status,
        since=since,
        limit=limit,
    )
    return JSONResponse(content={
        'count': len(records),
        'executions': [r.to_dict() for r in records],
    })


@router.get('/stats/{skill_id:path}')
def skill_stats(skill_id: str) -> JSONResponse:
    """Return aggregated execution statistics for one skill."""
    store = _store()
    analyzer = TelemetryAnalyzer(store)
    stats = analyzer.skill_stats(skill_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f'No records for skill: {skill_id}')
    return JSONResponse(content=stats.to_dict())


@router.get('/report')
def telemetry_report() -> JSONResponse:
    """Return a full fleet telemetry report across all skills and nodes."""
    store = _store()
    analyzer = TelemetryAnalyzer(store)
    return JSONResponse(content=analyzer.report())


@router.get('/anomalies')
def detect_anomalies(
    skill_id: Optional[str] = Query(None, description='Filter by skill ID'),
    z_threshold: float = Query(2.0, ge=0.1, description='Z-score threshold'),
) -> JSONResponse:
    """Return executions whose duration deviates >= z_threshold σ from mean."""
    store = _store()
    analyzer = TelemetryAnalyzer(store)
    anomalies = analyzer.anomalies(skill_id=skill_id, z_threshold=z_threshold)
    return JSONResponse(content={
        'count': len(anomalies),
        'z_threshold': z_threshold,
        'anomalies': [
            {**r.to_dict(), 'z_score': z}
            for r, z in anomalies
        ],
    })
