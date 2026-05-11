"""Tests for station profile loader and compatibility checker."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.station_profile_loader import (
    StationProfile,
    StationCompatibilityResult,
    load_station_profile,
    load_all_profiles,
    check_skill_compatible,
    is_skill_allowed,
)

_PROFILES_DIR = ROOT / 'station_profiles'


# ── Load helpers ──────────────────────────────────────────────────────────────

def test_load_weld_station_profile():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    assert p.station_id == 'weld_station_a'
    assert 'weld' in p.allowed_skill_families
    assert p.max_payload_kg == 2.0
    assert p.requires_human_aware is True
    assert p.platform == 'hyundai_wia_h_motion_cobot'


def test_load_mobed_station_profile():
    p = load_station_profile(_PROFILES_DIR / 'mobed_logistics_a.json')
    assert p.station_id == 'mobed_logistics_a'
    assert 'transport' in p.allowed_skill_families
    assert p.max_payload_kg == 100.0
    assert p.platform == 'hyundai_mobed_amr'


def test_load_humanoid_station_profile():
    p = load_station_profile(_PROFILES_DIR / 'humanoid_hmgma_a.json')
    assert p.station_id == 'humanoid_hmgma_a'
    assert 'humanoid' in p.allowed_skill_families
    assert p.requires_human_aware is True
    assert p.platform == 'boston_dynamics_atlas'


def test_load_all_profiles():
    profiles = load_all_profiles(_PROFILES_DIR)
    assert len(profiles) >= 6
    assert 'weld_station_a' in profiles
    assert 'mobed_logistics_a' in profiles
    assert 'humanoid_hmgma_a' in profiles
    assert isinstance(profiles['weld_station_a'], StationProfile)


def test_load_all_profiles_keyed_by_station_id():
    profiles = load_all_profiles(_PROFILES_DIR)
    for station_id, profile in profiles.items():
        assert station_id == profile.station_id


# ── StationProfile methods ────────────────────────────────────────────────────

def test_allows_family_true():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    assert p.allows_family('weld') is True
    assert p.allows_family('inspect') is True


def test_allows_family_false():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    assert p.allows_family('humanoid') is False
    assert p.allows_family('transport') is False


def test_to_dict_roundtrip():
    p = load_station_profile(_PROFILES_DIR / 'humanoid_hmgma_a.json')
    d = p.to_dict()
    p2 = StationProfile.from_dict(d)
    assert p2.station_id == p.station_id
    assert p2.allowed_skill_families == p.allowed_skill_families
    assert p2.max_payload_kg == p.max_payload_kg
    assert p2.platform == p.platform


# ── check_skill_compatible — happy path ───────────────────────────────────────

def test_compatible_weld_skill_at_weld_station():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    result = check_skill_compatible(
        p,
        skill_family='weld',
        payload_kg=1.5,
        requires_human_aware=False,
        required_services=['welding.torch_control', 'manipulation.arm_control'],
        skill_id='etd.hyundai.wia_welding',
    )
    assert result.compatible is True
    assert result.reason == 'station_compatible'
    assert result.missing_services == []


def test_compatible_transport_at_mobed_station():
    p = load_station_profile(_PROFILES_DIR / 'mobed_logistics_a.json')
    result = check_skill_compatible(
        p,
        skill_family='transport',
        payload_kg=50.0,
        requires_human_aware=True,
        required_services=['navigation.path_planner', 'manipulation.lift_control'],
        skill_id='etd.hyundai.mobed_transport',
    )
    assert result.compatible is True


def test_compatible_humanoid_at_atlas_station():
    p = load_station_profile(_PROFILES_DIR / 'humanoid_hmgma_a.json')
    result = check_skill_compatible(
        p,
        skill_family='humanoid',
        payload_kg=5.0,
        requires_human_aware=True,
        required_services=['locomotion.walk_planner', 'state.balance_state'],
        skill_id='etd.atlas.humanoid_walkfetch',
    )
    assert result.compatible is True


# ── check_skill_compatible — failure cases ────────────────────────────────────

def test_incompatible_wrong_family():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    result = check_skill_compatible(
        p,
        skill_family='transport',
        payload_kg=1.0,
        requires_human_aware=False,
        required_services=[],
    )
    assert result.compatible is False
    assert 'transport' in result.reason
    assert 'not_allowed' in result.reason


def test_incompatible_payload_exceeded():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    result = check_skill_compatible(
        p,
        skill_family='weld',
        payload_kg=5.0,  # weld_station max is 2.0
        requires_human_aware=False,
        required_services=[],
    )
    assert result.compatible is False
    assert '2.0' in result.reason


def test_incompatible_missing_service():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    result = check_skill_compatible(
        p,
        skill_family='weld',
        payload_kg=1.0,
        requires_human_aware=False,
        required_services=['welding.torch_control', 'nonexistent.service'],
    )
    assert result.compatible is False
    assert result.reason == 'missing_services_at_station'
    assert 'nonexistent.service' in result.missing_services


def test_incompatible_payload_at_weld_boundary():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    result_ok = check_skill_compatible(p, 'weld', 2.0, False, [])
    result_fail = check_skill_compatible(p, 'weld', 2.001, False, [])
    assert result_ok.compatible is True
    assert result_fail.compatible is False


# ── human-aware warning ───────────────────────────────────────────────────────

def test_human_aware_warning_when_station_does_not_enforce():
    p = load_station_profile(_PROFILES_DIR / 'logistics_cell_a.json')
    result = check_skill_compatible(
        p,
        skill_family='pickplace',
        payload_kg=1.0,
        requires_human_aware=True,
        required_services=[],
    )
    assert result.compatible is True
    assert any('human_aware' in w for w in result.warnings)


def test_no_human_aware_warning_when_station_enforces():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    result = check_skill_compatible(
        p,
        skill_family='weld',
        payload_kg=1.0,
        requires_human_aware=True,
        required_services=[],
    )
    assert result.compatible is True
    assert result.warnings == []


# ── Legacy helper ──────────────────────────────────────────────────────────────

def test_is_skill_allowed_with_profile_object():
    p = load_station_profile(_PROFILES_DIR / 'weld_station_a.json')
    assert is_skill_allowed(p, 'weld') is True
    assert is_skill_allowed(p, 'humanoid') is False


def test_is_skill_allowed_with_dict():
    d = {'allowed_skill_families': ['weld', 'inspect']}
    assert is_skill_allowed(d, 'weld') is True
    assert is_skill_allowed(d, 'transport') is False


# ── API: GET /store/stations ──────────────────────────────────────────────────

def test_api_list_stations():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r = client.get('/store/stations')
    assert r.status_code == 200
    body = r.json()
    assert body['count'] >= 6
    ids = {s['station_id'] for s in body['stations']}
    assert 'weld_station_a' in ids
    assert 'mobed_logistics_a' in ids
    assert 'humanoid_hmgma_a' in ids


def test_api_get_station_found():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r = client.get('/store/stations/weld_station_a')
    assert r.status_code == 200
    body = r.json()
    assert body['station_id'] == 'weld_station_a'
    assert 'weld' in body['allowed_skill_families']


def test_api_get_station_not_found():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r = client.get('/store/stations/does_not_exist')
    assert r.status_code == 404


def test_api_install_with_compatible_station():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'robot_class': 'humanoid',
        'available_services': [
            'perception.object_pose', 'perception.part_alignment',
            'manipulation.arm_control', 'force_control.contact_feedback',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
            'vision.barcode_scan', 'quality.photo_capture', 'telemetry.metrics',
        ],
        'station_id': 'cobot_zone_a',
    })
    assert r.status_code == 200
    body = r.json()
    assert body['allowed'] is True
    assert body['station_compatible'] is True
    assert body['station_reason'] == 'station_compatible'


def test_api_install_with_incompatible_station_family():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'robot_class': 'humanoid',
        'available_services': ['perception.object_pose'],
        'station_id': 'weld_station_a',
    })
    assert r.status_code == 200
    body = r.json()
    assert 'station_compatible' in body
    assert body['station_compatible'] is False


def test_api_install_station_not_found():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r = client.post('/store/install', json={
        'skill_id': 'etd.pickplace.basic',
        'station_id': 'no_such_station',
    })
    assert r.status_code == 404


# ── CLI: stations command ──────────────────────────────────────────────────────

def test_cli_stations_list():
    from click.testing import CliRunner
    from etd_cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ['stations'])
    assert result.exit_code == 0, result.output
    assert 'weld_station_a' in result.output
    assert 'mobed_logistics_a' in result.output
    assert 'station(s) found.' in result.output


def test_cli_stations_json():
    import json as _json
    from click.testing import CliRunner
    from etd_cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ['stations', '--json'])
    assert result.exit_code == 0, result.output
    parsed = _json.loads(result.output)
    assert isinstance(parsed, list)
    ids = [s['station_id'] for s in parsed]
    assert 'weld_station_a' in ids


def test_cli_validate_with_compatible_station():
    from click.testing import CliRunner
    from etd_cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, [
        'validate', 'examples/etd.hyundai.wia_welding',
        '--runtime-context', 'runtime_context_wia.json',
        '--station-profile', 'station_profiles/weld_station_a.json',
    ])
    assert result.exit_code == 0, result.output
    assert 'COMPATIBLE' in result.output
    assert 'weld_station_a' in result.output


def test_cli_validate_with_incompatible_station():
    from click.testing import CliRunner
    from etd_cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, [
        'validate', 'examples/etd.hyundai.wia_welding',
        '--runtime-context', 'runtime_context_wia.json',
        '--station-profile', 'station_profiles/mobed_logistics_a.json',
    ])
    assert result.exit_code == 0, result.output
    assert 'INCOMPATIBLE' in result.output


def test_cli_install_with_station_profile():
    from click.testing import CliRunner
    from etd_cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, [
        'install', 'etd.pickplace.basic',
        '--runtime-context', 'runtime_context.json',
        '--station-profile', 'station_profiles/cobot_zone_a.json',
    ])
    assert result.exit_code == 0, result.output
    assert 'ALLOWED' in result.output
    assert 'cobot_zone_a' in result.output
