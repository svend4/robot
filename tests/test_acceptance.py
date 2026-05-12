"""Pytest wrapper around sim/acceptance_runner.py — runs all 39 YAML scenarios."""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.acceptance_runner import (
    AcceptanceMiddleware,
    TestResult,
    SuiteResult,
    _run_test,
    _load_run,
    _print_suite,
    run_suite,
    main as _acc_main,
)

_ALL_SKILLS = [
    'etd.pickplace.basic',
    'etd.assembly.precision',
    'etd.inspect.vision',
    'etd.cobot.safeassist',
    'etd.atlas.humanoid_walkfetch',
    'etd.hyundai.wia_welding',
    'etd.hyundai.mobed_transport',
    'etd.hyundai.vest_exoskeleton',
]


@pytest.mark.parametrize('skill_id', _ALL_SKILLS)
def test_acceptance_suite(skill_id):
    random.seed(42)  # deterministic classify_result confidence for inspect.vision
    suite = run_suite(skill_id)
    failures = [r for r in suite.results if not r.passed]
    assert len(failures) == 0, (
        f'{skill_id}: {len(failures)} scenario(s) failed:\n' +
        '\n'.join(
            f'  {r.test_id}: status={r.status!r}, reason={r.reason!r}'
            + (f', msg={r.failure_message!r}' if r.failure_message else '')
            for r in failures
        )
    )


# ── AcceptanceMiddleware.read() topic coverage ────────────────────────────────

def _mw(**kw):
    return AcceptanceMiddleware(**kw)


def test_mw_read_safety_state():
    mw = _mw()
    s = mw.read('state.safety_state')
    assert s['human_in_forbidden_zone'] is False
    assert s['human_ready_signal'] is True


def test_mw_read_force_contact_feedback():
    mw = _mw()
    fb = mw.read('force_control.contact_feedback')
    assert 'normal_force_n' in fb
    assert fb['normal_force_n'] == 12.0


def test_mw_read_part_alignment():
    mw = _mw()
    pa = mw.read('perception.part_alignment')
    assert pa['aligned'] is True
    assert 'confidence' in pa
    assert 'offset_mm' in pa


def test_mw_read_camera_frame_increments():
    mw = _mw()
    f1 = mw.read('perception.camera_frame')
    f2 = mw.read('perception.camera_frame')
    assert f1['frame_id'] == 1
    assert f2['frame_id'] == 2
    assert f1['width'] == 1920


def test_mw_read_scene_map():
    mw = _mw()
    sm = mw.read('perception.scene_map')
    assert sm['map_ready'] is True
    assert sm['obstacles'] == []


def test_mw_read_balance_state():
    mw = _mw()
    bs = mw.read('state.balance_state')
    assert bs['stable'] is True
    assert bs['gait'] == 'stand'


def test_mw_read_object_pose():
    mw = _mw()
    op = mw.read('perception.object_pose')
    assert op['object_class'] == 'automotive_part'
    assert 'confidence' in op


def test_mw_read_seam_tracker():
    mw = _mw()
    st = mw.read('perception.seam_tracker')
    assert st['seam_found'] is True
    assert 'offset_mm' in st


def test_mw_read_weld_inspection():
    mw = _mw()
    wi = mw.read('vision.weld_inspection')
    assert wi['pass'] is True
    assert wi['defects'] == []
    assert wi['confidence'] == 0.97


def test_mw_read_obstacle_detector():
    mw = _mw()
    od = mw.read('perception.obstacle_detector')
    assert od['obstacles'] == []
    assert od['clear'] is True


def test_mw_read_path_planner():
    mw = _mw()
    pp = mw.read('navigation.path_planner')
    assert pp['path_ready'] is True
    assert pp['estimated_time_s'] == 30


def test_mw_read_lift_control():
    mw = _mw()
    lc = mw.read('manipulation.lift_control')
    assert lc['lift_ready'] is True
    assert lc['current_height_mm'] == 0


def test_mw_read_intent_detector():
    mw = _mw()
    id_ = mw.read('perception.intent_detector')
    assert id_['mode'] == 'overhead'
    assert id_['direction'] == 'up'


def test_mw_read_exo_joint_state():
    mw = _mw()
    ej = mw.read('state.exo_joint_state')
    assert ej['calibrated'] is True
    assert ej['torque_within_limits'] is True


def test_mw_read_fatigue_monitor():
    mw = _mw()
    fm = mw.read('state.fatigue_monitor')
    assert 'fatigue_pct' in fm
    assert fm['session_sec'] == 0


def test_mw_read_imu_pose():
    mw = _mw()
    ip = mw.read('perception.imu_pose')
    assert ip['valid'] is True
    assert 'roll_deg' in ip


def test_mw_read_unknown_topic_returns_none():
    mw = _mw()
    assert mw.read('some.unknown.topic') is None


# ── AcceptanceMiddleware.publish() inject_at branches ─────────────────────────

def test_mw_publish_non_telemetry_is_noop():
    mw = _mw()
    mw.publish('some.other.topic', {'data': 1})
    assert mw.events == []


def test_mw_publish_primitive_entered_records():
    mw = _mw()
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'grasp'})
    assert mw.primitives_entered == ['grasp']
    assert mw.events[0]['event'] == 'primitive.entered'


def test_mw_inject_at_safety_state():
    mw = _mw(inject_at={'align': {'safety_state': {'human_in_forbidden_zone': True}}})
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'align'})
    safety = mw.read('state.safety_state')
    assert safety['human_in_forbidden_zone'] is True


def test_mw_inject_at_perception_override():
    mw = _mw(inject_at={'scan': {'perception_override': {'confidence': 0.1}}})
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'scan'})
    part = mw.read('perception.part_alignment')
    assert part['confidence'] == 0.1


def test_mw_inject_at_force_override():
    mw = _mw(inject_at={'insert': {'force_override': {'normal_force_n': 50.0}}})
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'insert'})
    fb = mw.read('force_control.contact_feedback')
    assert fb['normal_force_n'] == 50.0


def test_mw_initial_safety_overrides_defaults():
    mw = _mw(initial_safety={'human_in_forbidden_zone': True, 'human_distance_m': 0.5})
    s = mw.read('state.safety_state')
    assert s['human_in_forbidden_zone'] is True
    assert s['human_distance_m'] == 0.5


# ── _run_test() edge cases ─────────────────────────────────────────────────────

def _make_run_fn(status='completed', reason=None, extra=None):
    def run_fn(job_ctx, middleware=None):
        result = {'status': status}
        if reason:
            result['reason'] = reason
        if extra:
            result.update(extra)
        return result
    return run_fn


def _run_fn_raises():
    def run_fn(job_ctx, middleware=None):
        raise RuntimeError('adapter exploded')
    return run_fn


def test_run_test_passes_on_matching_status():
    test_spec = {'id': 'test_ok', 'description': 'nominal', 'expect': {'status': 'completed'}}
    r = _run_test(_make_run_fn('completed'), test_spec, 'etd.test.skill')
    assert r.passed is True
    assert r.failure_message is None


def test_run_test_fails_on_status_mismatch():
    test_spec = {'id': 'test_fail', 'description': '', 'expect': {'status': 'completed'}}
    r = _run_test(_make_run_fn('aborted'), test_spec, 'etd.test.skill')
    assert r.passed is False
    assert 'status' in r.failure_message


def test_run_test_fails_on_reason_mismatch():
    test_spec = {
        'id': 'test_reason', 'description': '',
        'expect': {'status': 'aborted', 'reason': 'human_in_forbidden_zone'},
    }
    r = _run_test(_make_run_fn('aborted', reason='timeout'), test_spec, 'etd.test.skill')
    assert r.passed is False
    assert 'reason' in r.failure_message


def test_run_test_fails_on_missing_result_key():
    test_spec = {
        'id': 'test_keys', 'description': '',
        'expect': {'status': 'completed', 'result_keys': ['items_picked']},
    }
    r = _run_test(_make_run_fn('completed'), test_spec, 'etd.test.skill')
    assert r.passed is False
    assert 'items_picked' in r.failure_message


def test_run_test_passes_with_required_result_key_present():
    test_spec = {
        'id': 'test_keys_ok', 'description': '',
        'expect': {'status': 'completed', 'result_keys': ['items_picked']},
    }
    r = _run_test(_make_run_fn('completed', extra={'items_picked': 3}), test_spec, 'etd.test.skill')
    assert r.passed is True


def test_run_test_exception_returns_error_result():
    test_spec = {'id': 'test_exc', 'description': '', 'expect': {}}
    r = _run_test(_run_fn_raises(), test_spec, 'etd.test.skill')
    assert r.passed is False
    assert r.status == 'error'
    assert 'adapter exploded' in r.failure_message


def test_run_test_duration_ms_is_nonnegative():
    test_spec = {'id': 'test_dur', 'description': '', 'expect': {'status': 'completed'}}
    r = _run_test(_make_run_fn('completed'), test_spec, 'etd.test.skill')
    assert r.duration_ms >= 0.0


# ── run_suite() when yaml file missing ────────────────────────────────────────

def test_run_suite_no_yaml_returns_empty(tmp_path):
    pkg = tmp_path / 'etd.fake.skill'
    pkg.mkdir()
    suite = run_suite(str(pkg.name))
    assert suite.total == 0
    assert suite.passed == 0
    assert suite.failed == 0
    assert suite.success is True


# ── _print_suite() verbose and failure display ────────────────────────────────

def _make_suite(passed_ids, failed_id=None):
    results = [
        TestResult(test_id=tid, description='', passed=True, status='completed',
                   reason=None, failure_message=None, duration_ms=5.0)
        for tid in passed_ids
    ]
    if failed_id:
        results.append(
            TestResult(test_id=failed_id, description='', passed=False,
                       status='aborted', reason='timeout',
                       failure_message='status mismatch', duration_ms=10.0)
        )
    p = sum(1 for r in results if r.passed)
    return SuiteResult(
        skill_id='etd.test.skill', suite='test suite',
        total=len(results), passed=p, failed=len(results) - p,
        results=results,
    )


def test_print_suite_shows_skill_id(capsys):
    _print_suite(_make_suite(['t1', 't2']), verbose=False)
    out = capsys.readouterr().out
    assert 'etd.test.skill' in out


def test_print_suite_verbose_shows_status(capsys):
    _print_suite(_make_suite(['t1']), verbose=True)
    out = capsys.readouterr().out
    assert 'status=' in out


def test_print_suite_shows_fail_message(capsys):
    _print_suite(_make_suite(['t1'], failed_id='t_bad'), verbose=False)
    out = capsys.readouterr().out
    assert 'FAIL' in out
    assert 'status mismatch' in out


def test_print_suite_failed_suite_has_x_icon(capsys):
    _print_suite(_make_suite([], failed_id='t_bad'), verbose=False)
    out = capsys.readouterr().out
    assert '✗' in out


# ── acceptance_runner.main() CLI ──────────────────────────────────────────────

def test_acc_main_single_skill(capsys, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['acceptance_runner.py', '--skill', 'etd.pickplace.basic'])
    try:
        _acc_main()
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert 'etd.pickplace.basic' in out


def test_acc_main_json_output(capsys, monkeypatch):
    monkeypatch.setattr(sys, 'argv',
                        ['acceptance_runner.py', '--skill', 'etd.pickplace.basic', '--json'])
    try:
        _acc_main()
    except SystemExit:
        pass
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]['skill_id'] == 'etd.pickplace.basic'
    assert parsed[0]['failed'] == 0


def test_acc_main_verbose(capsys, monkeypatch):
    monkeypatch.setattr(sys, 'argv',
                        ['acceptance_runner.py', '--skill', 'etd.pickplace.basic', '--verbose'])
    try:
        _acc_main()
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert 'status=' in out


# ── _run_test() legacy inject format + chsProfile auto-injection ──────────────

def test_run_test_legacy_inject_without_at_primitive_sets_initial_safety():
    """inject dict without 'at_primitive' applies safety globally before any primitive."""
    run_fn = _load_run('etd.pickplace.basic')
    test_spec = {
        'id': 'test_legacy_inject',
        'description': 'legacy inject format',
        'inject': {'safety_state': {'human_in_forbidden_zone': True}},
        'expect': {'status': 'aborted', 'reason': 'human_in_forbidden_zone'},
    }
    r = _run_test(run_fn, test_spec, 'etd.pickplace.basic')
    assert r.passed is True


def test_run_test_job_context_without_chs_profile_gets_profile_injected(monkeypatch):
    """When input.job_context lacks chsProfile, the profile field is auto-inserted."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    test_spec = {
        'id': 'test_no_profile',
        'description': 'no chsProfile in job_context',
        'profile': 'small_box',
        'input': {'job_context': {'priority': 'normal'}},
        'expect': {'status': 'completed'},
    }
    r = _run_test(run_fn, test_spec, 'etd.pickplace.basic')
    assert r.passed is True


# ── pickplace adapter: fragility='high' and unknown-profile branches ──────────

def test_pickplace_fragility_high_uses_slow_speed(monkeypatch):
    """fragility='high' forces speed_factor=0.5 regardless of profile."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    result = run_fn({'chsProfile': 'small_box', 'fragility': 'high', 'priority': 'normal'})
    assert result['status'] == 'completed'
    assert result['speed_factor'] == 0.5


def test_pickplace_unknown_profile_falls_back_to_small_box_defaults(monkeypatch):
    """Unknown chsProfile falls back to small_box defaults (payloadKg=1.5)."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    result = run_fn({'chsProfile': 'nonexistent_profile', 'priority': 'normal'})
    assert result['status'] == 'completed'
    assert result['payload_kg'] == 1.5
