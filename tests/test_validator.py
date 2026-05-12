"""Tests for ETDReferenceValidator — schema, semantic, and compatibility checks."""
import json
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import (
    ETDReferenceValidator, RuntimeContext, load_runtime_context,
    _version_tuple, _min_runtime,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_FULL_SERVICES = [
    'perception.object_pose', 'perception.part_alignment',
    'manipulation.arm_control', 'force_control.contact_feedback',
    'workflow.job_context', 'state.robot_pose', 'state.arm_state',
    'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
    'vision.barcode_scan', 'quality.photo_capture', 'telemetry.metrics',
]

_ATLAS_SERVICES = _FULL_SERVICES + [
    'locomotion.walk_planner', 'perception.scene_map',
    'safety.human_detector', 'state.balance_state',
    'navigation.path_planner',
]


def _base_ctx() -> RuntimeContext:
    return RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=_FULL_SERVICES,
    )


def _atlas_ctx() -> RuntimeContext:
    return RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=_ATLAS_SERVICES,
        platform_profile='boston_dynamics_atlas',
    )


# ── All reference packages pass at level A ───────────────────────────────────

@pytest.mark.parametrize('pkg_name', [
    'etd.pickplace.basic',
    'etd.assembly.precision',
    'etd.inspect.vision',
    'etd.cobot.safeassist',
])
def test_reference_packages_level_a(pkg_name):
    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(ROOT / 'examples' / pkg_name)
    assert report.valid, f'{pkg_name}: {report.errors}'
    assert report.compatibility['level'] == 'A'
    assert report.compatibility['score'] == 1.0


def test_atlas_package_level_a():
    ctx = load_runtime_context(ROOT / 'runtime_context_atlas.json')
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.atlas.humanoid_walkfetch'
    )
    assert report.valid, report.errors
    assert report.compatibility['level'] == 'A'


def test_wia_welding_package_level_a():
    ctx = load_runtime_context(ROOT / 'runtime_context_wia.json')
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.hyundai.wia_welding'
    )
    assert report.valid, report.errors
    assert report.compatibility['level'] == 'A'


def test_mobed_transport_package_level_a():
    ctx = load_runtime_context(ROOT / 'runtime_context_mobed.json')
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.hyundai.mobed_transport'
    )
    assert report.valid, report.errors
    assert report.compatibility['level'] == 'A'


def test_vest_exoskeleton_package_level_a():
    ctx = load_runtime_context(ROOT / 'runtime_context_exo.json')
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.hyundai.vest_exoskeleton'
    )
    assert report.valid, report.errors
    assert report.compatibility['level'] == 'A'


# ── Missing services → level D ───────────────────────────────────────────────

def test_missing_services_yield_level_d():
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=['perception.object_pose'],
    )
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.pickplace.basic'
    )
    assert report.compatibility['level'] == 'D'
    assert report.compatibility['score'] < 0.5


# ── Schema errors are reported ────────────────────────────────────────────────

def test_schema_error_missing_required_field(tmp_path):
    """A manifest missing 'robotClass' under compatibility should produce a schema error."""
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'bad_pkg'
    shutil.copytree(src, dst)

    manifest = yaml.safe_load((dst / 'manifest.yaml').read_text())
    manifest['compatibility'].pop('robotClass', None)
    (dst / 'manifest.yaml').write_text(yaml.dump(manifest))

    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(dst)
    manifest_errs = report.schema_errors.get('manifest', [])
    # Either schema flags the error or the overall report is invalid
    assert not report.valid or len(manifest_errs) > 0


def test_schema_error_unknown_field(tmp_path):
    """A manifest with additionalProperties should produce a schema error."""
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'bad_pkg2'
    shutil.copytree(src, dst)

    manifest = yaml.safe_load((dst / 'manifest.yaml').read_text())
    manifest['__unknown_field__'] = 'should_fail'
    (dst / 'manifest.yaml').write_text(yaml.dump(manifest))

    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(dst)
    manifest_errs = report.schema_errors.get('manifest', [])
    assert len(manifest_errs) > 0 or not report.valid


# ── ValidationReport to_json roundtrip ───────────────────────────────────────

def test_report_to_json_roundtrip():
    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.pickplace.basic'
    )
    parsed = json.loads(report.to_json())
    assert parsed['valid'] is True
    assert parsed['compatibility']['level'] == 'A'
    assert 'schema_errors' in parsed
    assert 'semantic_checks' in parsed


# ── Semantic checks ───────────────────────────────────────────────────────────

def test_semantic_required_files_present():
    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.pickplace.basic'
    )
    assert report.semantic_checks.get('required_files_present') is True


def test_semantic_entrypoint_exists():
    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.pickplace.basic'
    )
    assert report.semantic_checks.get('entrypoint_exists') is True


def test_semantic_forbidden_caps_declared():
    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.cobot.safeassist'
    )
    assert report.semantic_checks.get('forbidden_caps_declared') is True


# ── load_runtime_context ──────────────────────────────────────────────────────

def test_load_base_runtime_context():
    ctx = load_runtime_context(ROOT / 'runtime_context.json')
    assert ctx.robot_class == 'humanoid'
    assert len(ctx.available_services) > 5


def test_load_atlas_runtime_context():
    ctx = load_runtime_context(ROOT / 'runtime_context_atlas.json')
    assert 'locomotion.walk_planner' in ctx.available_services
    assert 'state.balance_state' in ctx.available_services


def test_load_wia_runtime_context():
    ctx = load_runtime_context(ROOT / 'runtime_context_wia.json')
    assert any('welding' in s or 'seam' in s for s in ctx.available_services)


def test_load_mobed_runtime_context():
    ctx = load_runtime_context(ROOT / 'runtime_context_mobed.json')
    assert any('navigation' in s for s in ctx.available_services)


def test_load_exo_runtime_context():
    ctx = load_runtime_context(ROOT / 'runtime_context_exo.json')
    assert any('exo' in s for s in ctx.available_services)


# ── Compatibility level B (optional services missing) ─────────────────────────

def test_compat_level_b_optional_services_missing():
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=[
            'perception.object_pose', 'manipulation.arm_control',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
            # intentionally omit optional: perception.part_alignment, telemetry.metrics
        ],
    )
    report = ETDReferenceValidator(ctx).validate_package(ROOT / 'examples' / 'etd.pickplace.basic')
    assert report.compatibility['level'] == 'B'
    assert report.valid is True
    assert any('missing_optional_service' in w for w in report.compatibility['warnings'])


# ── Compatibility errors: runtime_too_old and robot_class_mismatch ────────────

def test_compat_runtime_too_old():
    ctx = RuntimeContext(
        runtime_version='0.0.1',
        robot_class='humanoid',
        available_services=_FULL_SERVICES,
    )
    report = ETDReferenceValidator(ctx).validate_package(ROOT / 'examples' / 'etd.pickplace.basic')
    assert 'runtime_too_old' in report.compatibility['errors']
    assert report.compatibility['level'] == 'D'


def test_compat_robot_class_mismatch():
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='exoskeleton',
        available_services=_FULL_SERVICES,
    )
    report = ETDReferenceValidator(ctx).validate_package(ROOT / 'examples' / 'etd.pickplace.basic')
    assert 'robot_class_mismatch' in report.compatibility['errors']
    assert report.compatibility['level'] == 'D'


# ── Parse error ───────────────────────────────────────────────────────────────

def test_parse_error_returns_invalid_report(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'bad_parse_pkg'
    shutil.copytree(src, dst)
    (dst / 'manifest.yaml').write_text(': broken: [yaml\n!!invalid')
    ctx = _base_ctx()
    report = ETDReferenceValidator(ctx).validate_package(dst)
    assert report.valid is False
    assert any('parse error' in e for e in report.errors)


# ── _version_tuple and _min_runtime helpers ───────────────────────────────────

def test_version_tuple_normal():
    assert _version_tuple('1.2.3') == (1, 2, 3)


def test_version_tuple_malformed_returns_zero():
    assert _version_tuple('not.a.version') == (0, 0, 0)


def test_min_runtime_none_returns_none():
    assert _min_runtime(None) is None


def test_min_runtime_empty_returns_none():
    assert _min_runtime('') is None


def test_min_runtime_with_spec():
    assert _min_runtime('>=0.5.0') == '0.5.0'


# ── Missing required files ────────────────────────────────────────────────────

def test_missing_required_file_returns_invalid(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_missing'
    shutil.copytree(src, dst)
    (dst / 'capabilities.json').unlink()
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.valid is False
    assert any('missing required file' in e and 'capabilities.json' in e for e in report.errors)


def test_missing_required_file_semantic_false(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_missing2'
    shutil.copytree(src, dst)
    (dst / 'tests' / 'acceptance_tests.yaml').unlink()
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('required_files_present') is False


# ── Semantic check failures ────────────────────────────────────────────────────

def test_semantic_name_mismatch(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_name'
    shutil.copytree(src, dst)
    skill = json.loads((dst / 'skill.json').read_text())
    skill['skillId'] = 'etd.wrong.name'
    (dst / 'skill.json').write_text(json.dumps(skill))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('name_matches_skill_id') is False
    assert any('name_matches_skill_id' in e for e in report.errors)


def test_semantic_version_mismatch(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_ver'
    shutil.copytree(src, dst)
    skill = json.loads((dst / 'skill.json').read_text())
    skill['version'] = '9.9.9'
    (dst / 'skill.json').write_text(json.dumps(skill))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('version_matches_skill_version') is False


def test_semantic_duplicate_profile_names(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_dup'
    shutil.copytree(src, dst)
    profiles = json.loads((dst / 'chs_profiles.json').read_text())
    dup = dict(profiles['profiles'][0])
    profiles['profiles'].append(dup)
    (dst / 'chs_profiles.json').write_text(json.dumps(profiles))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('profile_uniqueness') is False


def test_semantic_default_profile_missing(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_defprof'
    shutil.copytree(src, dst)
    skill = json.loads((dst / 'skill.json').read_text())
    skill['defaultChsProfile'] = 'nonexistent_profile'
    (dst / 'skill.json').write_text(json.dumps(skill))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('default_chs_profile_exists') is False


def test_semantic_no_lifecycle_events(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_noev'
    shutil.copytree(src, dst)
    events_doc = json.loads((dst / 'telemetry' / 'events.json').read_text())
    events_doc['events'] = ['custom.event.only']
    (dst / 'telemetry' / 'events.json').write_text(json.dumps(events_doc))
    manifest = yaml.safe_load((dst / 'manifest.yaml').read_text())
    manifest['telemetry']['events'] = ['custom.event.only']
    (dst / 'manifest.yaml').write_text(yaml.dump(manifest))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('telemetry_has_lifecycle_event') is False


def test_semantic_primitive_order_empty(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_noprim'
    shutil.copytree(src, dst)
    skill = json.loads((dst / 'skill.json').read_text())
    skill['primitiveOrder'] = []
    (dst / 'skill.json').write_text(json.dumps(skill))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('primitive_order_nonempty') is False


def test_semantic_invalid_force_window(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_fw'
    shutil.copytree(src, dst)
    profiles = json.loads((dst / 'chs_profiles.json').read_text())
    profiles['profiles'][0]['forceWindowN'] = [50.0, 10.0]  # max < min → invalid
    (dst / 'chs_profiles.json').write_text(json.dumps(profiles))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('force_windows_valid') is False


def test_semantic_payload_exceeds_constraint(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_payload'
    shutil.copytree(src, dst)
    profiles = json.loads((dst / 'chs_profiles.json').read_text())
    profiles['profiles'][0]['payloadKg'] = 999.0   # >> payloadKgMax=8
    (dst / 'chs_profiles.json').write_text(json.dumps(profiles))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('payload_within_constraints') is False


def test_semantic_capability_unsafe(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_unsafe'
    shutil.copytree(src, dst)
    caps = json.loads((dst / 'capabilities.json').read_text())
    caps['write'].append('command.servo_torque')
    (dst / 'capabilities.json').write_text(json.dumps(caps))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('capability_safe') is False


def test_semantic_missing_skill_intent_in_write(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_nointent'
    shutil.copytree(src, dst)
    caps = json.loads((dst / 'capabilities.json').read_text())
    caps['write'] = [c for c in caps['write'] if c != 'command.skill_intent']
    (dst / 'capabilities.json').write_text(json.dumps(caps))
    report = ETDReferenceValidator(_base_ctx()).validate_package(dst)
    assert report.semantic_checks.get('capability_safe') is False


# ── _load_schema returns None when schema file absent ─────────────────────────

def test_schema_warning_when_schema_file_missing(tmp_path, monkeypatch):
    import etd_reference_validator as _mod
    original_map = _mod._SCHEMA_MAP.copy()
    monkeypatch.setattr(_mod, '_SCHEMA_MAP', {
        **original_map,
        'manifest.yaml': 'does_not_exist.schema.json',
    })
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    report = _mod.ETDReferenceValidator(_base_ctx()).validate_package(src)
    assert any('schema file not found' in w for w in report.warnings)


# ── Compat score degrades with multiple errors ─────────────────────────────────

def test_compat_score_decreases_with_multiple_errors():
    ctx = RuntimeContext(
        runtime_version='0.0.1',        # runtime_too_old
        robot_class='exoskeleton',      # robot_class_mismatch
        available_services=[],          # all services missing
    )
    report = ETDReferenceValidator(ctx).validate_package(
        ROOT / 'examples' / 'etd.pickplace.basic'
    )
    assert report.compatibility['level'] == 'D'
    assert report.compatibility['score'] < 0.5
    assert len(report.compatibility['errors']) >= 3
