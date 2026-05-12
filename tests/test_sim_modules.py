"""Tests for sim/ modules: event_replay, mock_robot_state_generator,
fake_middleware_endpoint, scenario_runner, and failure_scenarios."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── sim.event_replay ──────────────────────────────────────────────────────────

from sim.event_replay import replay, replay_execution, nominal_lifecycle, aborted_lifecycle


def test_replay_string_events_all_pass_at_debug():
    msgs = replay(['skill.started', 'skill.completed'], 'etd.pickplace.basic',
                  min_severity='debug')
    assert len(msgs) == 2


def test_replay_primitive_entered_filtered_at_info():
    msgs = replay(['skill.started', 'primitive.entered', 'skill.completed'],
                  'etd.pickplace.basic', min_severity='info')
    assert len(msgs) == 2
    assert all(m['event'] != 'primitive.entered' for m in msgs)


def test_replay_preserves_skill_id():
    msgs = replay(['skill.started'], 'etd.atlas.humanoid_walkfetch')
    assert msgs[0]['skill_id'] == 'etd.atlas.humanoid_walkfetch'


def test_replay_robot_and_site_forwarded():
    msgs = replay(['skill.started'], 'etd.x', robot_id='bot-3', site_id='weld-cell-a')
    assert msgs[0]['robot_id'] == 'bot-3'
    assert msgs[0]['site_id'] == 'weld-cell-a'


def test_replay_dict_events_use_own_skill_id():
    msgs = replay([{'event': 'skill.started', 'skill_id': 'etd.custom.x'}],
                  skill_id='etd.default')
    assert msgs[0]['skill_id'] == 'etd.custom.x'


def test_replay_execution_returns_envelopes():
    log = [
        {'event': 'skill.started',   'skill_id': 'etd.x'},
        {'event': 'skill.completed', 'skill_id': 'etd.x', 'data': {'result': 'ok'}},
    ]
    msgs = replay_execution(log)
    assert len(msgs) == 2
    assert msgs[1]['data']['result'] == 'ok'


def test_nominal_lifecycle_structure():
    prims = ['approach', 'grasp', 'place']
    log = nominal_lifecycle('etd.x', prims)
    events = [e['event'] for e in log]
    assert events[0] == 'skill.started'
    assert events[-1] == 'skill.completed'
    assert events.count('primitive.entered') == 3
    assert events.count('primitive.exited') == 3


def test_aborted_lifecycle_ends_with_abort():
    log = aborted_lifecycle('etd.x', ['approach'], reason='human_in_forbidden_zone')
    assert log[-1]['event'] == 'skill.aborted'
    assert log[-1]['data']['reason'] == 'human_in_forbidden_zone'


def test_aborted_lifecycle_no_completed_event():
    log = aborted_lifecycle('etd.x', ['approach'])
    assert not any(e['event'] == 'skill.completed' for e in log)


# ── sim.mock_robot_state_generator ───────────────────────────────────────────

from sim.mock_robot_state_generator import RobotStateGenerator, mock_state


def test_generator_at_returns_state_dict():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    state = gen.at('approach')
    assert 'safety_state' in state
    assert 'arm_state' in state
    assert 'body_pose' in state
    assert state['primitive'] == 'approach'


def test_generator_at_unknown_primitive_returns_idle():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    state = gen.at('nonexistent_step')
    assert 'safety_state' in state


def test_generator_safety_state_defaults_safe():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    s = gen.at('grasp')['safety_state']
    assert s['human_in_forbidden_zone'] is False
    assert s['emergency_stop'] is False


def test_generator_primitives_nonempty():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    prims = gen.primitives()
    assert len(prims) > 0
    assert 'approach' in prims


def test_generator_walk_yields_all_primitives():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    states = list(gen.walk())
    assert len(states) == len(gen.primitives())
    assert states[0]['primitive'] == gen.primitives()[0]


def test_generator_step_advances():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    s0 = gen.step()
    s1 = gen.step()
    assert s0 is not None
    assert s1 is not None
    assert s0['primitive'] != s1['primitive']


def test_generator_step_returns_none_when_exhausted():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    for _ in gen.primitives():
        gen.step()
    assert gen.step() is None


def test_generator_reset_restarts():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    first = gen.step()
    gen.reset()
    again = gen.step()
    assert first['primitive'] == again['primitive']


def test_generator_weld_family():
    gen = RobotStateGenerator(skill_id='etd.hyundai.wia_welding')
    state = gen.at('arc_ignite')
    assert state['skill_specific'].get('arc_on') is True


def test_generator_transport_family():
    gen = RobotStateGenerator(skill_id='etd.hyundai.mobed_transport')
    state = gen.at('lift_payload')
    assert state['skill_specific'].get('loaded') is True


def test_mock_state_legacy_helper():
    s = mock_state()
    assert 'safety_state' in s
    assert s['safety_state']['human_in_forbidden_zone'] is False


def test_mock_state_human_too_close():
    s = mock_state(human_too_close=True)
    assert s['safety_state']['human_in_forbidden_zone'] is True


# ── sim.fake_middleware_endpoint ─────────────────────────────────────────────

from sim.fake_middleware_endpoint import FakeMiddleware, send_request


def test_middleware_accepts_bounded_request():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'request_type': 'skill_intent', 'payload': {}})
    assert r['accepted'] is True
    assert r['execution_id'] is not None


def test_middleware_rejects_unbounded():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': False})
    assert r['accepted'] is False
    assert r['reason'] == 'unbounded_request'


def test_middleware_rejects_forbidden_command():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'payload': {'servo_torque': 1.0}})
    assert r['accepted'] is False
    assert 'servo_torque' in r['reason']


def test_middleware_rejects_unknown_station():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'station_id': 'mars_station_1', 'payload': {}})
    assert r['accepted'] is False
    assert r['reason'] == 'unknown_station'


def test_middleware_known_station_accepted():
    mw = FakeMiddleware(station_id='weld_station_a')
    r = mw.send_request({'bounded': True, 'payload': {}})
    assert r['accepted'] is True


def test_middleware_status_running_after_accept():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'payload': {}})
    status = mw.get_status(r['execution_id'])
    assert status['status'] == 'running'


def test_middleware_complete_and_get_result():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'payload': {}})
    mw.complete(r['execution_id'], result='success', data={'items': 1})
    result = mw.get_result(r['execution_id'])
    assert result is not None
    assert result['status'] == 'success'
    assert result['result_data']['items'] == 1


def test_middleware_get_result_none_while_running():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'payload': {}})
    assert mw.get_result(r['execution_id']) is None


def test_middleware_cancel():
    mw = FakeMiddleware()
    r = mw.send_request({'bounded': True, 'payload': {}})
    assert mw.cancel(r['execution_id']) is True
    assert mw.get_status(r['execution_id'])['status'] == 'cancelled'


def test_middleware_cancel_nonexistent():
    mw = FakeMiddleware()
    assert mw.cancel('no-such-id') is False


def test_middleware_active_count():
    mw = FakeMiddleware()
    assert mw.active_count() == 0
    r1 = mw.send_request({'bounded': True, 'payload': {}})
    r2 = mw.send_request({'bounded': True, 'payload': {}})
    assert mw.active_count() == 2
    mw.complete(r1['execution_id'])
    assert mw.active_count() == 1


def test_middleware_unique_execution_ids():
    mw = FakeMiddleware()
    ids = {mw.send_request({'bounded': True, 'payload': {}})['execution_id']
           for _ in range(10)}
    assert len(ids) == 10


def test_legacy_send_request():
    r = send_request({'bounded': True, 'request_type': 'skill_intent', 'payload': {}})
    assert r['accepted'] is True


# ── sim.scenario_runner ───────────────────────────────────────────────────────

from sim.scenario_runner import run_all_scenarios


def test_scenario_runner_all_valid():
    results = run_all_scenarios()
    assert len(results) == 8
    for r in results:
        assert r['valid'] is True, f'{r["package"]} expected valid, got {r}'


def test_scenario_runner_all_level_a():
    results = run_all_scenarios()
    for r in results:
        assert r['level'] == 'A', f'{r["package"]} expected level A, got {r["level"]}'


def test_scenario_runner_uses_correct_context():
    results = run_all_scenarios()
    ctx_map = {r['package']: r['ctx'] for r in results}
    assert ctx_map['etd.atlas.humanoid_walkfetch'] == 'runtime_context_atlas.json'
    assert ctx_map['etd.hyundai.wia_welding']      == 'runtime_context_wia.json'
    assert ctx_map['etd.hyundai.mobed_transport']  == 'runtime_context_mobed.json'
    assert ctx_map['etd.pickplace.basic']              == 'runtime_context.json'
    assert ctx_map['etd.hyundai.vest_exoskeleton']     == 'runtime_context_exo.json'


# ── sim.failure_scenarios ────────────────────────────────────────────────────

from sim.failure_scenarios import (
    scenario_missing_service_level_d,
    scenario_human_in_forbidden_zone,
    scenario_payload_out_of_range,
    scenario_station_family_mismatch,
    run_all,
)


def test_failure_missing_service_level_d():
    r = scenario_missing_service_level_d()
    assert r['passed'] is True
    assert r['level'] == 'D'
    assert len(r['missing_errors']) > 0


def test_failure_human_in_forbidden_zone():
    r = scenario_human_in_forbidden_zone()
    assert r['passed'] is True
    assert r['status'] == 'aborted'
    assert r['reason'] == 'human_in_forbidden_zone'


def test_failure_payload_out_of_range():
    r = scenario_payload_out_of_range()
    assert r['passed'] is True
    assert r['ok_at_1_5kg'] is True
    assert r['blocked_at_5kg'] is True


def test_failure_station_family_mismatch():
    r = scenario_station_family_mismatch()
    assert r['passed'] is True
    assert r['compatible'] is False
    assert 'transport' in r['reason']


def test_failure_run_all_four_pass():
    results = run_all()
    assert len(results) == 4
    for r in results:
        assert r['passed'] is True, f'{r["scenario"]} failed: {r.get("detail")}'


# ── RobotStateGenerator additional family coverage ────────────────────────────

def test_generator_humanoid_family():
    gen = RobotStateGenerator(skill_id='etd.atlas.humanoid_walkfetch')
    state = gen.at('nav_to_pick')
    assert state['skill_specific'].get('walking') is True
    assert state['primitive'] == 'nav_to_pick'


def test_generator_humanoid_reach_and_grasp():
    gen = RobotStateGenerator(skill_id='etd.atlas.humanoid_walkfetch')
    state = gen.at('reach_and_grasp')
    assert state['skill_specific'].get('holding') is True
    assert state['skill_specific'].get('at_pick') is True


def test_generator_noise_mode_returns_valid_structure():
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic', noise=True)
    state = gen.at('approach')
    assert 'safety_state' in state
    assert 'arm_state' in state
    assert 'body_pose' in state
    assert state['primitive'] == 'approach'


# ── scenario_runner.print_results ─────────────────────────────────────────────

import io
import contextlib
from sim.scenario_runner import print_results


def test_print_results_no_compat_errors(capsys):
    results = [
        {'package': 'etd.pickplace.basic', 'valid': True, 'level': 'A',
         'ctx': 'runtime_context.json', 'compat_errors': []},
    ]
    print_results(results)
    out = capsys.readouterr().out
    assert 'etd.pickplace.basic' in out
    assert 'PASS' in out
    assert '1/1' in out


def test_print_results_with_compat_errors(capsys):
    results = [
        {'package': 'etd.test.pkg', 'valid': False, 'level': 'D',
         'ctx': 'runtime_context.json', 'compat_errors': ['missing service X']},
    ]
    print_results(results)
    out = capsys.readouterr().out
    assert 'FAIL' in out
    assert 'missing service X' in out
    assert '0/1' in out


def test_print_results_mixed_pass_fail(capsys):
    results = [
        {'package': 'etd.ok.pkg',   'valid': True,  'level': 'A',
         'ctx': 'runtime_context.json', 'compat_errors': []},
        {'package': 'etd.bad.pkg',  'valid': False, 'level': 'D',
         'ctx': 'runtime_context.json', 'compat_errors': []},
    ]
    print_results(results)
    out = capsys.readouterr().out
    assert '1/2' in out


# ── sim.acceptance_runner — AcceptanceMiddleware and SuiteResult ──────────────

import sim.acceptance_runner as _acc_mod
from sim.acceptance_runner import AcceptanceMiddleware, SuiteResult, _run_test, run_suite, _print_suite
_AccTestResult = _acc_mod.TestResult   # alias avoids pytest collecting it as a test class


def test_acceptance_middleware_publish_records_telemetry():
    mw = AcceptanceMiddleware()
    mw.publish('telemetry.events', {'event': 'skill.started'})
    assert len(mw.events) == 1
    assert mw.events[0]['event'] == 'skill.started'


def test_acceptance_middleware_publish_non_telemetry_ignored():
    mw = AcceptanceMiddleware()
    mw.publish('command.skill_intent', {'primitive': 'approach'})
    assert len(mw.events) == 0


def test_acceptance_middleware_publish_tracks_primitives_entered():
    mw = AcceptanceMiddleware()
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'grasp'})
    assert 'grasp' in mw.primitives_entered


def test_acceptance_middleware_inject_updates_safety_at_primitive():
    inject_at = {'grasp': {'safety_state': {'human_in_forbidden_zone': True}}}
    mw = AcceptanceMiddleware(inject_at=inject_at)
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'grasp'})
    state = mw.read('state.safety_state')
    assert state['human_in_forbidden_zone'] is True


def test_acceptance_middleware_initial_safety_override():
    mw = AcceptanceMiddleware(initial_safety={'human_in_forbidden_zone': True})
    state = mw.read('state.safety_state')
    assert state['human_in_forbidden_zone'] is True


def test_suite_result_success_true():
    suite = SuiteResult(skill_id='etd.x', suite='test', total=3, passed=3, failed=0)
    assert suite.success is True


def test_suite_result_success_false():
    suite = SuiteResult(skill_id='etd.x', suite='test', total=3, passed=2, failed=1)
    assert suite.success is False


def test_run_test_exception_path():
    def _failing_run(job_ctx, middleware):
        raise RuntimeError('adapter crashed')

    test_spec = {'id': 'crash_test', 'description': 'triggers exception',
                 'profile': 'small_box', 'expect': {'status': 'completed'}}
    result = _run_test(_failing_run, test_spec, 'etd.pickplace.basic')
    assert result.passed is False
    assert result.status == 'error'
    assert 'Exception' in result.failure_message


# ── validate_examples — _load_contexts and _pick_context ─────────────────────

import sys as _sys
_VEXAMP_DIR = ROOT
if str(_VEXAMP_DIR) not in _sys.path:
    _sys.path.insert(0, str(_VEXAMP_DIR))

from validate_examples import _load_contexts, _pick_context


def test_load_contexts_returns_all_keys():
    contexts = _load_contexts(ROOT)
    for key in ('base', 'atlas', 'wia', 'mobed', 'exo'):
        assert key in contexts


def test_pick_context_atlas():
    contexts = _load_contexts(ROOT)
    assert _pick_context('etd.atlas.humanoid_walkfetch', contexts) is contexts['atlas']


def test_pick_context_wia():
    contexts = _load_contexts(ROOT)
    assert _pick_context('etd.hyundai.wia_welding', contexts) is contexts['wia']


def test_pick_context_mobed():
    contexts = _load_contexts(ROOT)
    assert _pick_context('etd.hyundai.mobed_transport', contexts) is contexts['mobed']


def test_pick_context_exo():
    contexts = _load_contexts(ROOT)
    assert _pick_context('etd.hyundai.vest_exoskeleton', contexts) is contexts['exo']


def test_pick_context_base_fallback():
    contexts = _load_contexts(ROOT)
    assert _pick_context('etd.pickplace.basic', contexts) is contexts['base']


# ── _run_test failure branches ────────────────────────────────────────────────

def _make_run_fn(status, reason=None, extra_keys=()):
    def _run(job_ctx, middleware):
        result = {'status': status}
        if reason is not None:
            result['reason'] = reason
        for k in extra_keys:
            result[k] = True
        return result
    return _run


def test_run_test_status_mismatch():
    test_spec = {'id': 't', 'profile': 'small_box',
                 'expect': {'status': 'aborted'}}
    result = _run_test(_make_run_fn('completed'), test_spec, 'etd.x')
    assert result.passed is False
    assert 'status' in result.failure_message


def test_run_test_reason_mismatch():
    test_spec = {'id': 't', 'profile': 'small_box',
                 'expect': {'status': 'aborted', 'reason': 'payload_overload'}}
    result = _run_test(_make_run_fn('aborted', reason='human_in_forbidden_zone'),
                       test_spec, 'etd.x')
    assert result.passed is False
    assert 'reason' in result.failure_message


def test_run_test_result_key_missing():
    test_spec = {'id': 't', 'profile': 'small_box',
                 'expect': {'status': 'completed', 'result_keys': ['payload_kg']}}
    result = _run_test(_make_run_fn('completed'), test_spec, 'etd.x')
    assert result.passed is False
    assert 'payload_kg' in result.failure_message


def test_run_test_result_key_present():
    test_spec = {'id': 't', 'profile': 'small_box',
                 'expect': {'status': 'completed', 'result_keys': ['weight']}}
    result = _run_test(_make_run_fn('completed', extra_keys=('weight',)),
                       test_spec, 'etd.x')
    assert result.passed is True


# ── run_suite no tests file ───────────────────────────────────────────────────

def test_run_suite_no_tests_file():
    suite = run_suite('etd.nonexistent.skill')
    assert suite.total == 0
    assert suite.passed == 0
    assert suite.suite == '(no tests)'
    assert suite.success is True


# ── _print_suite output ───────────────────────────────────────────────────────

def _make_suite(passed_count, failed_count, with_reason=False):
    results = []
    for i in range(passed_count):
        results.append(_AccTestResult(
            test_id=f'pass_{i}', description='', passed=True,
            status='completed', reason='done' if with_reason else None,
            failure_message=None,
        ))
    for i in range(failed_count):
        results.append(_AccTestResult(
            test_id=f'fail_{i}', description='', passed=False,
            status='aborted', reason=None, failure_message='expected completed got aborted',
        ))
    return SuiteResult(
        skill_id='etd.x', suite='test_suite',
        total=passed_count + failed_count,
        passed=passed_count, failed=failed_count,
        results=results,
    )


def test_print_suite_all_passing(capsys):
    _print_suite(_make_suite(2, 0), verbose=False)
    out = capsys.readouterr().out
    assert '✓' in out
    assert '2/2' in out
    assert 'FAIL' not in out


def test_print_suite_with_failure(capsys):
    _print_suite(_make_suite(1, 1), verbose=False)
    out = capsys.readouterr().out
    assert '✗' in out
    assert 'FAIL' in out
    assert 'expected completed got aborted' in out


def test_print_suite_verbose_shows_status(capsys):
    _print_suite(_make_suite(1, 0, with_reason=True), verbose=True)
    out = capsys.readouterr().out
    assert 'status=' in out
    assert 'reason=' in out


# ── sim.visualizer ────────────────────────────────────────────────────────────

from sim.visualizer import (
    PrimitiveTrace, SkillTrace, TracingMiddleware, _bar, ascii_timeline, run_traced,
)


def test_primitive_trace_duration():
    p = PrimitiveTrace(name='grasp', start=1.0, end=1.5)
    assert abs(p.duration - 0.5) < 1e-9


def test_primitive_trace_duration_clamps_to_zero():
    p = PrimitiveTrace(name='grasp', start=2.0, end=1.0)
    assert p.duration == 0.0


def test_skill_trace_total_duration():
    t = SkillTrace(skill_id='etd.x', profile='p', start=0.0, end=0.25)
    assert abs(t.total_duration - 0.25) < 1e-9


def test_skill_trace_total_duration_clamps_to_zero():
    t = SkillTrace(skill_id='etd.x', profile='p', start=5.0, end=4.0)
    assert t.total_duration == 0.0


def test_bar_full():
    assert _bar(1.0, width=10) == '██████████'


def test_bar_empty():
    assert _bar(0.0, width=10) == '░░░░░░░░░░'


def test_bar_half():
    b = _bar(0.5, width=10)
    assert b == '█████░░░░░'


def test_bar_overflow_clamps():
    b = _bar(2.0, width=5)
    assert b == '█████'


def test_bar_underflow_clamps():
    b = _bar(-1.0, width=5)
    assert b == '░░░░░'


def _make_trace(skill_id='etd.x', profile='p', status='completed'):
    import time
    t0 = time.time()
    trace = SkillTrace(skill_id=skill_id, profile=profile, start=t0, end=t0 + 0.1,
                       status=status)
    trace.primitives.append(PrimitiveTrace(name='init', start=t0, end=t0 + 0.05, status='ok'))
    trace.events = [{'event': 'skill.started'}, {'event': 'skill.completed'}]
    trace.result = {'pass_qc': True, 'payload_kg': 3.0}
    return trace


def test_ascii_timeline_contains_skill_id():
    out = ascii_timeline([_make_trace()])
    assert 'etd.x' in out


def test_ascii_timeline_contains_primitive_name():
    out = ascii_timeline([_make_trace()])
    assert 'init' in out


def test_ascii_timeline_shows_checkmark_for_completed():
    out = ascii_timeline([_make_trace(status='completed')])
    assert '✓' in out


def test_ascii_timeline_shows_cross_for_aborted():
    out = ascii_timeline([_make_trace(status='aborted')])
    assert '✗' in out


def test_ascii_timeline_shows_result_summary_keys():
    out = ascii_timeline([_make_trace()])
    assert 'pass_qc' in out
    assert 'payload_kg' in out


def test_ascii_timeline_multiple_traces():
    traces = [_make_trace('etd.a'), _make_trace('etd.b')]
    out = ascii_timeline(traces)
    assert 'etd.a' in out
    assert 'etd.b' in out


# ── TracingMiddleware.publish ─────────────────────────────────────────────────

def _make_mw():
    import time
    trace = SkillTrace(skill_id='etd.x', profile='p', start=time.time())
    return TracingMiddleware(trace), trace


def test_tracing_middleware_publish_non_telemetry_ignored():
    mw, trace = _make_mw()
    mw.publish('some.other.topic', {'value': 1})
    assert trace.events == []
    assert trace.primitives == []


def test_tracing_middleware_publish_records_event():
    mw, trace = _make_mw()
    mw.publish('telemetry.events', {'event': 'skill.started'})
    assert len(trace.events) == 1
    assert trace.events[0]['event'] == 'skill.started'


def test_tracing_middleware_primitive_entered_creates_primitive():
    mw, trace = _make_mw()
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'grasp'})
    assert len(trace.primitives) == 1
    assert trace.primitives[0].name == 'grasp'


def test_tracing_middleware_primitive_exited_sets_end():
    mw, trace = _make_mw()
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'grasp'})
    mw.publish('telemetry.events', {'event': 'primitive.exited'})
    assert trace.primitives[0].end > 0
    assert trace.primitives[0].status == 'ok'
    assert mw._current_primitive is None


def test_tracing_middleware_skill_aborted_closes_primitive():
    mw, trace = _make_mw()
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'move'})
    mw.publish('telemetry.events', {'event': 'skill.aborted'})
    assert trace.primitives[0].status == 'aborted'
    assert trace.primitives[0].end > 0


def test_tracing_middleware_skill_failed_closes_primitive():
    mw, trace = _make_mw()
    mw.publish('telemetry.events', {'event': 'primitive.entered', 'primitive': 'move'})
    mw.publish('telemetry.events', {'event': 'skill.failed'})
    assert trace.primitives[0].status == 'failed'


# ── TracingMiddleware.read ────────────────────────────────────────────────────

def test_tracing_middleware_read_safety_state():
    mw, _ = _make_mw()
    s = mw.read('state.safety_state')
    assert 'human_in_forbidden_zone' in s
    assert s['human_in_forbidden_zone'] is False


def test_tracing_middleware_read_contact_feedback():
    mw, _ = _make_mw()
    r = mw.read('force_control.contact_feedback')
    assert 'normal_force_n' in r


def test_tracing_middleware_read_part_alignment():
    mw, _ = _make_mw()
    r = mw.read('perception.part_alignment')
    assert r['aligned'] is True


def test_tracing_middleware_read_camera_frame_increments():
    mw, _ = _make_mw()
    f1 = mw.read('perception.camera_frame')
    f2 = mw.read('perception.camera_frame')
    assert f2['frame_id'] == f1['frame_id'] + 1


def test_tracing_middleware_read_scene_map():
    mw, _ = _make_mw()
    r = mw.read('perception.scene_map')
    assert r['map_ready'] is True


def test_tracing_middleware_read_balance_state():
    mw, _ = _make_mw()
    r = mw.read('state.balance_state')
    assert r['stable'] is True


def test_tracing_middleware_read_object_pose():
    mw, _ = _make_mw()
    r = mw.read('perception.object_pose')
    assert 'confidence' in r
    assert r['object_class'] == 'automotive_part'


def test_tracing_middleware_read_seam_tracker():
    mw, _ = _make_mw()
    r = mw.read('perception.seam_tracker')
    assert r['seam_found'] is True


def test_tracing_middleware_read_weld_inspection():
    mw, _ = _make_mw()
    r = mw.read('vision.weld_inspection')
    assert r['pass'] is True


def test_tracing_middleware_read_obstacle_detector():
    mw, _ = _make_mw()
    r = mw.read('perception.obstacle_detector')
    assert r['clear'] is True


def test_tracing_middleware_read_path_planner():
    mw, _ = _make_mw()
    r = mw.read('navigation.path_planner')
    assert r['path_ready'] is True


def test_tracing_middleware_read_lift_control():
    mw, _ = _make_mw()
    r = mw.read('manipulation.lift_control')
    assert r['lift_ready'] is True


def test_tracing_middleware_read_exo_joint_state():
    mw, _ = _make_mw()
    r = mw.read('state.exo_joint_state')
    assert r['calibrated'] is True


def test_tracing_middleware_read_intent_detector():
    mw, _ = _make_mw()
    r = mw.read('perception.intent_detector')
    assert 'confidence' in r
    assert r['mode'] == 'overhead'


def test_tracing_middleware_read_fatigue_monitor():
    mw, _ = _make_mw()
    r = mw.read('state.fatigue_monitor')
    assert 'fatigue_pct' in r


def test_tracing_middleware_read_imu_pose():
    mw, _ = _make_mw()
    r = mw.read('perception.imu_pose')
    assert r['valid'] is True


def test_tracing_middleware_read_unknown_topic_returns_none():
    mw, _ = _make_mw()
    assert mw.read('nonexistent.topic') is None


# ── run_traced — full execution round-trip ────────────────────────────────────

def test_run_traced_pickplace():
    trace = run_traced('etd.pickplace.basic', 'fragile_item')
    assert trace.skill_id == 'etd.pickplace.basic'
    assert trace.status == 'completed'
    assert len(trace.primitives) > 0
    assert trace.total_duration > 0


def test_run_traced_wia_welding():
    trace = run_traced('etd.hyundai.wia_welding', 'standard_seam')
    assert trace.status == 'completed'
    assert trace.total_duration > 0


def test_run_traced_sets_result():
    trace = run_traced('etd.pickplace.basic', 'fragile_item')
    assert isinstance(trace.result, dict)
    assert 'status' in trace.result


# ── etd_demo_runner ───────────────────────────────────────────────────────────

from etd_demo_runner import _pick_context as _demo_pick_context, _level_ok, run_all as demo_run_all, _print_table


def test_demo_pick_context_atlas():
    p = _demo_pick_context('etd.atlas.humanoid_walkfetch')
    assert 'atlas' in p.name


def test_demo_pick_context_humanoid():
    p = _demo_pick_context('etd.some.humanoid_skill')
    assert 'atlas' in p.name


def test_demo_pick_context_wia():
    p = _demo_pick_context('etd.hyundai.wia_welding')
    assert 'wia' in p.name


def test_demo_pick_context_welding():
    p = _demo_pick_context('etd.some.welding_skill')
    assert 'wia' in p.name


def test_demo_pick_context_mobed():
    p = _demo_pick_context('etd.hyundai.mobed_transport')
    assert 'mobed' in p.name


def test_demo_pick_context_transport():
    p = _demo_pick_context('etd.some.transport_skill')
    assert 'mobed' in p.name


def test_demo_pick_context_amr():
    p = _demo_pick_context('etd.some.amr_skill')
    assert 'mobed' in p.name


def test_demo_pick_context_vest():
    p = _demo_pick_context('etd.hyundai.vest_exoskeleton')
    assert 'exo' in p.name


def test_demo_pick_context_exoskeleton():
    p = _demo_pick_context('etd.some.exoskeleton_skill')
    assert 'exo' in p.name


def test_demo_pick_context_exo():
    p = _demo_pick_context('etd.some.exo_skill')
    assert 'exo' in p.name


def test_demo_pick_context_default():
    p = _demo_pick_context('etd.pickplace.basic')
    assert 'runtime_context.json' == p.name


def test_level_ok_a():
    assert _level_ok('A') is True


def test_level_ok_b():
    assert _level_ok('B') is True


def test_level_ok_d():
    assert _level_ok('D') is False


def test_level_ok_c():
    assert _level_ok('C') is False


def test_demo_run_all_returns_eight_packages():
    results = demo_run_all()
    assert len(results) == 8


def test_demo_run_all_all_level_a():
    results = demo_run_all()
    for r in results:
        assert r['level'] == 'A', f"{r['package']} is level {r['level']}"


def test_demo_run_all_result_keys():
    results = demo_run_all()
    for r in results:
        for key in ('package', 'valid', 'level', 'score', 'ctx', 'errors', 'warnings'):
            assert key in r, f"Missing key '{key}' in {r}"


def test_demo_run_all_fail_fast_completes_when_all_pass():
    results = demo_run_all(fail_fast=True)
    assert len(results) == 8


def test_print_table_shows_pass(capsys):
    results = [{'package': 'etd.x', 'ctx': 'runtime_context.json',
                'level': 'A', 'score': 1.0, 'compat_errors': [], 'errors': [], 'warnings': []}]
    _print_table(results)
    out = capsys.readouterr().out
    assert 'PASS' in out
    assert 'etd.x' in out


def test_print_table_shows_fail(capsys):
    results = [{'package': 'etd.y', 'ctx': 'runtime_context.json',
                'level': 'D', 'score': 0.2, 'compat_errors': ['missing_service'],
                'errors': ['schema_error'], 'warnings': ['warn1']}]
    _print_table(results)
    out = capsys.readouterr().out
    assert 'FAIL' in out
    assert 'missing_service' in out
    assert 'schema_error' in out
    assert 'warn1' in out


def test_print_table_summary_line(capsys):
    results = [
        {'package': 'etd.a', 'ctx': 'ctx.json', 'level': 'A', 'score': 1.0,
         'compat_errors': [], 'errors': [], 'warnings': []},
        {'package': 'etd.b', 'ctx': 'ctx.json', 'level': 'D', 'score': 0.1,
         'compat_errors': [], 'errors': [], 'warnings': []},
    ]
    _print_table(results)
    out = capsys.readouterr().out
    assert '1/2' in out


# ── marketplace_demo._pick_context ────────────────────────────────────────────

from sim.marketplace_demo import _pick_context as _md_pick_context


def test_md_pick_context_humanoid():
    from etd_reference_validator import RuntimeContext
    ctx = _md_pick_context('humanoid')
    assert isinstance(ctx, RuntimeContext)
    assert ctx.robot_class == 'humanoid'


def test_md_pick_context_atlas():
    from etd_reference_validator import RuntimeContext
    ctx = _md_pick_context('atlas')
    assert isinstance(ctx, RuntimeContext)


def test_md_pick_context_welding():
    from etd_reference_validator import RuntimeContext
    ctx = _md_pick_context('welding')
    assert isinstance(ctx, RuntimeContext)
    assert ctx.robot_class == 'cobot'


def test_md_pick_context_transport():
    from etd_reference_validator import RuntimeContext
    ctx = _md_pick_context('transport')
    assert isinstance(ctx, RuntimeContext)


def test_md_pick_context_assist():
    from etd_reference_validator import RuntimeContext
    ctx = _md_pick_context('assist')
    assert isinstance(ctx, RuntimeContext)


def test_md_pick_context_default():
    from marketplace.skill_store import default_runtime_context
    ctx = _md_pick_context('unknown_family')
    default = default_runtime_context()
    assert ctx.robot_class == default.robot_class


# ── report_runner._pick_context ───────────────────────────────────────────────

from sim.report_runner import _pick_context as _rr_pick_context


def test_rr_pick_context_atlas():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.atlas.humanoid_walkfetch', contexts)
    assert ctx is contexts['atlas']


def test_rr_pick_context_humanoid():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.some.humanoid_skill', contexts)
    assert ctx is contexts['atlas']


def test_rr_pick_context_wia_welding():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.hyundai.wia_welding', contexts)
    assert ctx is contexts['wia']


def test_rr_pick_context_wia_weld():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.hyundai.wia_weld_v2', contexts)
    assert ctx is contexts['wia']


def test_rr_pick_context_mobed():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.hyundai.mobed_transport', contexts)
    assert ctx is contexts['mobed']


def test_rr_pick_context_transport():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.some.transport_skill', contexts)
    assert ctx is contexts['mobed']


def test_rr_pick_context_vest():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.hyundai.vest_exoskeleton', contexts)
    assert ctx is contexts['exo']


def test_rr_pick_context_exoskeleton():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.some.exoskeleton_device', contexts)
    assert ctx is contexts['exo']


def test_rr_pick_context_base_fallback():
    contexts = _load_contexts(ROOT)
    ctx = _rr_pick_context('etd.pickplace.basic', contexts)
    assert ctx is contexts['base']
