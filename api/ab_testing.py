"""ETD A/B Testing REST API router.

Endpoints:
    POST /ab/experiments                       — create experiment
    GET  /ab/experiments                       — list (optional ?status=)
    GET  /ab/experiments/{id}                  — get one; 404 if unknown
    DELETE /ab/experiments/{id}                — delete; 404 if unknown
    PUT  /ab/experiments/{id}/pause            — pause active experiment
    PUT  /ab/experiments/{id}/resume           — resume paused experiment
    POST /ab/experiments/{id}/conclude         — conclude with optional winner
    GET  /ab/experiments/{id}/route            — pick a variant (weighted random)
    GET  /ab/experiments/{id}/results          — compare via telemetry
    GET  /ab/experiments/{id}/recommend        — recommend winning variant
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

from marketplace.ab_testing import (
    ABExperiment,
    ABExperimentStore,
    ABVariant,
    ABAnalyzer,
)
from marketplace.telemetry_analytics import TelemetryStore

router = APIRouter(prefix='/ab', tags=['ab-testing'])

_AB_STORE_PATH = ROOT / 'ab' / 'experiments.json'
_TEL_STORE_PATH = ROOT / 'telemetry' / 'executions.jsonl'


def _ab_store() -> ABExperimentStore:
    return ABExperimentStore(_AB_STORE_PATH)


def _analyzer() -> ABAnalyzer:
    return ABAnalyzer(TelemetryStore(_TEL_STORE_PATH))


def _get_or_404(store: ABExperimentStore, experiment_id: str) -> ABExperiment:
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404,
                            detail=f'Experiment not found: {experiment_id}')
    return exp


# ── Models ────────────────────────────────────────────────────────────────────

class ABVariantBody(BaseModel):
    skill_id: str
    version: str
    weight: float = 1.0
    label: str = ''


class CreateExperimentRequest(BaseModel):
    name: str
    variants: List[ABVariantBody]
    metadata: Optional[Dict[str, Any]] = None


class ConcludeRequest(BaseModel):
    winner_label: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post('/experiments', status_code=201)
def create_experiment(req: CreateExperimentRequest) -> JSONResponse:
    """Create a new A/B experiment."""
    if len(req.variants) < 2:
        raise HTTPException(status_code=422,
                            detail='An experiment requires at least 2 variants.')
    variants = [
        ABVariant(skill_id=v.skill_id, version=v.version,
                  weight=v.weight, label=v.label)
        for v in req.variants
    ]
    exp = ABExperiment.make(name=req.name, variants=variants,
                             metadata=req.metadata or {})
    store = _ab_store()
    store.save(exp)
    return JSONResponse(content=exp.to_dict(), status_code=201)


@router.get('/experiments')
def list_experiments(
    status: Optional[str] = Query(None, description='Filter by status'),
) -> JSONResponse:
    """List all experiments, optionally filtered by status."""
    store = _ab_store()
    experiments = store.list_experiments(status=status)
    return JSONResponse(content={
        'count': len(experiments),
        'experiments': [e.to_dict() for e in experiments],
    })


@router.get('/experiments/{experiment_id}')
def get_experiment(experiment_id: str) -> JSONResponse:
    """Get one experiment by ID."""
    return JSONResponse(content=_get_or_404(_ab_store(), experiment_id).to_dict())


@router.delete('/experiments/{experiment_id}')
def delete_experiment(experiment_id: str) -> JSONResponse:
    """Delete an experiment."""
    store = _ab_store()
    _get_or_404(store, experiment_id)
    store.delete(experiment_id)
    return JSONResponse(content={'deleted': experiment_id})


@router.put('/experiments/{experiment_id}/pause')
def pause_experiment(experiment_id: str) -> JSONResponse:
    """Pause an active experiment."""
    store = _ab_store()
    exp = _get_or_404(store, experiment_id)
    try:
        exp.pause()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    store.save(exp)
    return JSONResponse(content=exp.to_dict())


@router.put('/experiments/{experiment_id}/resume')
def resume_experiment(experiment_id: str) -> JSONResponse:
    """Resume a paused experiment."""
    store = _ab_store()
    exp = _get_or_404(store, experiment_id)
    try:
        exp.resume()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    store.save(exp)
    return JSONResponse(content=exp.to_dict())


@router.post('/experiments/{experiment_id}/conclude')
def conclude_experiment(experiment_id: str,
                        req: ConcludeRequest) -> JSONResponse:
    """Conclude an experiment with an optional declared winner."""
    store = _ab_store()
    exp = _get_or_404(store, experiment_id)
    try:
        exp.conclude(winner_label=req.winner_label)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    store.save(exp)
    return JSONResponse(content=exp.to_dict())


@router.get('/experiments/{experiment_id}/route')
def route_experiment(experiment_id: str) -> JSONResponse:
    """Return a weighted-random variant for this experiment."""
    store = _ab_store()
    exp = _get_or_404(store, experiment_id)
    try:
        chosen = exp.route()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return JSONResponse(content={
        'experiment_id': experiment_id,
        'chosen': chosen.to_dict(),
    })


@router.get('/experiments/{experiment_id}/results')
def experiment_results(experiment_id: str) -> JSONResponse:
    """Compare variants using telemetry data."""
    store = _ab_store()
    exp = _get_or_404(store, experiment_id)
    return JSONResponse(content=_analyzer().compare(exp))


@router.get('/experiments/{experiment_id}/recommend')
def recommend_winner(experiment_id: str) -> JSONResponse:
    """Return the recommended winning variant label based on telemetry."""
    store = _ab_store()
    exp = _get_or_404(store, experiment_id)
    label = _analyzer().recommend_winner(exp)
    return JSONResponse(content={
        'experiment_id': experiment_id,
        'recommended_winner': label,
    })
