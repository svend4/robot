"""Tests for SkillStore and marketplace logic."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.skill_store import SkillStore, default_runtime_context, InstallDecision
from etd_reference_validator import RuntimeContext, load_runtime_context

_ATLAS_SERVICES = [
    'perception.object_pose', 'perception.part_alignment',
    'manipulation.arm_control', 'force_control.contact_feedback',
    'workflow.job_context', 'state.robot_pose', 'state.arm_state',
    'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
    'vision.barcode_scan', 'quality.photo_capture', 'telemetry.metrics',
    'locomotion.walk_planner', 'perception.scene_map',
    'safety.human_detector', 'state.balance_state',
    'navigation.path_planner',
]


@pytest.fixture
def store():
    return SkillStore(ROOT)


@pytest.fixture
def base_ctx():
    return default_runtime_context()


@pytest.fixture
def atlas_ctx():
    return load_runtime_context(ROOT / 'runtime_context_atlas.json')


# ── list_entries / list_skills ────────────────────────────────────────────────

def test_store_lists_seven_skills(store):
    entries = store.list_entries()
    assert len(entries) == 7


def test_store_list_skills_returns_dicts(store):
    skills = store.list_skills()
    assert all(isinstance(s, dict) for s in skills)
    ids = {s['skillId'] for s in skills}
    assert 'etd.pickplace.basic' in ids
    assert 'etd.atlas.humanoid_walkfetch' in ids


# ── find_skill / get_entry ────────────────────────────────────────────────────

def test_find_skill_found(store):
    entry = store.find_skill('etd.pickplace.basic')
    assert entry is not None
    assert entry['licenseModel'] == 'open_source'


def test_find_skill_not_found(store):
    entry = store.find_skill('etd.nonexistent')
    assert entry is None


def test_get_entry_found(store):
    entry = store.get_entry('etd.inspect.vision')
    assert entry is not None
    assert entry.requiresEntitlement is True


# ── validate_for_install ──────────────────────────────────────────────────────

def test_install_free_skill_allowed(store, base_ctx):
    decision = store.validate_for_install('etd.pickplace.basic', base_ctx)
    assert isinstance(decision, InstallDecision)
    assert decision.allowed is True
    assert decision.reason == 'install_allowed'
    assert decision.licenseModel == 'open_source'
    assert decision.pricingModel == 'free'


def test_install_commercial_no_token_denied(store, base_ctx):
    decision = store.validate_for_install('etd.assembly.precision', base_ctx)
    assert decision.allowed is False
    assert decision.reason == 'entitlement_required'


def test_install_commercial_with_token_allowed(store, base_ctx):
    decision = store.validate_for_install(
        'etd.assembly.precision', base_ctx, entitlement_token='valid-token'
    )
    assert decision.allowed is True


def test_install_all_free_skills_allowed(store, base_ctx):
    free_ids = ['etd.pickplace.basic', 'etd.atlas.humanoid_walkfetch']
    for skill_id in free_ids:
        if 'atlas' in skill_id or 'humanoid' in skill_id:
            ctx = store._load_json(ROOT / 'runtime_context_atlas.json')
            from etd_reference_validator import RuntimeContext
            atlas_ctx = RuntimeContext(
                runtime_version=ctx.get('runtime_version', '0.1.0'),
                robot_class=ctx.get('robot_class', 'humanoid'),
                available_services=ctx.get('available_services', _ATLAS_SERVICES),
                platform_profile=ctx.get('platform_profile', 'boston_dynamics_atlas'),
            )
            decision = store.validate_for_install(skill_id, atlas_ctx)
        else:
            decision = store.validate_for_install(skill_id, base_ctx)
        assert decision.allowed is True, f'{skill_id}: {decision.reason}'


def test_install_unknown_skill(store, base_ctx):
    decision = store.validate_for_install('etd.unknown.skill', base_ctx)
    assert decision.allowed is False
    assert decision.reason == 'skill_not_found'


def test_install_with_missing_services_denied(store):
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=['perception.object_pose'],
    )
    decision = store.validate_for_install('etd.pickplace.basic', ctx)
    assert decision.allowed is False
    assert decision.validationLevel == 'D'


# ── validate_listing ─────────────────────────────────────────────────────────

def test_validate_listing_returns_all_fields(store, base_ctx):
    result = store.validate_listing('etd.pickplace.basic', base_ctx)
    for key in ('skillId', 'version', 'licenseModel', 'pricingModel',
                'requiresEntitlement', 'validationLevel', 'installAllowed', 'reason'):
        assert key in result, f'Missing key: {key}'


# ── default_runtime_context ────────────────────────────────────────────────────

def test_default_context_has_required_services():
    ctx = default_runtime_context()
    assert 'perception.object_pose' in ctx.available_services
    assert 'state.safety_state' in ctx.available_services
    assert ctx.robot_class == 'humanoid'
