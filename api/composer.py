"""FastAPI router — composed multi-step skill endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix='/compose', tags=['composer'])

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / 'examples'


# ── Request / Response models ─────────────────────────────────────────────────

class SkillStepBody(BaseModel):
    skillId: str
    versionConstraint: str = ''
    onFailure: str = 'abort'
    retryCount: int = 0
    params: Dict[str, Any] = {}


class ComposedSkillBody(BaseModel):
    skillId: str
    version: str = '0.0.0'
    name: str = ''
    description: str = ''
    steps: List[SkillStepBody] = []


class ValidateRequest(BaseModel):
    composed: ComposedSkillBody


class RunRequest(BaseModel):
    composed: ComposedSkillBody


# ── Helpers ───────────────────────────────────────────────────────────────────

def _body_to_composed(body: ComposedSkillBody):
    from marketplace.composer import ComposedSkill
    return ComposedSkill.from_dict({
        'skillId': body.skillId,
        'version': body.version,
        'name': body.name or body.skillId,
        'description': body.description,
        'steps': [
            {
                'skillId': s.skillId,
                'versionConstraint': s.versionConstraint,
                'onFailure': s.onFailure,
                'retryCount': s.retryCount,
                'params': s.params,
            }
            for s in body.steps
        ],
    })


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post('/validate')
def validate_composed(req: ValidateRequest) -> Dict[str, Any]:
    """Validate a composed skill manifest and return issues list."""
    from marketplace.composer import SkillComposer
    from marketplace.skill_store import SkillStore
    try:
        composed = _body_to_composed(req.composed)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    store = SkillStore(Path(__file__).resolve().parent.parent)
    issues = SkillComposer(store).validate(composed)
    return {
        'skill_id': composed.skill_id,
        'version': composed.version,
        'valid': len(issues) == 0,
        'issues': issues,
        'step_count': len(composed.steps),
    }


@router.post('/run')
def run_composed(req: RunRequest) -> Dict[str, Any]:
    """Dry-run a composed skill (mock executor) and return execution result."""
    from marketplace.composer import SkillComposer
    try:
        composed = _body_to_composed(req.composed)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = SkillComposer().run(composed)
    return result.to_dict()


@router.get('/examples')
def list_composed_examples() -> List[Dict[str, Any]]:
    """List composed skill packages available in the examples directory."""
    from marketplace.composer import load_composed_skill
    results = []
    for pkg in sorted(_EXAMPLES_DIR.iterdir()):
        manifest = pkg / 'composed_skill.json'
        if not pkg.is_dir() or not manifest.exists():
            continue
        try:
            composed = load_composed_skill(pkg)
            results.append({
                'package_path': str(pkg),
                'skill_id': composed.skill_id,
                'version': composed.version,
                'name': composed.name,
                'step_count': len(composed.steps),
            })
        except Exception:
            pass
    return results


@router.get('/examples/{package_name}/validate')
def validate_example(package_name: str) -> Dict[str, Any]:
    """Validate a named composed skill example package."""
    from marketplace.composer import SkillComposer, load_composed_skill
    from marketplace.skill_store import SkillStore
    pkg = _EXAMPLES_DIR / package_name
    if not pkg.exists():
        raise HTTPException(status_code=404,
                            detail=f'Package {package_name!r} not found')
    try:
        composed = load_composed_skill(pkg)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    store = SkillStore(Path(__file__).resolve().parent.parent)
    issues = SkillComposer(store).validate(composed)
    return {
        'skill_id': composed.skill_id,
        'version': composed.version,
        'valid': len(issues) == 0,
        'issues': issues,
        'step_count': len(composed.steps),
    }


@router.get('/examples/{package_name}/run')
def run_example(package_name: str) -> Dict[str, Any]:
    """Dry-run a named composed skill example package."""
    from marketplace.composer import SkillComposer, load_composed_skill
    pkg = _EXAMPLES_DIR / package_name
    if not pkg.exists():
        raise HTTPException(status_code=404,
                            detail=f'Package {package_name!r} not found')
    try:
        composed = load_composed_skill(pkg)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    result = SkillComposer().run(composed)
    return result.to_dict()
