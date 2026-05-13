"""ETD Skill Store REST API — FastAPI application.

Endpoints:
    GET  /health                          — liveness check
    POST /validate                        — validate a skill package by path
    GET  /store/skills                    — list all skills in the store
    GET  /store/skills/{skill_id}         — get one skill entry
    POST /store/install                   — install-decision for a skill
    GET  /store/policy                    — marketplace policy
    POST /store/sign                      — sign a skill package (requires key on server)

Run:
    uvicorn api.app:app --reload --port 8080
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from etd_reference_validator import ETDReferenceValidator, RuntimeContext, load_runtime_context
from marketplace.skill_store import SkillStore, default_runtime_context
from adapters.station_profile_loader import load_all_profiles, check_skill_compatible

app = FastAPI(
    title='ETD Skill Store API',
    description='Validate, browse, and install ETD robot skill packages.',
    version='0.79.0',
    docs_url='/docs',
    redoc_url='/redoc',
)

from api.publisher import router as _publisher_router
from api.cross_platform import router as _cross_platform_router
from api.fleet import router as _fleet_router
from api.composer import router as _composer_router
app.include_router(_publisher_router)
app.include_router(_cross_platform_router)
app.include_router(_fleet_router)
app.include_router(_composer_router)

_ctx_path = ROOT / 'runtime_context.json'
_default_ctx = load_runtime_context(_ctx_path) if _ctx_path.exists() else RuntimeContext()
_store = SkillStore(ROOT)
_station_profiles_dir = ROOT / 'station_profiles'


# ── Models ────────────────────────────────────────────────────────────────────

class ValidateRequest(BaseModel):
    package_path: str
    robot_class: Optional[str] = 'humanoid'
    runtime_version: Optional[str] = '0.1.0'
    available_services: Optional[List[str]] = []

class InstallRequest(BaseModel):
    skill_id: str
    entitlement_token: Optional[str] = None
    robot_class: Optional[str] = 'humanoid'
    runtime_version: Optional[str] = '0.1.0'
    available_services: Optional[List[str]] = []
    station_id: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get('/health', tags=['system'])
def health() -> Dict[str, Any]:
    station_count = len(list(_station_profiles_dir.glob('*.json'))) if _station_profiles_dir.exists() else 0
    skill_count = len(_store.list_skills())
    revoked_count = len(_store._revoked)
    return {
        'status': 'ok',
        'version': '0.5.0',
        'validator_version': '0.5.0',
        'loaded_skills': skill_count,
        'loaded_stations': station_count,
        'revoked_skills': revoked_count,
    }


@app.post('/validate', tags=['validation'])
def validate_package(req: ValidateRequest) -> JSONResponse:
    """Validate an ETD skill package directory on the server filesystem.

    Returns a full ValidationReport including schema results, semantic checks,
    and compatibility level (A/B/C/D).
    """
    pkg_path = Path(req.package_path)
    if not pkg_path.is_absolute():
        pkg_path = ROOT / pkg_path
    if not pkg_path.exists():
        raise HTTPException(status_code=404, detail=f'Package path not found: {pkg_path}')

    ctx = RuntimeContext(
        runtime_version=req.runtime_version or '0.1.0',
        robot_class=req.robot_class or 'humanoid',
        available_services=req.available_services or [],
    )
    report = ETDReferenceValidator(ctx).validate_package(pkg_path)
    return JSONResponse(content=json.loads(report.to_json()))


@app.get('/store/skills', tags=['store'])
def list_skills(
    family: Optional[str] = Query(None, description='Filter by skill family'),
    license_model: Optional[str] = Query(None, description='Filter by license model'),
    free_only: bool = Query(False, description='Only free skills'),
) -> JSONResponse:
    """List all skills in the ETD Skill Store index."""
    entries = _store.list_skills()

    if family:
        entries = [e for e in entries if e.get('family') == family]
    if license_model:
        entries = [e for e in entries if e.get('licenseModel') == license_model]
    if free_only:
        entries = [e for e in entries if e.get('pricingModel') == 'free']

    return JSONResponse(content={'count': len(entries), 'skills': entries})


@app.get('/store/skills/{skill_id:path}', tags=['store'])
def get_skill(skill_id: str) -> JSONResponse:
    """Get details for a specific skill by ID (e.g. etd.pickplace.basic)."""
    entry = _store.find_skill(skill_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f'Skill not found: {skill_id}')
    return JSONResponse(content=entry)


@app.get('/store/stations', tags=['store'])
def list_stations() -> JSONResponse:
    """List all known station profiles."""
    profiles = load_all_profiles(_station_profiles_dir)
    return JSONResponse(content={
        'count': len(profiles),
        'stations': [p.to_dict() for p in profiles.values()],
    })


@app.get('/store/stations/{station_id}', tags=['store'])
def get_station(station_id: str) -> JSONResponse:
    """Get a single station profile by ID."""
    profiles = load_all_profiles(_station_profiles_dir)
    if station_id not in profiles:
        raise HTTPException(status_code=404, detail=f'Station not found: {station_id}')
    return JSONResponse(content=profiles[station_id].to_dict())


@app.post('/store/install', tags=['store'])
def install_decision(req: InstallRequest) -> JSONResponse:
    """Return an install decision for a skill given robot context and entitlement.

    Optionally pass station_id to also check station compatibility.
    The response includes whether install is allowed, validation level,
    license model, pricing model, and (if station_id given) station_compatible.
    """
    ctx = default_runtime_context()
    ctx.robot_class = req.robot_class or ctx.robot_class
    ctx.runtime_version = req.runtime_version or ctx.runtime_version
    if req.available_services:
        ctx.available_services = req.available_services

    decision = _store.validate_for_install(
        req.skill_id, ctx, entitlement_token=req.entitlement_token
    )
    if decision is None:
        raise HTTPException(status_code=404, detail=f'Skill not found: {req.skill_id}')

    result = asdict(decision)

    if req.station_id:
        profiles = load_all_profiles(_station_profiles_dir)
        if req.station_id not in profiles:
            raise HTTPException(status_code=404, detail=f'Station not found: {req.station_id}')
        profile = profiles[req.station_id]
        entry = _store.find_skill(req.skill_id)
        if entry:
            compat = check_skill_compatible(
                profile,
                skill_family=entry.get('family', ''),
                payload_kg=entry.get('maxPayloadKg', 0.0),
                requires_human_aware=entry.get('requiresHumanAware', False),
                required_services=entry.get('requiredServices', []),
                skill_id=req.skill_id,
            )
            result['station_compatible'] = compat.compatible
            result['station_reason'] = compat.reason
            result['station_missing_services'] = compat.missing_services
            result['station_warnings'] = compat.warnings

    return JSONResponse(content=result)


@app.get('/store/policy', tags=['store'])
def get_policy() -> JSONResponse:
    """Return the current marketplace policy document."""
    policy_path = ROOT / 'marketplace' / 'marketplace_policy.json'
    if not policy_path.exists():
        raise HTTPException(status_code=404, detail='Policy file not found')
    return JSONResponse(content=json.loads(policy_path.read_text()))


@app.post('/store/sign', tags=['store'])
def sign_skill(package_path: str, key_path: Optional[str] = 'keys/etd_signing_key.hex') -> JSONResponse:
    """Sign a skill package on the server (key must exist on server filesystem)."""
    pkg = Path(package_path)
    if not pkg.is_absolute():
        pkg = ROOT / pkg
    if not pkg.exists():
        raise HTTPException(status_code=404, detail=f'Package path not found: {pkg}')

    key = Path(key_path or 'keys/etd_signing_key.hex')
    if not key.is_absolute():
        key = ROOT / key
    if not key.exists():
        raise HTTPException(status_code=400, detail=f'Signing key not found: {key}. Run: python scripts/generate_keypair.py')

    try:
        from scripts.sign_package import sign_package
        sig_path = sign_package(pkg, key)
        return JSONResponse(content={'signed': True, 'signature_file': str(sig_path)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api.app:app', host='0.0.0.0', port=8080, reload=True)
