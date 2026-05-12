"""Tests for the ETD CLI (etd_cli.py) using Click's test runner."""
import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_cli import cli

runner = CliRunner()

_FULL_SERVICES_ARGS = [
    '--service', 'perception.object_pose',
    '--service', 'perception.part_alignment',
    '--service', 'manipulation.arm_control',
    '--service', 'force_control.contact_feedback',
    '--service', 'workflow.job_context',
    '--service', 'state.robot_pose',
    '--service', 'state.arm_state',
    '--service', 'state.wrist_state',
    '--service', 'state.safety_state',
    '--service', 'safety.zone_monitor',
    '--service', 'vision.barcode_scan',
    '--service', 'quality.photo_capture',
    '--service', 'telemetry.metrics',
]


# ── validate command ──────────────────────────────────────────────────────────

def test_validate_basic_package():
    result = runner.invoke(cli, ['validate', 'examples/etd.pickplace.basic',
                                 '--runtime-context', 'runtime_context.json'])
    assert result.exit_code == 0, result.output
    assert 'PASS' in result.output


def test_validate_all_packages():
    for pkg in ['etd.pickplace.basic', 'etd.assembly.precision',
                'etd.inspect.vision', 'etd.cobot.safeassist']:
        result = runner.invoke(cli, ['validate', f'examples/{pkg}',
                                     '--runtime-context', 'runtime_context.json'])
        assert result.exit_code == 0, f'{pkg}: {result.output}'


def test_validate_hyundai_packages():
    cases = [
        ('etd.atlas.humanoid_walkfetch', 'runtime_context_atlas.json'),
        ('etd.hyundai.wia_welding',      'runtime_context_wia.json'),
        ('etd.hyundai.mobed_transport',  'runtime_context_mobed.json'),
        ('etd.hyundai.vest_exoskeleton', 'runtime_context_exo.json'),
    ]
    for pkg, ctx in cases:
        result = runner.invoke(cli, ['validate', f'examples/{pkg}',
                                     '--runtime-context', ctx])
        assert result.exit_code == 0, f'{pkg}: {result.output}'
        assert 'PASS' in result.output, f'{pkg} expected PASS, got: {result.output}'


def test_validate_json_output():
    result = runner.invoke(cli, ['validate', 'examples/etd.pickplace.basic',
                                 '--runtime-context', 'runtime_context.json', '--json'])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed['valid'] is True
    assert parsed['compatibility']['level'] == 'A'


def test_validate_with_services_override():
    result = runner.invoke(cli, ['validate', 'examples/etd.pickplace.basic'] +
                           _FULL_SERVICES_ARGS)
    assert result.exit_code == 0, result.output


def test_validate_missing_services_fails():
    result = runner.invoke(cli, ['validate', 'examples/etd.pickplace.basic',
                                 '--service', 'perception.object_pose'])
    assert result.exit_code == 1
    assert 'FAIL' in result.output


def test_validate_nonexistent_path():
    result = runner.invoke(cli, ['validate', 'examples/etd.does.not.exist',
                                 '--runtime-context', 'runtime_context.json'])
    assert result.exit_code != 0


# ── list command ──────────────────────────────────────────────────────────────

def test_list_all():
    result = runner.invoke(cli, ['list'])
    assert result.exit_code == 0, result.output
    assert 'etd.pickplace.basic' in result.output
    assert 'etd.atlas.humanoid_walkfetch' in result.output
    assert 'etd.hyundai.wia_welding' in result.output
    assert '8 skill(s) found.' in result.output


def test_list_filter_family():
    result = runner.invoke(cli, ['list', '--family', 'pickplace'])
    assert result.exit_code == 0, result.output
    assert 'etd.pickplace.basic' in result.output
    assert '1 skill(s) found.' in result.output


def test_list_free_only():
    result = runner.invoke(cli, ['list', '--free'])
    assert result.exit_code == 0, result.output
    assert 'commercial' not in result.output


def test_list_json():
    result = runner.invoke(cli, ['list', '--json'])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) == 8


# ── info command ──────────────────────────────────────────────────────────────

def test_info_found():
    result = runner.invoke(cli, ['info', 'etd.pickplace.basic'])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed['skillId'] == 'etd.pickplace.basic'
    assert 'licenseModel' in parsed


def test_info_not_found():
    result = runner.invoke(cli, ['info', 'etd.does.not.exist'])
    assert result.exit_code == 1
    assert 'not found' in result.output.lower()


def test_info_atlas():
    result = runner.invoke(cli, ['info', 'etd.atlas.humanoid_walkfetch'])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed['platformTarget'] == 'boston_dynamics_atlas'


def test_info_vest_exoskeleton():
    result = runner.invoke(cli, ['info', 'etd.hyundai.vest_exoskeleton'])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed['skillId'] == 'etd.hyundai.vest_exoskeleton'
    assert parsed['family'] == 'assist'
    assert parsed['requiresEntitlement'] is True


def test_install_vest_exo_requires_entitlement():
    result = runner.invoke(cli, ['install', 'etd.hyundai.vest_exoskeleton',
                                 '--runtime-context', 'runtime_context_exo.json'])
    assert result.exit_code == 1
    assert 'entitlement' in result.output.lower()


def test_install_vest_exo_with_token():
    result = runner.invoke(cli, ['install', 'etd.hyundai.vest_exoskeleton',
                                 '--runtime-context', 'runtime_context_exo.json',
                                 '--token', 'valid-token'])
    assert result.exit_code == 0, result.output
    assert 'allowed' in result.output.lower()


# ── install command ───────────────────────────────────────────────────────────

def test_install_free_skill_allowed():
    result = runner.invoke(cli, ['install', 'etd.pickplace.basic',
                                 '--runtime-context', 'runtime_context.json'])
    assert result.exit_code == 0, result.output
    assert 'allowed' in result.output.lower()


def test_install_entitlement_required_no_token():
    result = runner.invoke(cli, ['install', 'etd.assembly.precision',
                                 '--runtime-context', 'runtime_context.json'])
    assert result.exit_code == 1
    assert 'entitlement' in result.output.lower()


def test_install_with_token():
    result = runner.invoke(cli, ['install', 'etd.assembly.precision',
                                 '--token', 'valid-token',
                                 '--runtime-context', 'runtime_context.json'])
    assert result.exit_code == 0, result.output
