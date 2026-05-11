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
    assert len(results) == 7
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
    assert ctx_map['etd.pickplace.basic']          == 'runtime_context.json'


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
