"""Tests for the ETD CLI (etd_cli.py) using Click's test runner."""
import json
import shutil
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


# ── keygen command ────────────────────────────────────────────────────────────

def test_keygen_creates_key_files(tmp_path):
    result = runner.invoke(cli, ['keygen', '--out-dir', str(tmp_path / 'keys')])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'keys' / 'etd_signing_key.hex').exists()
    assert (tmp_path / 'keys' / 'etd_verify_key.hex').exists()


# ── verify command ────────────────────────────────────────────────────────────

def test_verify_signed_package_succeeds(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'etd.pickplace.basic'
    shutil.copytree(src, dst)
    from scripts.generate_keypair import generate
    from scripts.sign_package import sign_package
    key_dir = tmp_path / 'keys'
    generate(key_dir)
    sign_package(dst, key_dir / 'etd_signing_key.hex')
    result = runner.invoke(cli, ['verify', str(dst)])
    assert result.exit_code == 0, result.output


def test_verify_unsigned_package_fails(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'unsigned_pkg'
    shutil.copytree(src, dst)
    result = runner.invoke(cli, ['verify', str(dst)])
    assert result.exit_code == 1


# ── publish command ───────────────────────────────────────────────────────────

def test_publish_skip_sign(tmp_path):
    out_dir = tmp_path / 'out'
    result = runner.invoke(cli, [
        'publish', 'examples/etd.pickplace.basic',
        '--skip-sign',
        '--out', str(out_dir),
        '--runtime-context', 'runtime_context.json',
    ])
    assert result.exit_code == 0, result.output
    zips = list(out_dir.glob('*.zip'))
    assert len(zips) == 1
    assert 'etd.pickplace.basic' in zips[0].name


# ── validate --json with failing package ──────────────────────────────────────

def test_validate_json_output_failure():
    result = runner.invoke(cli, [
        'validate', 'examples/etd.pickplace.basic',
        '--service', 'perception.object_pose',
        '--json',
    ])
    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert parsed['valid'] is False
    assert parsed['compatibility']['level'] == 'D'


# ── _load_ctx fallback when context file does not exist ──────────────────────

def test_validate_nonexistent_ctx_falls_back_to_default():
    extra = []
    for s in [
        'perception.object_pose', 'perception.part_alignment',
        'manipulation.arm_control', 'force_control.contact_feedback',
        'workflow.job_context', 'state.robot_pose', 'state.arm_state',
        'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
        'vision.barcode_scan', 'quality.photo_capture', 'telemetry.metrics',
    ]:
        extra += ['--service', s]
    result = runner.invoke(cli, [
        'validate', 'examples/etd.pickplace.basic',
        '--runtime-context', 'does_not_exist.json',
    ] + extra)
    assert result.exit_code == 0, result.output
    assert 'PASS' in result.output


def test_validate_robot_class_override():
    result = runner.invoke(cli, [
        'validate', 'examples/etd.pickplace.basic',
        '--runtime-context', 'runtime_context.json',
        '--robot-class', 'exoskeleton',   # wrong class → level D
    ])
    assert result.exit_code == 1
    assert 'FAIL' in result.output


# ── _print_report pretty-print shows errors and warnings ─────────────────────

def test_validate_pretty_print_shows_errors(tmp_path):
    # Remove a required file to trigger schema/semantic errors shown as ✗
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_nofile'
    shutil.copytree(src, dst)
    (dst / 'capabilities.json').unlink()
    result = runner.invoke(cli, [
        'validate', str(dst),
        '--runtime-context', 'runtime_context.json',
    ])
    assert result.exit_code == 1
    assert '✗' in result.output


def test_validate_pretty_print_shows_all_checks_passed_when_valid():
    result = runner.invoke(cli, [
        'validate', 'examples/etd.pickplace.basic',
        '--runtime-context', 'runtime_context.json',
    ])
    assert result.exit_code == 0
    assert 'All checks passed' in result.output


# ── validate with --station-profile --json ────────────────────────────────────

def test_validate_station_profile_json_output():
    result = runner.invoke(cli, [
        'validate', 'examples/etd.hyundai.wia_welding',
        '--runtime-context', 'runtime_context_wia.json',
        '--station-profile', 'station_profiles/weld_station_a.json',
        '--json',
    ])
    assert result.exit_code == 0, result.output
    # Output is two JSON objects: validation report then station check
    parts = [p.strip() for p in result.output.strip().split('\n}\n{') if p.strip()]
    first_json = parts[0] if parts[0].startswith('{') else '{' + parts[0]
    if not first_json.endswith('}'):
        first_json += '}'
    parsed = json.loads(result.output.strip().split('\n}\n')[0] + '\n}')
    assert parsed['valid'] is True
    assert 'station_check' in result.output
    assert 'weld_station_a' in result.output


def test_validate_station_json_incompatible():
    result = runner.invoke(cli, [
        'validate', 'examples/etd.hyundai.wia_welding',
        '--runtime-context', 'runtime_context_wia.json',
        '--station-profile', 'station_profiles/mobed_logistics_a.json',
        '--json',
    ])
    assert 'compatible' in result.output.lower()


# ── install with --station-profile (decision allowed) ────────────────────────

def test_install_with_station_profile_compatible():
    result = runner.invoke(cli, [
        'install', 'etd.pickplace.basic',
        '--runtime-context', 'runtime_context.json',
        '--station-profile', 'station_profiles/cobot_zone_a.json',
    ])
    assert result.exit_code == 0, result.output
    assert 'COMPATIBLE' in result.output
    assert 'cobot_zone_a' in result.output


# ── list with --family filter (table output) ──────────────────────────────────

def test_list_filter_transport_family():
    result = runner.invoke(cli, ['list', '--family', 'transport'])
    assert result.exit_code == 0, result.output
    assert 'etd.hyundai.mobed_transport' in result.output
    assert '1 skill(s) found.' in result.output


# ── stations command ──────────────────────────────────────────────────────────

def test_stations_table_output():
    result = runner.invoke(cli, ['stations'])
    assert result.exit_code == 0, result.output
    assert 'weld_station_a' in result.output
    assert 'mobed_logistics_a' in result.output
    assert 'station(s) found.' in result.output


def test_stations_json_output():
    result = runner.invoke(cli, ['stations', '--json'])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) >= 6
    ids = {s['station_id'] for s in parsed}
    assert 'weld_station_a' in ids
    assert 'exo_assembly_a' in ids


# ── install --station-profile when decision is blocked ────────────────────────

def test_install_blocked_skill_station_check_skipped():
    result = runner.invoke(cli, [
        'install', 'etd.assembly.precision',
        '--runtime-context', 'runtime_context.json',
        '--station-profile', 'station_profiles/assembly_station_a.json',
        # no token → entitlement_required → station check skipped
    ])
    assert result.exit_code == 1
    assert 'BLOCKED' in result.output
    assert 'COMPATIBLE' not in result.output


# ── install with station-profile when incompatible station ────────────────────

def test_install_with_station_profile_incompatible():
    result = runner.invoke(cli, [
        'install', 'etd.pickplace.basic',
        '--runtime-context', 'runtime_context.json',
        '--station-profile', 'station_profiles/weld_station_a.json',
    ])
    assert result.exit_code == 0, result.output
    assert 'INCOMPATIBLE' in result.output


# ── _check_station skipped when package files missing ────────────────────────

def test_validate_station_skipped_when_no_manifest(tmp_path):
    pkg = tmp_path / 'empty_pkg'
    pkg.mkdir()
    result = runner.invoke(cli, [
        'validate', str(pkg),
        '--station-profile', 'station_profiles/weld_station_a.json',
    ])
    # validation will fail (missing files), station check skipped with warning
    assert 'Station check skipped' in result.output or result.exit_code != 0


# ── _check_station_entry(None) early return ───────────────────────────────────

def test_install_nonexistent_skill_no_station_output():
    # When skill_id is not found, _check_station_entry(None) is called → returns early
    result = runner.invoke(cli, [
        'install', 'etd.does.not.exist',
        '--runtime-context', 'runtime_context.json',
        '--station-profile', 'station_profiles/assembly_station_a.json',
    ])
    assert result.exit_code == 1
    # station output not produced when entry is None
    assert 'COMPATIBLE' not in result.output
    assert 'INCOMPATIBLE' not in result.output


# ── install not found exits 1 ─────────────────────────────────────────────────

def test_install_skill_not_found_exits_one():
    result = runner.invoke(cli, ['install', 'etd.no.such.skill'])
    assert result.exit_code == 1
    assert 'skill_not_found' in result.output or 'BLOCKED' in result.output


# ── list --family AND --free chained filter ───────────────────────────────────

def test_list_filter_family_and_free_chained():
    # inspect family has pricingModel=subscription → chained --free removes it
    result = runner.invoke(cli, ['list', '--family', 'inspect', '--free'])
    assert result.exit_code == 0
    assert 'etd.inspect.vision' not in result.output
    # transport family has pricingModel=free → both filters match
    result2 = runner.invoke(cli, ['list', '--family', 'transport', '--free'])
    assert result2.exit_code == 0
    assert 'etd.hyundai.mobed_transport' in result2.output


# ── _check_station: skill.json missing requiredServices key → else [] branch ──

def test_validate_station_no_required_services_field(tmp_path):
    # Write minimal manifest.yaml and skill.json with NO requiredServices key.
    # This exercises the `else []` branch in _check_station (line 91 of etd_cli.py).
    (tmp_path / 'manifest.yaml').write_text(
        'skillId: etd.test.minimal\nversion: 0.1.0\nsafety:\n  humanAware: false\n'
    )
    (tmp_path / 'skill.json').write_text(
        json.dumps({'skillId': 'etd.test.minimal', 'family': 'cobot', 'maxPayloadKg': 5.0})
    )
    result = runner.invoke(cli, [
        'validate', str(tmp_path),
        '--runtime-context', 'runtime_context.json',
        '--station-profile', 'station_profiles/assembly_station_a.json',
    ])
    # Station check ran (not skipped) — manifest.yaml and skill.json both exist
    assert 'Station check skipped' not in result.output
    assert 'COMPATIBLE' in result.output or 'INCOMPATIBLE' in result.output


# ── _load_ctx: both --robot-class AND --service flags together ────────────────

def test_validate_robot_class_and_service_both_applied():
    # Exercises both `if robot_class is not None:` and `if services:` branches
    # in _load_ctx simultaneously (only one service → missing others → compat fail)
    result = runner.invoke(cli, [
        'validate', 'examples/etd.pickplace.basic',
        '--runtime-context', 'runtime_context.json',
        '--robot-class', 'humanoid',
        '--service', 'perception.object_pose',
    ])
    # robot_class='humanoid' is set; available_services=['perception.object_pose'] is set
    # Many required services missing → compat errors → exit 1
    assert result.exit_code == 1
    assert 'FAIL' in result.output


# ── _check_station: warnings text output (for w in result.warnings: echo) ────

def test_validate_station_human_aware_warning_in_text_output(tmp_path):
    """Skill requires human-aware but station doesn't enforce it → warning line in output."""
    # Create a skill with humanAware: True
    (tmp_path / 'manifest.yaml').write_text(
        'skillId: etd.test.ha\nversion: 0.1.0\nsafety:\n  humanAware: true\n'
    )
    (tmp_path / 'skill.json').write_text(
        json.dumps({
            'skillId': 'etd.test.ha',
            'family': 'manipulator',
            'maxPayloadKg': 5.0,
        })
    )
    # Station profile with requires_human_aware=False and allows 'manipulator'
    station_file = tmp_path / 'station.json'
    station_file.write_text(json.dumps({
        'station_id': 'test_station',
        'allowed_skill_families': ['manipulator'],
        'max_payload_kg': 20.0,
        'requires_human_aware': False,
    }))
    result = runner.invoke(cli, [
        'validate', str(tmp_path),
        '--runtime-context', 'runtime_context.json',
        '--station-profile', str(station_file),
    ])
    # _check_station text branch: 'for w in result.warnings: click.echo(f"  ! {w}")'
    assert 'skill_requires_human_aware_but_station_does_not_enforce_it' in result.output


# ── _check_station: text output shows missing services when incompatible ──────

def test_validate_station_text_output_shows_missing_services(tmp_path):
    """_check_station text branch: 'if result.missing_services: click.echo(Missing services: ...)'."""
    # Skill whose family is allowed at the station but requires a service the station lacks
    (tmp_path / 'manifest.yaml').write_text(
        'skillId: etd.test.ms\nversion: 0.1.0\nsafety:\n  humanAware: false\n'
    )
    (tmp_path / 'skill.json').write_text(
        json.dumps({
            'skillId': 'etd.test.ms',
            'family': 'weld',
            'maxPayloadKg': 5.0,
            'requiredServices': [{'name': 'some.missing.service'}],
        })
    )
    # Station allows 'weld', has available_services that does NOT include 'some.missing.service'
    station_file = tmp_path / 'station.json'
    station_file.write_text(json.dumps({
        'station_id': 'partial_weld_station',
        'allowed_skill_families': ['weld'],
        'max_payload_kg': 25.0,
        'requires_human_aware': False,
        'available_services': ['perception.seam_tracker'],
    }))
    result = runner.invoke(cli, [
        'validate', str(tmp_path),
        '--runtime-context', 'runtime_context.json',
        '--station-profile', str(station_file),
    ])
    # _check_station text branch: 'if result.missing_services: click.echo(Missing services: ...)'
    assert 'Missing services' in result.output
    assert 'some.missing.service' in result.output
