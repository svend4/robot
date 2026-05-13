"""FastAPI router — fleet management endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix='/fleet', tags=['fleet'])

_FLEET_DIR = Path(__file__).resolve().parent.parent / 'fleet'


def _fm():
    from marketplace.fleet_manager import FleetManager
    return FleetManager(data_dir=_FLEET_DIR)


# ── Request / Response models ─────────────────────────────────────────────────

class RegisterNodeRequest(BaseModel):
    node_id: str
    station_id: str
    platform_id: str
    metadata: Dict[str, Any] = {}


class HeartbeatRequest(BaseModel):
    status: str = 'online'
    installed_skills: Optional[List[str]] = None


class DeployRequest(BaseModel):
    skill_id: str
    version: str = '0.1.0'
    target_node_ids: List[str]
    skill_info: Optional[Dict[str, Any]] = None
    source_platform: str = ''
    entitlement_tokens: Optional[List[Dict[str, Any]]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get('/nodes')
def list_nodes() -> List[Dict[str, Any]]:
    """List all registered fleet nodes."""
    return [n.to_dict() for n in _fm().list_nodes()]


@router.post('/nodes', status_code=201)
def register_node(req: RegisterNodeRequest) -> Dict[str, Any]:
    """Register (or replace) a robot node in the fleet."""
    from marketplace.fleet_manager import RobotNode
    fm = _fm()
    node = RobotNode(
        node_id=req.node_id,
        station_id=req.station_id,
        platform_id=req.platform_id,
        metadata=req.metadata,
    )
    fm.register_node(node)
    return node.to_dict()


@router.delete('/nodes/{node_id}')
def unregister_node(node_id: str) -> Dict[str, Any]:
    """Remove a robot node from the fleet."""
    fm = _fm()
    removed = fm.unregister_node(node_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f'Node {node_id!r} not found')
    return {'removed': node_id}


@router.get('/nodes/{node_id}')
def get_node(node_id: str) -> Dict[str, Any]:
    """Return a single node descriptor."""
    fm = _fm()
    node = fm.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f'Node {node_id!r} not found')
    return node.to_dict()


@router.put('/nodes/{node_id}/heartbeat')
def heartbeat(node_id: str, req: HeartbeatRequest) -> Dict[str, Any]:
    """Update a node's last-seen timestamp and status."""
    fm = _fm()
    ok = fm.heartbeat(node_id, status=req.status,
                      installed_skills=req.installed_skills)
    if not ok:
        raise HTTPException(status_code=404, detail=f'Node {node_id!r} not found')
    return fm.get_node(node_id).to_dict()


@router.post('/deployments', status_code=201)
def deploy(req: DeployRequest) -> Dict[str, Any]:
    """Deploy a skill to selected fleet nodes."""
    fm = _fm()
    deployment = fm.deploy(
        skill_id=req.skill_id,
        version=req.version,
        target_node_ids=req.target_node_ids,
        entitlement_tokens=req.entitlement_tokens,
        skill_info=req.skill_info,
        source_platform=req.source_platform,
    )
    return deployment.to_dict()


@router.get('/deployments')
def list_deployments(
    skill_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List fleet deployments, optionally filtered by skill_id or status."""
    return [d.to_dict() for d in _fm().list_deployments(skill_id=skill_id, status=status)]


@router.get('/deployments/{deployment_id}')
def get_deployment(deployment_id: str) -> Dict[str, Any]:
    """Return a single deployment record."""
    fm = _fm()
    dep = fm.get_deployment(deployment_id)
    if dep is None:
        raise HTTPException(status_code=404,
                            detail=f'Deployment {deployment_id!r} not found')
    return dep.to_dict()


@router.get('/status')
def fleet_status() -> Dict[str, Any]:
    """Return a fleet health snapshot."""
    return _fm().fleet_status().to_dict()
