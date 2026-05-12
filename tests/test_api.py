"""Tests for the ETD Skill Store REST API (FastAPI)."""
import shutil
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
    assert body['version'] == '0.5.0'


# ── Store — list skills ───────────────────────────────────────────────────────

def test_list_skills_all():
    r = client.get('/store/skills')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 8
    ids = {s['skillId'] for s in body['skills']}
    assert 'etd.pickplace.basic' in ids
    assert 'etd.atlas.humanoid_walkfetch' in ids
    assert 'etd.hyundai.wia_welding' in ids
    assert 'etd.hyundai.mobed_transport' in ids


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


def test_get_vest_exoskeleton_skill():
    r = client.get('/store/skills/etd.hyundai.vest_exoskeleton')
    assert r.status_code == 200
    body = r.json()
    assert body['skillId'] == 'etd.hyundai.vest_exoskeleton'
    assert body['family'] == 'assist'
    assert body['requiresEntitlement'] is True


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


# ── POST /store/sign ──────────────────────────────────────────────────────────

def test_sign_package_not_found():
    r = client.post('/store/sign', params={
        'package_path': 'examples/etd.does.not.exist',
    })
    assert r.status_code == 404


def test_sign_key_not_found():
    r = client.post('/store/sign', params={
        'package_path': 'examples/etd.pickplace.basic',
        'key_path': 'keys/no_such_key.hex',
    })
    assert r.status_code == 400


def test_sign_valid_package(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'etd.pickplace.basic'
    shutil.copytree(src, dst)

    from scripts.generate_keypair import generate
    key_dir = tmp_path / 'keys'
    generate(key_dir)

    r = client.post('/store/sign', params={
        'package_path': str(dst),
        'key_path': str(key_dir / 'etd_signing_key.hex'),
    })
    assert r.status_code == 200
    body = r.json()
    assert body['signed'] is True
    assert 'signature_file' in body
    assert (dst / 'package.sig').exists()


# ── Validate endpoint — extra paths ──────────────────────────────────────────

def test_validate_with_absolute_path():
    r = client.post('/validate', json={
        'package_path': str(ROOT / 'examples' / 'etd.pickplace.basic'),
        'robot_class': 'humanoid',
        'available_services': _FULL_SERVICES,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['valid'] is True


def test_validate_hyundai_wia_welding():
    wia_ctx_path = ROOT / 'runtime_context_wia.json'
    import json as _json
    wia_services = _json.loads(wia_ctx_path.read_text())['available_services']
    r = client.post('/validate', json={
        'package_path': 'examples/etd.hyundai.wia_welding',
        'robot_class': 'cobot',
        'available_services': wia_services,
    })
    assert r.status_code == 200
    body = r.json()
    assert body['valid'] is True
    assert body['compatibility']['level'] == 'A'


# ── Store — list skills extra filters ─────────────────────────────────────────

def test_list_skills_filter_family_no_match():
    r = client.get('/store/skills?family=does_not_exist')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 0
    assert body['skills'] == []


def test_list_skills_filter_welding_family():
    r = client.get('/store/skills?family=welding')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 1
    assert body['skills'][0]['skillId'] == 'etd.hyundai.wia_welding'


def test_list_skills_filter_assist_family():
    r = client.get('/store/skills?family=assist')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 1
    assert body['skills'][0]['skillId'] == 'etd.hyundai.vest_exoskeleton'


# ── Store — install decision extra cases ──────────────────────────────────────

def test_install_mobed_with_compatible_station():
    import json as _json
    mobed_ctx = _json.loads((ROOT / 'runtime_context_mobed.json').read_text())
    r = client.post('/store/install', json={
        'skill_id': 'etd.hyundai.mobed_transport',
        'entitlement_token': 'valid-token-123',
        'robot_class': mobed_ctx['robot_class'],
        'available_services': mobed_ctx['available_services'],
        'station_id': 'mobed_logistics_a',
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is True
    assert body['station_compatible'] is True
    assert 'station_warnings' in body
    assert 'station_missing_services' in body


def test_install_nonexistent_skill_with_valid_station():
    """Valid station_id + unknown skill_id: entry=None branch skips station check."""
    r = client.post('/store/install', json={
        'skill_id': 'etd.does.not.exist',
        'robot_class': 'humanoid',
        'available_services': [],
        'station_id': 'weld_station_a',
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is False
    assert body['reason'] == 'skill_not_found'
    assert 'station_compatible' not in body


# ── /store/skills: all three query filters combined ───────────────────────────

def test_list_skills_all_three_filters():
    # etd.pickplace.basic: family=pickplace, licenseModel=open_source, pricingModel=free
    r = client.get('/store/skills?family=pickplace&license_model=open_source&free_only=true')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] == 1
    assert body['skills'][0]['skillId'] == 'etd.pickplace.basic'


# ── POST /store/sign: sign_package raises → 500 ───────────────────────────────

def test_sign_package_exception_returns_500(tmp_path):
    from unittest.mock import patch
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'etd.pickplace.basic'
    shutil.copytree(src, dst)
    fake_key = tmp_path / 'fake_key.hex'
    fake_key.write_text('00' * 32)
    with patch('scripts.sign_package.sign_package', side_effect=RuntimeError('signing failed')):
        r = client.post('/store/sign', params={
            'package_path': str(dst),
            'key_path': str(fake_key),
        })
    assert r.status_code == 500
    assert 'signing failed' in r.json()['detail']


# ── POST /store/install: available_services overrides ctx.available_services ──

def test_install_available_services_overrides_context():
    """Non-empty available_services replaces ctx.available_services before validation.

    Contrast: empty list (falsy) → branch skipped → default full services → allowed.
    Non-empty incomplete list → branch taken → ctx gets subset → missing services → fails.
    """
    # Branch NOT taken (empty list): default full services → validation passes
    r_no_override = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': [],
    })
    assert r_no_override.status_code == 200
    assert r_no_override.json()['allowed'] is True

    # Branch TAKEN (incomplete list): ctx.available_services overridden → missing services
    r_override = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'robot_class': 'humanoid',
        'runtime_version': '0.1.0',
        'available_services': ['perception.object_pose'],  # incomplete: many services missing
    })
    assert r_override.status_code == 200
    assert r_override.json()['allowed'] is False
    assert r_override.json()['reason'] == 'validation_failed'
