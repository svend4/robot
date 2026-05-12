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


# ── _run_test: inject without at_primitive AND without safety_state ───────────

def test_run_test_inject_without_at_primitive_and_no_safety_state(monkeypatch):
    """inject dict with no 'at_primitive' and no 'safety_state' → initial_safety=None, skill completes."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    # inject_spec has no 'at_primitive' → line 186 branch taken
    # inject_spec.get('safety_state') → None (key absent) → initial_safety=None
    test_spec = {
        'id': 'inject_no_safety_state',
        'description': 'inject without at_primitive and without safety_state gives initial_safety=None',
        'inject': {'custom_key': 'some_value'},
        'input': {'job_context': {'chsProfile': 'small_box'}},
        'expect': {'status': 'completed'},
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


# ── Extended middleware: per-topic overrides + safety-state countdown ──────────

class _AdapterMW(AcceptanceMiddleware):
    """AcceptanceMiddleware with per-topic overrides and optional safety countdown.

    after_n_safety_reads / then_safety: after N reads of state.safety_state,
    subsequent reads return then_safety instead of the AcceptanceMiddleware defaults.
    """

    def __init__(self, joint_state=None, intent=None, fatigue=None,
                 seam_tracker=None, part_alignment=None,
                 balance_state=None, scene_map=None, object_pose=None,
                 after_n_safety_reads=None, then_safety=None, **kw):
        super().__init__(**kw)
        self._joint_state_override = joint_state
        self._intent_override = intent
        self._fatigue_override = fatigue
        self._seam_tracker_override = seam_tracker
        self._part_alignment_override = part_alignment
        self._balance_state_override = balance_state
        self._scene_map_override = scene_map
        self._object_pose_override = object_pose
        self._safety_count = 0
        self._after_n = after_n_safety_reads
        self._then_safety = then_safety or {}

    def read(self, topic):
        if topic == 'state.safety_state':
            self._safety_count += 1
            if self._after_n is not None and self._safety_count > self._after_n:
                return dict(self._then_safety)
        if topic == 'state.exo_joint_state' and self._joint_state_override is not None:
            return dict(self._joint_state_override)
        if topic == 'perception.intent_detector' and self._intent_override is not None:
            return dict(self._intent_override)
        if topic == 'state.fatigue_monitor' and self._fatigue_override is not None:
            return dict(self._fatigue_override)
        if topic == 'perception.seam_tracker' and self._seam_tracker_override is not None:
            return dict(self._seam_tracker_override)
        if topic == 'perception.part_alignment' and self._part_alignment_override is not None:
            return dict(self._part_alignment_override)
        if topic == 'state.balance_state' and self._balance_state_override is not None:
            return dict(self._balance_state_override)
        if topic == 'perception.scene_map' and self._scene_map_override is not None:
            return dict(self._scene_map_override)
        if topic == 'perception.object_pose' and self._object_pose_override is not None:
            return dict(self._object_pose_override)
        return super().read(topic)


# ── Vest exoskeleton adapter: safety and calibration branches ─────────────────

def test_exo_operator_panic_release_aborts():
    """operator_panic_release flag in safety state aborts at first primitive."""
    run_fn = _load_run('etd.hyundai.vest_exoskeleton')
    mw = AcceptanceMiddleware(initial_safety={'operator_panic_release': True})
    result = run_fn({'profileId': 'overhead_assembly'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'operator_panic_release'


def test_exo_calibration_failed_aborts():
    """calibrate_fit aborts when joint sensor reports calibrated=False."""
    run_fn = _load_run('etd.hyundai.vest_exoskeleton')
    mw = _AdapterMW(joint_state={'calibrated': False, 'torque_within_limits': True})
    result = run_fn({'profileId': 'overhead_assembly'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'calibration_failed'


def test_exo_intent_confidence_below_threshold_aborts(monkeypatch):
    """detect_intent aborts when intent confidence is below the profile minimum."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.hyundai.vest_exoskeleton')
    mw = _AdapterMW(intent={'confidence': 0.5, 'mode': 'overhead', 'direction': 'up'})
    result = run_fn({'profileId': 'overhead_assembly'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'intent_confidence_below_threshold'
    assert result['confidence'] == 0.5


def test_exo_fatigue_threshold_adapts_gain(monkeypatch):
    """monitor_fatigue / adapt_gain lowers final_gain when fatigue exceeds threshold."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.hyundai.vest_exoskeleton')
    # overhead_assembly: fatigue_threshold_pct=70; inject 90 > 70
    mw = _AdapterMW(fatigue={'fatigue_pct': 90, 'session_sec': 0})
    result = run_fn({'profileId': 'overhead_assembly'}, middleware=mw)
    assert result['status'] == 'completed'
    assert result['fatigue_pct'] == 90
    assert result['final_gain'] < 1.0  # max(0.5, 1.0 - (90-70)/100) = 0.8


# ── Cobot safeassist adapter: wait_human_ready branches ──────────────────────

def test_cobot_human_ready_timeout_aborts(monkeypatch):
    """wait_human_ready aborts with human_ready_timeout when deadline is already past."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.cobot.safeassist')
    mw = AcceptanceMiddleware(initial_safety={'human_ready_signal': False})
    result = run_fn(
        {'chsProfile': 'safe_handover', 'humanReadyTimeoutSec': -1},
        middleware=mw,
    )
    assert result['status'] == 'aborted'
    assert result['reason'] == 'human_ready_timeout'


def test_cobot_forbidden_zone_during_wait_loop_aborts(monkeypatch):
    """human_in_forbidden_zone detected inside the wait_human_ready while-loop aborts."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.cobot.safeassist')
    # 3 outer reads safe (social_approach, offer_preposition, wait_human_ready),
    # then forbidden zone on the first iteration inside the while loop
    mw = _AdapterMW(
        after_n_safety_reads=3,
        then_safety={'human_in_forbidden_zone': True, 'human_ready_signal': False},
    )
    result = run_fn(
        {'chsProfile': 'safe_handover', 'humanReadyTimeoutSec': 5.0},
        middleware=mw,
    )
    assert result['status'] == 'aborted'
    assert result['reason'] == 'human_in_forbidden_zone'


# ── WIA welding adapter: seam-tracking, tack-weld, and arc-active branches ────

def test_wia_seam_track_confidence_low_aborts():
    """torch_align aborts when seam tracker confidence is below alignment minimum."""
    run_fn = _load_run('etd.hyundai.wia_welding')
    # standard_seam: alignment_confidence_min=0.90; inject confidence=0.5 via safety dict
    mw = AcceptanceMiddleware(initial_safety={'confidence': 0.5})
    result = run_fn({'chsProfile': 'standard_seam'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'seam_track_confidence_low'
    assert result['confidence'] == 0.5


def test_wia_tack_weld_skips_traverse_and_inspection(monkeypatch):
    """tack_weld profile (travel_speed=0, post_inspection=False) skips traversal loop and inspection."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.hyundai.wia_welding')
    mw = AcceptanceMiddleware()
    result = run_fn({'chsProfile': 'tack_weld'}, middleware=mw)
    assert result['status'] == 'completed'
    event_names = [e['event'] for e in mw.events]
    assert 'welding.seam_progress' not in event_names
    assert 'inspection.result' not in event_names


def test_wia_arc_active_abort_emits_arc_stopped_first(monkeypatch):
    """When human enters zone while arc is active, welding.arc_stopped precedes skill.aborted."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.hyundai.wia_welding')
    # 3 outer reads safe (approach_seam_start, torch_align, ignite_arc),
    # 4th read at weld_traverse outer check → forbidden (arc_active=True at this point)
    mw = _AdapterMW(
        after_n_safety_reads=3,
        then_safety={'human_in_forbidden_zone': True},
    )
    result = run_fn({'chsProfile': 'standard_seam'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['at_primitive'] == 'weld_traverse'
    event_names = [e['event'] for e in mw.events]
    assert 'welding.arc_stopped' in event_names
    assert event_names.index('welding.arc_stopped') < event_names.index('skill.aborted')


# ── MobED transport adapter: human abort inside navigation segment ─────────────

def test_mobed_abort_during_navigation_segment(monkeypatch):
    """human_in_forbidden_zone inside _navigate_segment loop returns abort from that function."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.hyundai.mobed_transport')
    # 1 outer read safe (navigate_to_pickup outer check), then forbidden inside loop
    mw = _AdapterMW(
        after_n_safety_reads=1,
        then_safety={'human_in_forbidden_zone': True},
    )
    result = run_fn({'chsProfile': 'standard_carry'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'human_in_forbidden_zone'
    assert result['at_primitive'] == 'navigate_to_pickup'


# ── Assembly precision adapter: vision alignment and seating branches ──────────

def test_assembly_alignment_confidence_below_threshold_aborts():
    """vision_align aborts when part_alignment confidence is below profile minimum."""
    run_fn = _load_run('etd.assembly.precision')
    # peg_in_hole: alignment_confidence_min=0.90; inject confidence=0.5
    mw = AcceptanceMiddleware(initial_safety={'confidence': 0.5})
    result = run_fn({'chsProfile': 'peg_in_hole'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'alignment_confidence_below_threshold'
    assert result['confidence'] == 0.5


def test_assembly_alignment_offset_too_large_aborts():
    """vision_align aborts when part offset exceeds precision_mm * 3."""
    run_fn = _load_run('etd.assembly.precision')
    # peg_in_hole: precision_mm=0.5, limit=1.5mm; inject offset=5.0mm
    mw = _AdapterMW(part_alignment={'confidence': 0.95, 'offset_mm': 5.0, 'aligned': False})
    result = run_fn({'chsProfile': 'peg_in_hole'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'alignment_offset_too_large'
    assert result['offset_mm'] == 5.0


def test_assembly_insufficient_seating_force_aborts():
    """seat_verify aborts when measured contact force is below 80% of seat_force_n."""
    run_fn = _load_run('etd.assembly.precision')
    # peg_in_hole: seat_force_n=15.0, threshold=12.0; inject normal_force_n=5.0
    mw = AcceptanceMiddleware(initial_safety={'normal_force_n': 5.0})
    result = run_fn({'chsProfile': 'peg_in_hole'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'insufficient_seating_force'


# ── Inspect vision adapter: classification confidence and defect branches ──────

def test_inspect_low_classification_confidence_aborts(monkeypatch):
    """classify_result aborts when classification confidence falls below threshold."""
    import random as _random
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    # defect_scan: threshold=0.92; uniform(a,b)->a => 0.93+(-0.04)=0.89 < 0.92
    monkeypatch.setattr(_random, 'uniform', lambda a, b: a)
    monkeypatch.setattr(_random, 'random', lambda: 0.5)
    run_fn = _load_run('etd.inspect.vision')
    result = run_fn({'chsProfile': 'defect_scan', 'partId': 'P-001'},
                    middleware=AcceptanceMiddleware())
    assert result['status'] == 'aborted'
    assert result['reason'] == 'low_classification_confidence'
    assert result['confidence'] < 0.92


def test_inspect_defect_found_sets_pass_qc_false(monkeypatch):
    """_classify_defects with a detected defect sets pass_qc=False in completed result."""
    import random as _random
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    # uniform->max => confidence=0.97 >= 0.92 (passes gate); random()->0.0<0.08 => defect injected
    monkeypatch.setattr(_random, 'uniform', lambda a, b: b)
    monkeypatch.setattr(_random, 'random', lambda: 0.0)
    run_fn = _load_run('etd.inspect.vision')
    result = run_fn({'chsProfile': 'defect_scan', 'partId': 'P-002'},
                    middleware=AcceptanceMiddleware())
    assert result['status'] == 'completed'
    assert result['pass_qc'] is False
    assert len(result['defects_found']) > 0


# ── Atlas humanoid adapter: balance, localization, grasp, handover branches ────

def test_atlas_balance_loss_detected_aborts(monkeypatch):
    """Balance check at every primitive aborts immediately when stable=False."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.atlas.humanoid_walkfetch')
    mw = _AdapterMW(balance_state={'stable': False, 'com_margin': 0.0, 'gait': 'stand'})
    result = run_fn({'chsProfile': 'sequencing_carry'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'balance_loss_detected'


def test_atlas_localization_failure_aborts(monkeypatch):
    """localize_target aborts when scene map reports map_ready=False."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.atlas.humanoid_walkfetch')
    mw = _AdapterMW(scene_map={'map_ready': False, 'obstacles': []})
    result = run_fn({'chsProfile': 'sequencing_carry'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'localization_failure'


def test_atlas_grasp_confidence_low_aborts(monkeypatch):
    """approach_object aborts when object pose confidence is below grasp_confidence_min."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.atlas.humanoid_walkfetch')
    # sequencing_carry: grasp_confidence_min=0.85; inject confidence=0.5
    mw = _AdapterMW(object_pose={
        'confidence': 0.5, 'x': 3.0, 'y': 1.5, 'z': 0.8,
        'object_class': 'automotive_part', 'mass_estimate_kg': 4.5,
    })
    result = run_fn({'chsProfile': 'sequencing_carry'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'grasp_confidence_low'
    assert result['confidence'] == 0.5


def test_atlas_handover_timeout_aborts(monkeypatch):
    """deposit_or_handover aborts with handover_timeout when human_ready deadline is past."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.atlas.humanoid_walkfetch')
    atlas_mod = sys.modules['etd_acc_etd_atlas_humanoid_walkfetch']
    # Set timeout to -1 so deadline is already past; loop body never executes
    monkeypatch.setitem(atlas_mod._PROFILE_DEFAULTS['human_handover'],
                        'humanReadyTimeoutSec', -1.0)
    mw = AcceptanceMiddleware(initial_safety={'human_ready_signal': False})
    result = run_fn({'chsProfile': 'human_handover'}, middleware=mw)
    assert result['status'] == 'aborted'
    assert result['reason'] == 'handover_timeout'


# ── _run_test: missing 'status' key in expect → exp_status None → check skipped

def test_run_test_no_status_in_expect_skips_status_check():
    # expect dict has no 'status' key → exp_status = None → if exp_status and ... → False
    # → failure_msg stays None → test passes regardless of actual status
    test_spec = {'id': 'no_status', 'description': 'no status check'}
    r = _run_test(_make_run_fn('completed'), test_spec, 'etd.test.skill')
    assert r.passed is True
    assert r.failure_message is None


# ── _run_test: 'status' matches but 'reason' missing → reason check skipped ──

def test_run_test_no_reason_in_expect_skips_reason_check():
    # expect has status (matches) but no 'reason' key → exp_reason = None → check skipped
    test_spec = {
        'id': 'no_reason',
        'description': 'status matches, reason check skipped',
        'expect': {'status': 'aborted'},  # no 'reason' key
    }
    # run_fn returns status='aborted' with an arbitrary reason
    r = _run_test(_make_run_fn('aborted', reason='some_unexpected_reason'), test_spec, 'etd.test.skill')
    assert r.passed is True
    assert r.failure_message is None


# ── Vest exoskeleton: adapt_gain below fatigue threshold → final_gain stays 1.0

def test_exo_adapt_gain_below_fatigue_threshold_stays_at_full_gain():
    """fatigue_pct=50 < threshold=70: adapt_gain branch not taken, final_gain=1.0."""
    run_fn = _load_run('etd.hyundai.vest_exoskeleton')
    # intent mode='overhead' so detect_intent passes; fatigue_pct=50 < 70
    mw = _AdapterMW(
        intent={'confidence': 0.95, 'mode': 'overhead', 'direction': 'up'},
        fatigue={'fatigue_pct': 50, 'session_sec': 300},
    )
    result = run_fn({'profileId': 'overhead_assembly'}, middleware=mw)
    assert result['status'] == 'completed'
    assert result['final_gain'] == 1.0
    event_names = [e['event'] for e in mw.events]
    assert 'assist.mode_switched' not in event_names


# ── Vest exoskeleton: engage_assist mode='reach' → no overhead/lumbar event ──

def test_exo_engage_assist_reach_mode_skips_overhead_and_lumbar_events():
    """mode='reach' falls through both if/elif in engage_assist, torque still applied."""
    run_fn = _load_run('etd.hyundai.vest_exoskeleton')
    mw = _AdapterMW(
        intent={'confidence': 0.95, 'mode': 'reach', 'direction': 'forward'},
        fatigue={'fatigue_pct': 10, 'session_sec': 0},
    )
    result = run_fn({'profileId': 'overhead_assembly'}, middleware=mw)
    assert result['status'] == 'completed'
    event_names = [e['event'] for e in mw.events]
    assert 'assist.overhead_mode_entered' not in event_names
    assert 'assist.lumbar_mode_entered' not in event_names
    assert 'assist.torque_applied' in event_names


# ── Cobot safeassist: human_in_safety_radius key absent → speed_factor=0.8 ───

def test_cobot_social_approach_missing_safety_radius_key_uses_fast_speed():
    """When safety state has no human_in_safety_radius key, speed_factor=0.8 (not 0.4)."""
    run_fn = _load_run('etd.cobot.safeassist')

    published_intents = []

    class _CaptureMW(_AdapterMW):
        def publish(self, topic, msg):
            if topic == 'command.skill_intent':
                published_intents.append(msg)
            super().publish(topic, msg)

    # Safety state lacks 'human_in_safety_radius' → .get() returns None → falsy
    mw = _CaptureMW(
        after_n_safety_reads=0,
        then_safety={'human_in_forbidden_zone': False, 'human_ready_signal': True},
    )
    result = run_fn({'chsProfile': 'handover_assist'}, middleware=mw)
    assert result['status'] == 'completed'
    social_intents = [i for i in published_intents if i.get('primitive') == 'social_approach']
    assert len(social_intents) == 1
    assert social_intents[0]['speed_factor'] == 0.8


# ── Assembly precision: vision_align confidence == threshold → not aborted ───

def test_assembly_vision_align_confidence_at_exact_threshold_passes():
    """confidence=0.90 with threshold=0.90: strict-less check means NOT aborted."""
    run_fn = _load_run('etd.assembly.precision')
    # part_alignment override: confidence exactly equals peg_in_hole threshold (0.90)
    mw = _AdapterMW(part_alignment={'confidence': 0.90, 'offset_mm': 0.0, 'aligned': True})
    result = run_fn({'chsProfile': 'peg_in_hole'}, middleware=mw)
    assert result['status'] == 'completed'
    event_names = [e['event'] for e in mw.events]
    assert 'skill.aborted' not in event_names


# ── inspect.vision: barcode_qa profile → _classify_barcode path ──────────────

def test_inspect_barcode_qa_uses_classify_barcode(monkeypatch):
    """barcode_qa profile sets scan_mode='barcode': _classify_barcode called, not _classify_defects."""
    import random as _random
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    # uniform->max => confidence = 0.94 + 0.03 = 0.97 ≥ 0.88 → pass_qc True
    monkeypatch.setattr(_random, 'uniform', lambda a, b: b)
    run_fn = _load_run('etd.inspect.vision')
    result = run_fn({'chsProfile': 'barcode_qa', 'partId': 'BARCODE-001'},
                    middleware=AcceptanceMiddleware())
    assert result['status'] == 'completed'
    assert result['pass_qc'] is True
    assert result['profile'] == 'barcode_qa'
    # barcode_qa produces no defects_found list (QCResult defaults to [])
    assert result['defects_found'] == []


# ── run_suite: legacy 'scenarios' key in YAML falls back correctly ─────────────

def test_run_suite_legacy_scenarios_key_falls_back(tmp_path, monkeypatch):
    """spec.get('tests', spec.get('scenarios', [])) handles legacy YAML with 'scenarios' key."""
    import sim.acceptance_runner as _acc_mod
    import yaml as _yaml

    # Build a minimal fake package
    pkg = tmp_path / 'examples' / 'etd.legacy.test'
    (pkg / 'tests').mkdir(parents=True)
    (pkg / 'policies').mkdir()

    # YAML uses legacy 'scenarios' key instead of 'tests'
    (pkg / 'tests' / 'acceptance_tests.yaml').write_text(
        _yaml.dump({
            'suite': 'legacy test suite',
            'skill_id': 'etd.legacy.test',
            'scenarios': [{
                'id': 'legacy_pass',
                'description': 'always passes',
                'input': {'job_context': {}},
                'expect': {'status': 'completed'},
            }],
        })
    )

    # skill.json required by _load_run
    import json as _json
    (pkg / 'skill.json').write_text(_json.dumps({
        'skillId': 'etd.legacy.test',
        'entrypoint': 'policies/chs_adapter.py:run',
    }))

    # Minimal adapter that always returns completed
    (pkg / 'policies' / 'chs_adapter.py').write_text(
        'def run(job_context, middleware=None):\n'
        '    return {"status": "completed"}\n'
    )

    monkeypatch.setattr(_acc_mod, 'ROOT', tmp_path)
    suite = run_suite('etd.legacy.test')
    assert suite.total == 1
    assert suite.passed == 1
    assert suite.failed == 0


# ── WIA welding: unknown chsProfile falls back to standard_seam defaults ──────

def test_wia_unknown_profile_falls_back_to_standard_seam(monkeypatch):
    """Invalid chsProfile falls back to standard_seam via _PROFILE_DEFAULTS.get(name, default)."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.hyundai.wia_welding')
    wia_mod = sys.modules['etd_acc_etd_hyundai_wia_welding']
    # Confidence above standard_seam threshold (0.90)
    mw = AcceptanceMiddleware(initial_safety={'confidence': 0.95})
    result = run_fn({'chsProfile': 'nonexistent_profile'}, middleware=mw)
    assert result['status'] == 'completed'
    # standard_seam defaults: amperage=160, seam_length=150
    assert result['amperage_a'] == wia_mod._PROFILE_DEFAULTS['standard_seam']['amperageA']
    assert result['seam_length_mm'] == wia_mod._PROFILE_DEFAULTS['standard_seam']['seamLengthMm']


# ── _run_test: inject with at_primitive but no nested keys → empty patch dict ─

def test_run_test_inject_at_primitive_no_nested_keys_empty_patch(monkeypatch):
    """inject_spec has at_primitive key but no nested safety/perception/force keys.

    inject_at[at_prim] = {} (empty dict comprehension) — primitive fires with
    no state changes, skill completes normally.
    """
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    test_spec = {
        'id': 'empty_patch',
        'description': 'inject with no nested keys produces empty patch',
        'inject': {'at_primitive': 'approach'},  # no safety_state, no perception_override
        'input': {'job_context': {'chsProfile': 'small_box'}},
        'expect': {'status': 'completed'},
    }
    r = _run_test(run_fn, test_spec, 'etd.pickplace.basic')
    assert r.passed is True
    assert r.status == 'completed'


# ── _run_test: legacy 'expected' key fallback (test.get('expected', {})) ──────

def test_run_test_expected_key_used_as_fallback_for_expect(monkeypatch):
    """expect = test.get('expect', test.get('expected', {})) — 'expected' key works."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    # Use legacy 'expected' key instead of 'expect'
    test_spec = {
        'id': 'legacy_expected',
        'description': 'legacy expected key works as fallback',
        'input': {'job_context': {'chsProfile': 'small_box'}},
        'expected': {'status': 'completed'},  # legacy key — no 'expect' key present
    }
    r = _run_test(run_fn, test_spec, 'etd.pickplace.basic')
    assert r.passed is True


# ── _run_test: test_id fallback to 'name' then 'unknown' ─────────────────────

def test_run_test_uses_name_key_when_id_absent(monkeypatch):
    """test.get('id', test.get('name', 'unknown')) — 'name' used when 'id' absent."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    test_spec = {
        'name': 'my_named_test',   # no 'id' key → falls back to 'name'
        'description': 'name fallback test',
        'input': {'job_context': {'chsProfile': 'small_box'}},
        'expect': {'status': 'completed'},
    }
    r = _run_test(run_fn, test_spec, 'etd.pickplace.basic')
    assert r.test_id == 'my_named_test'
    assert r.passed is True


def test_run_test_uses_unknown_when_no_id_or_name(monkeypatch):
    """test.get('id', test.get('name', 'unknown')) — 'unknown' when neither key present."""
    import time as _time
    monkeypatch.setattr(_time, 'sleep', lambda s: None)
    run_fn = _load_run('etd.pickplace.basic')
    test_spec = {
        # neither 'id' nor 'name' key present
        'description': 'anonymous test',
        'input': {'job_context': {'chsProfile': 'small_box'}},
        'expect': {'status': 'completed'},
    }
    r = _run_test(run_fn, test_spec, 'etd.pickplace.basic')
    assert r.test_id == 'unknown'
    assert r.passed is True


# ── _load_run: default entrypoint when 'entrypoint' key absent from skill.json ─

def test_load_run_default_entrypoint_when_absent(tmp_path, monkeypatch):
    """skill.json without 'entrypoint' key → default 'policies/chs_adapter.py:run' is used."""
    import shutil, json as _json
    import sim.acceptance_runner as _ar

    examples = tmp_path / 'examples' / 'etd.test.noentrypoint'
    shutil.copytree(ROOT / 'examples' / 'etd.pickplace.basic', examples)

    skill = _json.loads((examples / 'skill.json').read_text())
    skill.pop('entrypoint', None)   # remove key → default applied in _load_run
    (examples / 'skill.json').write_text(_json.dumps(skill))

    monkeypatch.setattr(_ar, 'ROOT', tmp_path)
    run_fn = _ar._load_run('etd.test.noentrypoint')
    assert callable(run_fn)


# ── acceptance_runner.main(): no --skill arg → directory scan else-branch ─────

def test_acc_main_no_skill_arg_iterates_all_packages(monkeypatch):
    """main() without --skill triggers the else branch: directory scan of examples/."""
    import sim.acceptance_runner as _acc_mod

    ran_skills = []

    def _fake_run_suite(skill_id):
        ran_skills.append(skill_id)
        return SuiteResult(skill_id=skill_id, suite='fake', total=1, passed=1, failed=0,
                           results=[])

    monkeypatch.setattr(_acc_mod, 'run_suite', _fake_run_suite)
    monkeypatch.setattr(sys, 'argv', ['acceptance_runner.py', '--json'])

    try:
        _acc_main()
    except SystemExit:
        pass

    assert len(ran_skills) == 8
    assert 'etd.pickplace.basic' in ran_skills
    assert 'etd.hyundai.vest_exoskeleton' in ran_skills
