"""FastAPI router — cross-platform humanoid compatibility endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix='/platform', tags=['cross-platform'])


# ── Request / Response models ─────────────────────────────────────────────────

class SkillInfoBody(BaseModel):
    skillId: str
    family: str = ''
    primitiveOrder: List[str] = []


class CompatCheckRequest(BaseModel):
    skill_info: SkillInfoBody
    source: str
    target: str


class MatrixRequest(BaseModel):
    skill_info: Optional[SkillInfoBody] = None
    families: Optional[List[str]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get('/list')
def list_platforms() -> List[Dict[str, Any]]:
    """Return all registered robot platforms."""
    from marketplace.cross_platform import HumanoidRegistry
    reg = HumanoidRegistry()
    return [p.to_dict() for p in reg.list_platforms()]


@router.post('/check')
def check_compat(req: CompatCheckRequest) -> Dict[str, Any]:
    """Check cross-platform portability for a skill from source to target platform."""
    from marketplace.cross_platform import HumanoidRegistry
    reg = HumanoidRegistry()
    skill_info = {
        'skillId': req.skill_info.skillId,
        'family': req.skill_info.family,
        'primitiveOrder': req.skill_info.primitiveOrder,
    }
    result = reg.check_compat(skill_info, source=req.source, target=req.target)
    return result.to_dict()


@router.post('/matrix')
def compat_matrix(req: MatrixRequest) -> List[Dict[str, Any]]:
    """Return the NxN cross-platform compatibility matrix."""
    from marketplace.cross_platform import HumanoidRegistry
    reg = HumanoidRegistry()
    skill_info = None
    if req.skill_info is not None:
        skill_info = {
            'skillId': req.skill_info.skillId,
            'family': req.skill_info.family,
            'primitiveOrder': req.skill_info.primitiveOrder,
        }
    families = set(req.families) if req.families else None
    return reg.compat_matrix(skill_info=skill_info, families=families)


@router.get('/platform/{platform_id}')
def get_platform(platform_id: str) -> Dict[str, Any]:
    """Return a single platform descriptor by ID."""
    from marketplace.cross_platform import HumanoidRegistry
    reg = HumanoidRegistry()
    platform = reg.get(platform_id)
    if platform is None:
        raise HTTPException(status_code=404, detail=f'Platform {platform_id!r} not found')
    return platform.to_dict()
