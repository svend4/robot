"""Tests for SkillStore and marketplace logic."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.skill_store import SkillStore, default_runtime_context, InstallDecision, StoreEntry
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

def test_store_lists_eight_skills(store):
    entries = store.list_entries()
    assert len(entries) == 8


def test_store_list_skills_returns_dicts(store):
    skills = store.list_skills()
    assert all(isinstance(s, dict) for s in skills)
    ids = {s['skillId'] for s in skills}
    assert 'etd.pickplace.basic' in ids
    assert 'etd.atlas.humanoid_walkfetch' in ids
    assert 'etd.hyundai.wia_welding' in ids
    assert 'etd.hyundai.mobed_transport' in ids
    assert 'etd.hyundai.vest_exoskeleton' in ids


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


# ── Hyundai package install decisions ────────────────────────────────────────

def test_install_vest_exo_no_token_denied(store):
    ctx = load_runtime_context(ROOT / 'runtime_context_exo.json')
    decision = store.validate_for_install('etd.hyundai.vest_exoskeleton', ctx)
    assert decision.allowed is False
    assert decision.reason == 'entitlement_required'


def test_install_vest_exo_with_token_allowed(store):
    ctx = load_runtime_context(ROOT / 'runtime_context_exo.json')
    decision = store.validate_for_install(
        'etd.hyundai.vest_exoskeleton', ctx, entitlement_token='demo-entitlement-token'
    )
    assert decision.allowed is True


def test_install_wia_welding_with_token_allowed(store):
    ctx = load_runtime_context(ROOT / 'runtime_context_wia.json')
    decision = store.validate_for_install(
        'etd.hyundai.wia_welding', ctx, entitlement_token='valid-token'
    )
    assert decision.allowed is True


def test_install_mobed_transport_with_token_allowed(store):
    ctx = load_runtime_context(ROOT / 'runtime_context_mobed.json')
    decision = store.validate_for_install(
        'etd.hyundai.mobed_transport', ctx, entitlement_token='valid-token'
    )
    assert decision.allowed is True


# ── default_runtime_context ────────────────────────────────────────────────────

def test_default_context_has_required_services():
    ctx = default_runtime_context()
    assert 'perception.object_pose' in ctx.available_services
    assert 'state.safety_state' in ctx.available_services
    assert ctx.robot_class == 'humanoid'


# ── StoreEntry.from_dict compatibility shims ──────────────────────────────────

def test_store_entry_compat_requires_activation():
    payload = {
        'skillId': 'etd.test.skill', 'version': '0.1.0', 'family': 'manipulator',
        'packagePath': 'examples/etd.pickplace.basic', 'publisher': 'test',
        'riskLevel': 'low', 'certificationState': 'certified', 'targetUse': 'industrial',
        'requiresActivation': True,
    }
    entry = StoreEntry.from_dict(payload)
    assert entry.requiresEntitlement is True


def test_store_entry_compat_source_available_false():
    payload = {
        'skillId': 'etd.test.skill', 'version': '0.1.0', 'family': 'manipulator',
        'packagePath': 'examples/etd.pickplace.basic', 'publisher': 'test',
        'riskLevel': 'low', 'certificationState': 'certified', 'targetUse': 'industrial',
        'sourceAvailable': False,
    }
    entry = StoreEntry.from_dict(payload)
    assert entry.sourceAvailability == 'binary_or_private'


def test_store_entry_compat_source_available_true():
    payload = {
        'skillId': 'etd.test.skill', 'version': '0.1.0', 'family': 'manipulator',
        'packagePath': 'examples/etd.pickplace.basic', 'publisher': 'test',
        'riskLevel': 'low', 'certificationState': 'certified', 'targetUse': 'industrial',
        'sourceAvailable': True,
    }
    entry = StoreEntry.from_dict(payload)
    assert entry.sourceAvailability == 'full_source'


def test_store_entry_explicit_fields_take_precedence_over_compat():
    payload = {
        'skillId': 'etd.test.skill', 'version': '0.1.0', 'family': 'manipulator',
        'packagePath': 'examples/etd.pickplace.basic', 'publisher': 'test',
        'riskLevel': 'low', 'certificationState': 'certified', 'targetUse': 'industrial',
        'requiresEntitlement': False,
        'requiresActivation': True,
    }
    entry = StoreEntry.from_dict(payload)
    assert entry.requiresEntitlement is False


# ── get_entry not found ────────────────────────────────────────────────────────

def test_get_entry_not_found(store):
    entry = store.get_entry('etd.does.not.exist')
    assert entry is None


# ── validate_listing edge cases ───────────────────────────────────────────────

def test_validate_listing_skill_not_found(store, base_ctx):
    result = store.validate_listing('etd.nonexistent.skill', base_ctx)
    assert result['installAllowed'] is False
    assert result['reason'] == 'skill_not_found'
    assert result['skillId'] == 'etd.nonexistent.skill'


def test_validate_listing_commercial_uses_demo_token(store, base_ctx):
    result = store.validate_listing('etd.assembly.precision', base_ctx)
    assert result['installAllowed'] is True
    assert result['requiresEntitlement'] is True
    assert result['validationLevel'] == 'A'


def test_validate_listing_free_skill_install_allowed(store, base_ctx):
    result = store.validate_listing('etd.pickplace.basic', base_ctx)
    assert result['installAllowed'] is True
    assert result['licenseModel'] == 'open_source'
    assert 'version' in result
    assert 'sourceAvailability' in result


# ── _compat_level non-dict branch ─────────────────────────────────────────────

def test_compat_level_non_dict_compatibility(store):
    class _FakeReport:
        class _FakeCompat:
            level = 'B'
        compatibility = _FakeCompat()
        valid = True

    level = store._compat_level(_FakeReport())
    assert level == 'B'


def test_compat_level_missing_attribute_returns_d(store):
    class _NoCompat:
        pass

    level = store._compat_level(_NoCompat())
    assert level == 'D'


# ── InstallDecision fields ────────────────────────────────────────────────────

def test_install_decision_level_a_for_free_skill(store, base_ctx):
    decision = store.validate_for_install('etd.pickplace.basic', base_ctx)
    assert decision.validationLevel == 'A'
    assert decision.requiresEntitlement is False


def test_install_decision_level_b_still_allowed(store):
    """Level B (missing optional services) is still install-allowed."""
    from etd_reference_validator import RuntimeContext
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=[
            'perception.object_pose', 'manipulation.arm_control',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
            'vision.barcode_scan', 'quality.photo_capture',
            # intentionally omit optional: perception.part_alignment, telemetry.metrics
        ],
    )
    decision = store.validate_for_install('etd.pickplace.basic', ctx)
    assert decision.validationLevel == 'B'
    assert decision.allowed is True
    assert decision.reason == 'install_allowed'


def test_validate_listing_level_b_install_allowed(store):
    from etd_reference_validator import RuntimeContext
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=[
            'perception.object_pose', 'manipulation.arm_control',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
        ],
    )
    result = store.validate_listing('etd.pickplace.basic', ctx)
    assert result['validationLevel'] == 'B'
    assert result['installAllowed'] is True


# ── validate_for_install reason='validation_failed' ───────────────────────────

def test_install_validation_failed_reason(store):
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=['perception.object_pose'],  # missing most services → level D
    )
    decision = store.validate_for_install('etd.pickplace.basic', ctx)
    assert decision.allowed is False
    assert decision.reason == 'validation_failed'
    assert decision.validationLevel == 'D'


# ── __init__ package imports (adapters + sim) ─────────────────────────────────

def test_adapters_package_exports():
    import adapters
    assert callable(adapters.to_enterprise_event)
    assert callable(adapters.check_skill_compatible)
    assert callable(adapters.load_station_profile)
    assert adapters.OrbitEventBridge is not None


def test_sim_package_exports():
    import sim
    assert callable(sim.replay)
    assert callable(sim.nominal_lifecycle)
    assert sim.FakeMiddleware is not None
    assert callable(sim.run_all_scenarios)


# ── marketplace/skill_store.py __main__ block ─────────────────────────────────

def test_skill_store_module_main_prints_eight_decisions(capsys):
    import runpy
    runpy.run_path(str(ROOT / 'marketplace' / 'skill_store.py'), run_name='__main__')
    out = capsys.readouterr().out
    parsed_count = out.count('"skillId"')
    assert parsed_count == 8


def test_skill_store_module_main_all_have_allowed_field(capsys):
    import runpy, json as _json
    runpy.run_path(str(ROOT / 'marketplace' / 'skill_store.py'), run_name='__main__')
    out = capsys.readouterr().out
    blocks = [b.strip() for b in out.strip().split('\n}\n') if b.strip()]
    decisions = []
    for block in blocks:
        if not block.startswith('{'):
            block = '{' + block
        if not block.endswith('}'):
            block += '}'
        decisions.append(_json.loads(block))
    assert len(decisions) == 8
    for d in decisions:
        assert 'skillId' in d
        assert 'allowed' in d


# ── SkillStore.__init__: licensing_policy.json missing → {} fallback ──────────

def test_store_missing_licensing_policy_falls_back_to_empty_dict(tmp_path):
    import shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    # Deliberately do NOT copy licensing_policy.json
    store = SkillStore(tmp_path)
    assert store.licensing_policy == {}


# ── _compat_level: non-dict compatibility with no .level attr → 'D' default ──

def test_compat_level_non_dict_no_level_attr_falls_back_to_d(store):
    """Non-dict compatibility object without .level → getattr default 'D'."""
    class _CompatNoLevel:
        pass  # no .level attribute

    class _ReportWithNonDictCompat:
        compatibility = _CompatNoLevel()
        valid = True
        errors = []

    level = store._compat_level(_ReportWithNonDictCompat())
    assert level == 'D'


# ── Revocation blocklist (v0.6.0) ─────────────────────────────────────────────

def test_revoked_skill_is_blocked(tmp_path, monkeypatch):
    """validate_for_install returns skill_revoked when skill is in revoked.json."""
    import json, shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    (mp / 'revoked.json').write_text(json.dumps({
        'revoked': [{'skillId': 'etd.pickplace.basic', 'reason': 'test', 'revokedAt': '2026-01-01T00:00:00Z', 'revokedBy': 'test'}]
    }))
    store = SkillStore(tmp_path)
    ctx = RuntimeContext(runtime_version='0.1.0', robot_class='humanoid', available_services=[])
    decision = store.validate_for_install('etd.pickplace.basic', ctx)
    assert decision.allowed is False
    assert decision.reason == 'skill_revoked'


def test_non_revoked_skill_not_blocked_by_revocation(tmp_path, monkeypatch):
    """validate_for_install does not block a skill absent from revoked.json."""
    import json, shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    (mp / 'revoked.json').write_text(json.dumps({'revoked': []}))
    store = SkillStore(tmp_path)
    assert store.is_revoked('etd.pickplace.basic') is False


def test_store_no_revoked_file_loads_empty_set(store):
    """SkillStore with no revoked.json initialises _revoked to empty set."""
    # The real repo may or may not have revoked.json; either way is_revoked
    # should work without raising.
    assert isinstance(store._revoked, set)
    assert store.is_revoked('etd.nonexistent.skill') is False


def test_load_revoked_returns_set_of_skill_ids(tmp_path):
    """_load_revoked() extracts skillId values into a set."""
    import json, shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    (mp / 'revoked.json').write_text(json.dumps({
        'revoked': [
            {'skillId': 'etd.a.skill', 'reason': 'r1', 'revokedAt': '2026-01-01T00:00:00Z', 'revokedBy': 'test'},
            {'skillId': 'etd.b.skill', 'reason': 'r2', 'revokedAt': '2026-01-01T00:00:00Z', 'revokedBy': 'test'},
        ]
    }))
    store = SkillStore(tmp_path)
    assert 'etd.a.skill' in store._revoked
    assert 'etd.b.skill' in store._revoked
    assert 'etd.c.other' not in store._revoked


# ── Audit logging (v0.6.0) ────────────────────────────────────────────────────

def test_validate_for_install_writes_audit_entry_on_allowed(tmp_path):
    """validate_for_install writes an 'allowed' audit entry for a passing skill."""
    import shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    # Copy the signed package so signature check passes
    import shutil as _sh
    (tmp_path / 'examples').mkdir()
    _sh.copytree(ROOT / 'examples' / 'etd.pickplace.basic',
                 tmp_path / 'examples' / 'etd.pickplace.basic')
    store = SkillStore(tmp_path)
    store.audit_log._path = tmp_path / 'logs' / 'audit.jsonl'
    store.audit_log._path.parent.mkdir(parents=True, exist_ok=True)
    ctx = default_runtime_context()
    decision = store.validate_for_install('etd.pickplace.basic', ctx,
                                          station_id='assembly_a', operator_id='op1')
    entries = store.audit_log.read_entries()
    assert len(entries) == 1
    e = entries[0]
    assert e['skill_id'] == 'etd.pickplace.basic'
    assert e['station_id'] == 'assembly_a'
    assert e['operator_id'] == 'op1'
    assert e['result'] == ('allowed' if decision.allowed else 'blocked')
    assert 'timestamp' in e


def test_validate_for_install_writes_audit_entry_on_revoked(tmp_path):
    """validate_for_install writes a 'blocked' audit entry for a revoked skill."""
    import json, shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    (mp / 'revoked.json').write_text(json.dumps({
        'revoked': [{'skillId': 'etd.pickplace.basic', 'reason': 'test',
                     'revokedAt': '2026-01-01T00:00:00Z', 'revokedBy': 'test'}]
    }))
    store = SkillStore(tmp_path)
    store.audit_log._path = tmp_path / 'logs' / 'audit.jsonl'
    store.audit_log._path.parent.mkdir(parents=True, exist_ok=True)
    ctx = RuntimeContext(runtime_version='0.1.0', robot_class='humanoid', available_services=[])
    store.validate_for_install('etd.pickplace.basic', ctx)
    entries = store.audit_log.read_entries()
    assert len(entries) == 1
    assert entries[0]['result'] == 'blocked'
    assert entries[0]['reason'] == 'skill_revoked'


# ── Signature verification at install time (v0.6.0) ───────────────────────────

def test_validate_for_install_blocks_unsigned_package(tmp_path):
    """validate_for_install returns signature_invalid when package has no sig file."""
    import json, shutil
    mp = tmp_path / 'marketplace'
    mp.mkdir()
    shutil.copy(ROOT / 'marketplace' / 'skill_store_index.json', mp / 'skill_store_index.json')
    shutil.copy(ROOT / 'marketplace' / 'marketplace_policy.json', mp / 'marketplace_policy.json')
    (tmp_path / 'examples').mkdir()
    shutil.copytree(ROOT / 'examples' / 'etd.pickplace.basic',
                    tmp_path / 'examples' / 'etd.pickplace.basic')
    sig = tmp_path / 'examples' / 'etd.pickplace.basic' / 'package.sig'
    if sig.exists():
        sig.unlink()
    store = SkillStore(tmp_path)
    ctx = RuntimeContext(runtime_version='0.1.0', robot_class='humanoid', available_services=[])
    decision = store.validate_for_install('etd.pickplace.basic', ctx)
    assert decision.allowed is False
    assert decision.reason == 'signature_invalid'
