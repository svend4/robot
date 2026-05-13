"""ETD Skill Health Monitor REST API router.

Endpoints:
    GET  /monitor/skills                  — health check all known skills
    GET  /monitor/skills/{skill_id}       — health check one skill
    GET  /monitor/nodes                   — health check all known nodes
    GET  /monitor/nodes/{node_id}         — health check one node
    GET  /monitor/fleet                   — fleet-wide health report
    GET  /monitor/alerts                  — list active alerts
    DELETE /monitor/alerts/{alert_id}     — resolve an alert (404 if unknown)
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

from marketplace.health_monitor import HealthMonitor, HealthThresholds
from marketplace.telemetry_analytics import TelemetryStore

router = APIRouter(prefix='/monitor', tags=['health-monitor'])

_TELEMETRY_PATH = ROOT / 'telemetry' / 'executions.jsonl'
_ALERT_DIR = ROOT / 'health'


def _monitor() -> HealthMonitor:
    store = TelemetryStore(_TELEMETRY_PATH)
    return HealthMonitor(store, alert_dir=_ALERT_DIR)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/skills')
def list_skill_health(
    window_hours: int = Query(1, ge=1, description='Look-back window in hours'),
) -> JSONResponse:
    """Return health reports for all known skills."""
    mon = _monitor()
    store = TelemetryStore(_TELEMETRY_PATH)
    skill_ids = store.skill_ids()
    reports = [mon.check_skill(s, window_hours).to_dict() for s in skill_ids]
    return JSONResponse(content={
        'skill_count': len(reports),
        'window_hours': window_hours,
        'skills': reports,
    })


@router.get('/skills/{skill_id}')
def skill_health(
    skill_id: str,
    window_hours: int = Query(1, ge=1, description='Look-back window in hours'),
) -> JSONResponse:
    """Return health report for one skill."""
    mon = _monitor()
    report = mon.check_skill(skill_id, window_hours)
    return JSONResponse(content=report.to_dict())


@router.get('/nodes')
def list_node_health(
    window_hours: int = Query(1, ge=1, description='Look-back window in hours'),
) -> JSONResponse:
    """Return health reports for all known nodes."""
    mon = _monitor()
    store = TelemetryStore(_TELEMETRY_PATH)
    node_ids = store.node_ids()
    reports = [mon.check_node(n, window_hours).to_dict() for n in node_ids]
    return JSONResponse(content={
        'node_count': len(reports),
        'window_hours': window_hours,
        'nodes': reports,
    })


@router.get('/nodes/{node_id}')
def node_health(
    node_id: str,
    window_hours: int = Query(1, ge=1, description='Look-back window in hours'),
) -> JSONResponse:
    """Return health report for one node."""
    mon = _monitor()
    report = mon.check_node(node_id, window_hours)
    return JSONResponse(content=report.to_dict())


@router.get('/fleet')
def fleet_health(
    window_hours: int = Query(1, ge=1, description='Look-back window in hours'),
) -> JSONResponse:
    """Return fleet-wide health report (worst-case overall status)."""
    mon = _monitor()
    report = mon.check_fleet(window_hours)
    return JSONResponse(content=report.to_dict())


@router.get('/alerts')
def list_alerts(
    all_alerts: bool = Query(False, description='Include resolved alerts'),
) -> JSONResponse:
    """List health alerts (active only by default)."""
    mon = _monitor()
    alerts = mon.all_alerts() if all_alerts else mon.active_alerts()
    return JSONResponse(content={
        'alert_count': len(alerts),
        'alerts': [a.to_dict() for a in alerts],
    })


@router.delete('/alerts/{alert_id}')
def resolve_alert(alert_id: str) -> JSONResponse:
    """Mark an alert as resolved. 404 if the alert does not exist."""
    mon = _monitor()
    resolved = mon.resolve_alert(alert_id)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f'Alert not found or already resolved: {alert_id}',
        )
    return JSONResponse(content={'resolved': alert_id})
