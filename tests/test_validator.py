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

from etd_reference_validator import ETDReferenceValidator, RuntimeContext, load_runtime_context


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
