"""ETD Skill Dependency Resolver REST API router.

Endpoints:
    POST /deps/skills                    — register skill dependencies
    GET  /deps/skills                    — list registered skills
    GET  /deps/skills/{skill_id}         — get deps for one skill; 404
    DELETE /deps/skills/{skill_id}       — remove; 404
    GET  /deps/skills/{skill_id}/order   — topological install order; 409 on cycle
    GET  /deps/skills/{skill_id}/tree    — nested dependency tree
    POST /deps/check                     — check satisfaction against available set
    GET  /deps/cycles                    — detect cycles in full graph
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from marketplace.dependency_resolver import (
    CyclicDependencyError,
    DependencyStore,
    SkillDependency,
)

router = APIRouter(prefix='/deps', tags=['dependencies'])

_DEPS_DIR = ROOT / 'deps'


def _store() -> DependencyStore:
    return DependencyStore(_DEPS_DIR)


# ── Models ────────────────────────────────────────────────────────────────────

class DepEntry(BaseModel):
    skill_id: str
    version_constraint: str = ''
    optional: bool = False


class RegisterRequest(BaseModel):
    skill_id: str
    deps: List[DepEntry]


class CheckRequest(BaseModel):
    skill_id: str
    available: List[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post('/skills', status_code=201)
def register_skill(req: RegisterRequest) -> JSONResponse:
    """Register or update the dependency list for a skill."""
    store = _store()
    deps = [
        SkillDependency(skill_id=d.skill_id,
                        version_constraint=d.version_constraint,
                        optional=d.optional)
        for d in req.deps
    ]
    store.register(req.skill_id, deps)
    return JSONResponse(
        content={'skill_id': req.skill_id,
                 'deps': [d.to_dict() for d in deps]},
        status_code=201,
    )


@router.get('/skills')
def list_skills() -> JSONResponse:
    """List all skills with registered dependency declarations."""
    store = _store()
    skills = store.list_skills()
    return JSONResponse(content={
        'count': len(skills),
        'skills': [
            {'skill_id': s,
             'deps': [d.to_dict() for d in (store.get(s) or [])]}
            for s in skills
        ],
    })


@router.get('/skills/{skill_id}')
def get_skill_deps(skill_id: str) -> JSONResponse:
    """Get the dependency list for one skill."""
    store = _store()
    deps = store.get(skill_id)
    if deps is None:
        raise HTTPException(status_code=404,
                            detail=f'No deps registered for: {skill_id}')
    return JSONResponse(content={
        'skill_id': skill_id,
        'deps': [d.to_dict() for d in deps],
    })


@router.delete('/skills/{skill_id}')
def remove_skill_deps(skill_id: str) -> JSONResponse:
    """Remove the dependency declaration for a skill."""
    store = _store()
    if not store.remove(skill_id):
        raise HTTPException(status_code=404,
                            detail=f'No deps registered for: {skill_id}')
    return JSONResponse(content={'removed': skill_id})


@router.get('/order/{skill_id}')
def install_order(skill_id: str) -> JSONResponse:
    """Return topological install order for a skill. 409 if cycle detected."""
    store = _store()
    resolver = store.resolver()
    try:
        order = resolver.install_order(skill_id)
    except CyclicDependencyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return JSONResponse(content={
        'skill_id': skill_id,
        'install_order': order,
        'dep_count': len(order) - 1,
    })


@router.get('/tree/{skill_id}')
def dependency_tree(skill_id: str) -> JSONResponse:
    """Return the nested dependency tree for a skill."""
    store = _store()
    resolver = store.resolver()
    tree = resolver.dependency_tree(skill_id)
    return JSONResponse(content=tree)


@router.post('/check')
def check_satisfied(req: CheckRequest) -> JSONResponse:
    """Check whether required deps for a skill are in the available set."""
    store = _store()
    resolver = store.resolver()
    satisfied, missing = resolver.check_satisfied(
        req.skill_id, set(req.available)
    )
    return JSONResponse(content={
        'skill_id': req.skill_id,
        'satisfied': satisfied,
        'missing': missing,
    })


@router.get('/cycles')
def detect_cycles() -> JSONResponse:
    """Detect cycles in the full dependency graph."""
    store = _store()
    cycles = store.resolver().cycles()
    return JSONResponse(content={
        'cycle_count': len(cycles),
        'cycles': cycles,
    })
