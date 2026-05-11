"""Tests for the ETD Skill Store REST API (FastAPI)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import app

client = TestClient(app)

_FULL_SERVICES = [
    'perception.object_pose', 'perception.part_alignment',
    'manipulation.arm_control', 'force_control.contact_feedback',
    'workflow.job_context', 'state.robot_pose', 'state.arm_state',
    'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
    'vision.barcode_scan', 'quality.photo_capture', 'telemetry.metrics',
]


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'ok'
    assert 'version' in body


# ── Store — list skills ───────────────────────────────────────────────────────

def test_list_skills_all():
    r = client.get('/store/skills')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 5
    ids = {s['skillId'] for s in body['skills']}
    assert 'etd.pickplace.basic' in ids
    assert 'etd.atlas.humanoid_walkfetch' in ids


def test_list_skills_filter_family():
    r = client.get('/store/skills?family=pickplace')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 1
    assert body['skills'][0]['skillId'] == 'etd.pickplace.basic'


def test_list_skills_filter_free_only():
    r = client.get('/store/skills?free_only=true')
    assert r.status_code == 200
    body = r.json()
    for s in body['skills']:
        assert s['pricingModel'] == 'free'


def test_list_skills_filter_license():
    r = client.get('/store/skills?license_model=open_source')
    assert r.status_code == 200
    for s in r.json()['skills']:
        assert s['licenseModel'] == 'open_source'


# ── Store — get single skill ──────────────────────────────────────────────────

def test_get_skill_found():
    r = client.get('/store/skills/etd.pickplace.basic')
    assert r.status_code == 200
    body = r.json()
    assert body['skillId'] == 'etd.pickplace.basic'
    assert body['pricingModel'] == 'free'


def test_get_skill_not_found():
    r = client.get('/store/skills/etd.does.not.exist')
    assert r.status_code == 404


def test_get_atlas_skill():
    r = client.get('/store/skills/etd.atlas.humanoid_walkfetch')
    assert r.status_code == 200
    body = r.json()
    assert body['family'] == 'humanoid'
    assert body['platformTarget'] == 'boston_dynamics_atlas'


# ── Store — install decision ──────────────────────────────────────────────────

def test_install_free_skill_allowed():
    r = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is True
    assert body['reason'] == 'install_allowed'


def test_install_entitlement_required_no_token():
    r = client.post('/store/install', json={
        'skill_id': 'etd.assembly.precision',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is False
    assert body['reason'] == 'entitlement_required'


def test_install_entitlement_with_token():
    r = client.post('/store/install', json={
        'skill_id': 'etd.assembly.precision',
        'entitlement_token': 'valid-token-123',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is True


def test_install_not_found():
    r = client.post('/store/install', json={
        'skill_id': 'etd.nonexistent.skill',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is False


def test_install_missing_services_fails():
    r = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': ['perception.object_pose'],
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is False
    assert body['validationLevel'] == 'D'


# ── Validate endpoint ─────────────────────────────────────────────────────────

def test_validate_good_package():
    r = client.post('/validate', json={
        'package_path': 'examples/etd.pickplace.basic',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['valid'] is True
    assert body['compatibility']['level'] == 'A'


def test_validate_nonexistent_path():
    r = client.post('/validate', json={
        'package_path': 'examples/etd.does.not.exist',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 404


# ── Policy ────────────────────────────────────────────────────────────────────

def test_get_policy():
    r = client.get('/store/policy')
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert len(body) > 0


# ── OpenAPI schema ────────────────────────────────────────────────────────────

def test_openapi_schema():
    r = client.get('/openapi.json')
    assert r.status_code == 200
    schema = r.json()
    assert schema['info']['title'] == 'ETD Skill Store API'
    paths = schema['paths']
    assert '/health' in paths
    assert '/store/skills' in paths
    assert '/store/install' in paths
    assert '/validate' in paths
