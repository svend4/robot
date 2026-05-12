"""Tests for the ROS 2 bridge (ETDSkillActionServer) — no ROS 2 installation required."""
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_BRIDGE_DIR = ROOT / 'integrations' / 'ros2' / 'etd_ros2_bridge' / 'etd_ros2_bridge'
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from skill_action_server import ETDSkillActionServer


class _NominalMiddleware:
    """Minimal middleware that returns safe nominal state for all reads."""

    _TOPIC_DEFAULTS = {
        'state.safety_state': {
            'human_in_forbidden_zone': False, 'emergency_stop': False,
            'human_ready_signal': True, 'human_in_safety_radius': True,
            'human_distance_m': 2.0, 'normal_force_n': 12.0,
            'confidence': 0.96, 'aligned': True,
        },
        'force_control.contact_feedback': {'normal_force_n': 12.0},
        'perception.part_alignment': {'confidence': 0.96, 'offset_mm': 0.15, 'aligned': True},
        'perception.camera_frame': {'frame_id': 1, 'width': 1920, 'height': 1080},
        'perception.scene_map': {'map_ready': True, 'obstacles': []},
        'state.balance_state': {'stable': True, 'com_margin': 0.12, 'gait': 'stand'},
        'perception.object_pose': {
            'confidence': 0.96, 'x': 3.0, 'y': 1.5, 'z': 0.8,
            'object_class': 'automotive_part', 'mass_estimate_kg': 4.5,
        },
        'perception.seam_tracker': {'confidence': 0.96, 'offset_mm': 0.3, 'seam_found': True},
        'vision.weld_inspection': {'pass': True, 'defects': [], 'confidence': 0.97},
        'perception.obstacle_detector': {'obstacles': [], 'clear': True},
        'navigation.path_planner': {'path_ready': True, 'estimated_time_s': 30},
        'manipulation.lift_control': {'lift_ready': True, 'current_height_mm': 0},
        'state.exo_joint_state': {'calibrated': True, 'torque_within_limits': True},
        'perception.intent_detector': {'confidence': 0.96, 'mode': 'overhead', 'direction': 'up'},
        'state.fatigue_monitor': {'fatigue_pct': 20, 'session_sec': 0},
        'perception.imu_pose': {'valid': True, 'roll_deg': 0.2, 'pitch_deg': 0.1, 'yaw_deg': 0.0},
    }

    def publish(self, topic, msg):
        pass

    def read(self, topic):
        return self._TOPIC_DEFAULTS.get(topic)


_MW = _NominalMiddleware()

_ALL_SKILLS = [
    ('etd.pickplace.basic',          {'chsProfile': 'fragile_item',   'priority': 'normal'}),
    ('etd.assembly.precision',       {'chsProfile': 'peg_in_hole',    'priority': 'normal'}),
    ('etd.inspect.vision',           {'chsProfile': 'defect_scan',    'priority': 'normal'}),
    ('etd.cobot.safeassist',         {'chsProfile': 'safe_handover',  'priority': 'normal'}),
    ('etd.atlas.humanoid_walkfetch', {'chsProfile': 'sequencing_carry','priority': 'normal'}),
    ('etd.hyundai.wia_welding',      {'chsProfile': 'standard_seam',  'priority': 'normal'}),
    ('etd.hyundai.mobed_transport',  {'chsProfile': 'standard_carry', 'priority': 'normal'}),
    ('etd.hyundai.vest_exoskeleton', {'profileId':  'overhead_assembly','priority': 'normal'}),
]


# ── Adapter loading ───────────────────────────────────────────────────────────

def test_server_loads_adapter():
    server = ETDSkillActionServer('etd.pickplace.basic')
    assert server.skill_id == 'etd.pickplace.basic'
    assert callable(server._adapter)


def test_server_node_name_defaults():
    server = ETDSkillActionServer('etd.pickplace.basic')
    assert server.node_name == 'etd_etd_pickplace_basic'


def test_server_custom_node_name():
    server = ETDSkillActionServer('etd.pickplace.basic', node_name='my_node')
    assert server.node_name == 'my_node'


def test_server_raises_on_missing_package():
    with pytest.raises(FileNotFoundError):
        ETDSkillActionServer('etd.does.not.exist')


# ── execute_goal — all 8 packages ────────────────────────────────────────────

@pytest.mark.parametrize('skill_id,goal', _ALL_SKILLS)
def test_execute_goal_completes(skill_id, goal):
    random.seed(42)
    server = ETDSkillActionServer(skill_id)
    result = server.execute_goal(goal, middleware=_MW)
    assert result.get('status') == 'completed', \
        f'{skill_id}: status={result.get("status")!r}, reason={result.get("reason")!r}'


# ── Server-busy guard ─────────────────────────────────────────────────────────

def test_execute_goal_server_busy_returns_aborted():
    server = ETDSkillActionServer('etd.pickplace.basic')
    server._active = True
    result = server.execute_goal({'chsProfile': 'fragile_item'}, middleware=_MW)
    server._active = False
    assert result['status'] == 'aborted'
    assert result['reason'] == 'server_busy'


# ── Feedback callback ─────────────────────────────────────────────────────────

def test_execute_goal_calls_feedback_fn():
    random.seed(42)
    events = []
    server = ETDSkillActionServer('etd.pickplace.basic')
    server.execute_goal(
        {'chsProfile': 'fragile_item'},
        feedback_fn=lambda msg: events.append(msg.get('event', '')),
        middleware=_MW,
    )
    assert 'skill.started' in events
    assert 'primitive.entered' in events
    assert 'skill.completed' in events


def test_execute_goal_feedback_only_for_telemetry_events():
    random.seed(42)
    callbacks = []
    server = ETDSkillActionServer('etd.pickplace.basic')
    server.execute_goal(
        {'chsProfile': 'fragile_item'},
        feedback_fn=lambda msg: callbacks.append(msg),
        middleware=_MW,
    )
    assert len(callbacks) > 0
    assert all('event' in m for m in callbacks), \
        'feedback_fn should only receive telemetry.events messages'


# ── ETDSkillActionClient ──────────────────────────────────────────────────────

from skill_action_client import ETDSkillActionClient


def test_client_dry_run_completes():
    client = ETDSkillActionClient('etd.pickplace.basic')
    result = client.send_goal({'chsProfile': 'small_box', 'priority': 'normal'}, dry_run=True)
    assert result.get('status') == 'completed'


def test_client_dry_run_feedback_printed(capsys):
    client = ETDSkillActionClient('etd.pickplace.basic')
    client.send_goal({'chsProfile': 'small_box'}, dry_run=True)
    out = capsys.readouterr().out
    assert 'ETD Client' in out


def test_client_ros2_raises_without_rclpy():
    client = ETDSkillActionClient('etd.pickplace.basic')
    with pytest.raises(RuntimeError, match='rclpy not available'):
        client.send_goal({'chsProfile': 'small_box'}, dry_run=False)


# ── ETDSkillActionServer.run_ros2 ─────────────────────────────────────────────

def test_server_run_ros2_raises_without_rclpy():
    server = ETDSkillActionServer('etd.pickplace.basic')
    with pytest.raises(RuntimeError, match='rclpy not available'):
        server.run_ros2()


# ── _FeedbackMiddleware with no inner middleware ──────────────────────────────

def test_execute_goal_no_middleware_completes():
    random.seed(42)
    server = ETDSkillActionServer('etd.pickplace.basic')
    result = server.execute_goal({'chsProfile': 'fragile_item'}, middleware=None)
    assert result.get('status') == 'completed'


def test_execute_goal_no_middleware_with_feedback_fn():
    random.seed(42)
    events = []
    server = ETDSkillActionServer('etd.pickplace.basic')
    server.execute_goal(
        {'chsProfile': 'fragile_item'},
        feedback_fn=lambda msg: events.append(msg.get('event', '')),
        middleware=None,
    )
    assert 'skill.started' in events


def test_execute_goal_no_feedback_no_middleware():
    random.seed(42)
    server = ETDSkillActionServer('etd.pickplace.basic')
    result = server.execute_goal({'chsProfile': 'fragile_item'},
                                 feedback_fn=None, middleware=None)
    assert result.get('status') == 'completed'


# ── ETDSkillActionClient — all-8 via server.execute_goal + _MW ───────────────

@pytest.mark.parametrize('skill_id,goal', _ALL_SKILLS)
def test_client_execute_via_server_with_middleware(skill_id, goal):
    """Verify every skill completes when given a complete middleware."""
    random.seed(42)
    server = ETDSkillActionServer(skill_id)
    result = server.execute_goal(goal, middleware=_MW)
    assert result.get('status') == 'completed', \
        f'{skill_id}: {result.get("reason")!r}'


# ── ETDSkillActionServer.main(--dry-run) ──────────────────────────────────────

import sys as _sys

from skill_action_server import main as _server_main
from skill_action_client import ETDSkillActionClient, main as _client_main


def test_server_main_dry_run_completes(capsys, monkeypatch):
    monkeypatch.setattr(_sys, 'argv',
                        ['skill_action_server.py', '--skill', 'etd.pickplace.basic', '--dry-run'])
    _server_main()
    out = capsys.readouterr().out
    assert 'Dry run' in out
    assert 'etd.pickplace.basic' in out


def test_server_main_dry_run_json_result(capsys, monkeypatch):
    import json as _json
    monkeypatch.setattr(_sys, 'argv',
                        ['skill_action_server.py', '--skill', 'etd.pickplace.basic', '--dry-run'])
    _server_main()
    out = capsys.readouterr().out
    json_start = out.find('{')
    assert json_start != -1
    parsed = _json.loads(out[json_start:])
    assert 'status' in parsed


# ── ETDSkillActionClient.main(--dry-run) ──────────────────────────────────────

def test_client_main_dry_run_exits_zero(capsys, monkeypatch):
    monkeypatch.setattr(_sys, 'argv', [
        'skill_action_client.py',
        '--skill', 'etd.pickplace.basic',
        '--profile', 'small_box',
        '--dry-run',
    ])
    with pytest.raises(SystemExit) as exc_info:
        _client_main()
    assert exc_info.value.code == 0


def test_client_main_dry_run_output(capsys, monkeypatch):
    monkeypatch.setattr(_sys, 'argv', [
        'skill_action_client.py',
        '--skill', 'etd.pickplace.basic',
        '--profile', 'small_box',
        '--dry-run',
    ])
    try:
        _client_main()
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert 'ETD Client' in out
    assert 'etd.pickplace.basic' in out


# ── main() else branch: no --dry-run → calls run_ros2() → RuntimeError ───────

def test_server_main_no_dry_run_calls_run_ros2(monkeypatch):
    monkeypatch.setattr(_sys, 'argv', [
        'skill_action_server.py', '--skill', 'etd.pickplace.basic',
    ])
    with pytest.raises(RuntimeError, match='rclpy not available'):
        _server_main()


# ── run_ros2(): fake rclpy → lines 112-113, 121-134 ──────────────────────────

def test_server_run_ros2_with_mocked_rclpy_no_action_type(monkeypatch):
    """run_ros2(): inject fake rclpy → import lines 112-113 execute; rclpy.init() + Node()
    called (lines 121-123); etd_ros2_bridge.action ImportError → shutdown + return (lines 130-134)."""
    from unittest.mock import MagicMock

    fake_rclpy = MagicMock()
    fake_rclpy_action = MagicMock()
    fake_rclpy_node = MagicMock()

    monkeypatch.setitem(sys.modules, 'rclpy', fake_rclpy)
    monkeypatch.setitem(sys.modules, 'rclpy.action', fake_rclpy_action)
    monkeypatch.setitem(sys.modules, 'rclpy.node', fake_rclpy_node)

    server = ETDSkillActionServer('etd.pickplace.basic')
    server.run_ros2()   # should return (not raise) after etd_ros2_bridge.action ImportError

    fake_rclpy.init.assert_called_once()
    fake_rclpy.shutdown.assert_called_once()


# ── _ros2_execute(): fake rclpy → lines 69-70, 74-78 ─────────────────────────

def test_client_ros2_execute_with_mocked_rclpy_no_action_type(monkeypatch):
    """_ros2_execute(): inject fake rclpy so lines 69-70 execute; etd_ros2_bridge.action
    then raises ImportError → RuntimeError at lines 77-78."""
    from unittest.mock import MagicMock

    fake_rclpy = MagicMock()
    fake_rclpy_action = MagicMock()
    fake_rclpy_node = MagicMock()

    monkeypatch.setitem(sys.modules, 'rclpy', fake_rclpy)
    monkeypatch.setitem(sys.modules, 'rclpy.action', fake_rclpy_action)
    monkeypatch.setitem(sys.modules, 'rclpy.node', fake_rclpy_node)

    client = ETDSkillActionClient('etd.pickplace.basic')
    with pytest.raises(RuntimeError, match='ExecuteSkill action type not built'):
        client.send_goal({'chsProfile': 'small_box'}, dry_run=False)


# ── run_ros2(): full mock — ActionServer callback captured + invoked (lines 136-156) ──

def test_server_run_ros2_with_full_mock_captures_and_invokes_callback(monkeypatch):
    """run_ros2(): inject both rclpy and etd_ros2_bridge.action so ExecuteSkill import
    succeeds (line 128). _FakeActionServer captures _execute_callback (line 150).
    rclpy.spin raises KeyboardInterrupt → finally: rclpy.shutdown() (lines 153-156).
    Callback is then invoked manually to cover lines 136-148."""
    import json as _json
    from unittest.mock import MagicMock

    fake_rclpy = MagicMock()
    fake_rclpy.spin.side_effect = KeyboardInterrupt
    fake_rclpy_action = MagicMock()
    fake_rclpy_node = MagicMock()
    fake_etd_action = MagicMock()

    captured_callbacks = []

    class _FakeActionServer:
        def __init__(self, node, action_type, action_name, callback):
            captured_callbacks.append(callback)

    fake_rclpy_action.ActionServer = _FakeActionServer

    monkeypatch.setitem(sys.modules, 'rclpy', fake_rclpy)
    monkeypatch.setitem(sys.modules, 'rclpy.action', fake_rclpy_action)
    monkeypatch.setitem(sys.modules, 'rclpy.node', fake_rclpy_node)
    monkeypatch.setitem(sys.modules, 'etd_ros2_bridge', MagicMock())
    monkeypatch.setitem(sys.modules, 'etd_ros2_bridge.action', fake_etd_action)

    server = ETDSkillActionServer('etd.pickplace.basic')
    with pytest.raises(KeyboardInterrupt):
        server.run_ros2()

    fake_rclpy.init.assert_called_once()
    fake_rclpy.shutdown.assert_called_once()
    assert len(captured_callbacks) == 1

    # Invoke the captured _execute_callback to cover lines 136-148
    random.seed(42)
    fake_goal_handle = MagicMock()
    fake_goal_handle.request.job_context_json = _json.dumps(
        {'chsProfile': 'small_box', 'priority': 'normal'}
    )
    cb_result = captured_callbacks[0](fake_goal_handle)
    fake_goal_handle.succeed.assert_called_once()
    assert cb_result is not None


# ── _ros2_execute(): full mock — timeout, rejection, and happy-path (lines 79-109) ──

def _make_full_ros2_mocks(monkeypatch):
    """Inject fake rclpy + etd_ros2_bridge.action into sys.modules; return fake_rclpy
    and a configurable fake ActionClient instance."""
    from unittest.mock import MagicMock
    fake_rclpy = MagicMock()
    fake_rclpy_action = MagicMock()
    fake_rclpy_node = MagicMock()
    fake_etd_action = MagicMock()
    fake_ac = MagicMock()
    fake_rclpy_action.ActionClient.return_value = fake_ac
    monkeypatch.setitem(sys.modules, 'rclpy', fake_rclpy)
    monkeypatch.setitem(sys.modules, 'rclpy.action', fake_rclpy_action)
    monkeypatch.setitem(sys.modules, 'rclpy.node', fake_rclpy_node)
    monkeypatch.setitem(sys.modules, 'etd_ros2_bridge', MagicMock())
    monkeypatch.setitem(sys.modules, 'etd_ros2_bridge.action', fake_etd_action)
    return fake_rclpy, fake_ac


def test_client_ros2_execute_timeout_when_server_unavailable(monkeypatch):
    """_ros2_execute(): wait_for_server returns False → rclpy.shutdown() + TimeoutError
    (lines 84-86)."""
    fake_rclpy, fake_ac = _make_full_ros2_mocks(monkeypatch)
    fake_ac.wait_for_server.return_value = False

    client = ETDSkillActionClient('etd.pickplace.basic')
    with pytest.raises(TimeoutError, match='Action server not available'):
        client.send_goal({'chsProfile': 'small_box'}, dry_run=False)

    fake_rclpy.shutdown.assert_called_once()


def test_client_ros2_execute_goal_rejected(monkeypatch):
    """_ros2_execute(): goal_handle.accepted=False → returns rejected dict (lines 100-102)."""
    import json as _json
    from unittest.mock import MagicMock
    fake_rclpy, fake_ac = _make_full_ros2_mocks(monkeypatch)
    fake_ac.wait_for_server.return_value = True

    fake_goal_handle = MagicMock()
    fake_goal_handle.accepted = False
    fake_future = MagicMock()
    fake_future.result.return_value = fake_goal_handle
    fake_ac.send_goal_async.return_value = fake_future

    client = ETDSkillActionClient('etd.pickplace.basic')
    result = client.send_goal({'chsProfile': 'small_box'}, dry_run=False)
    assert result == {'status': 'rejected', 'reason': 'goal_rejected_by_server'}
    fake_rclpy.shutdown.assert_called_once()


def test_client_ros2_execute_goal_accepted_returns_result(monkeypatch):
    """_ros2_execute(): full happy path — goal accepted, result parsed from JSON
    (lines 88-109)."""
    import json as _json
    from unittest.mock import MagicMock
    fake_rclpy, fake_ac = _make_full_ros2_mocks(monkeypatch)
    fake_ac.wait_for_server.return_value = True

    fake_goal_handle = MagicMock()
    fake_goal_handle.accepted = True
    fake_future = MagicMock()
    fake_future.result.return_value = fake_goal_handle
    fake_ac.send_goal_async.return_value = fake_future

    expected = {'status': 'completed', 'primitives_executed': 5}
    fake_result_response = MagicMock()
    fake_result_response.result.result_json = _json.dumps(expected)
    fake_result_future = MagicMock()
    fake_result_future.result.return_value = fake_result_response
    fake_goal_handle.get_result_async.return_value = fake_result_future

    client = ETDSkillActionClient('etd.pickplace.basic')
    result = client.send_goal({'chsProfile': 'small_box'}, dry_run=False)
    assert result['status'] == 'completed'
    fake_rclpy.shutdown.assert_called_once()


# ── _local_execute(): sys.path.insert True branch (line 52) ──────────────────

def test_client_local_execute_inserts_bridge_dir_when_missing(monkeypatch):
    """_local_execute(): if str(_bridge_dir) not in sys.path → sys.path.insert (line 52).
    Temporarily remove the bridge dir from sys.path so the guard fires."""
    import random
    bridge_dir_str = str(_BRIDGE_DIR)
    # Remove bridge dir from sys.path so condition on line 51 is True
    monkeypatch.setattr(sys, 'path', [p for p in sys.path if p != bridge_dir_str])
    assert bridge_dir_str not in sys.path

    random.seed(42)
    client = ETDSkillActionClient('etd.pickplace.basic')
    result = client.send_goal({'chsProfile': 'fragile_item'}, dry_run=True)
    assert result.get('status') == 'completed'
    assert bridge_dir_str in sys.path  # must have been re-inserted


# ── _ros2_execute(): feedback callback body invoked (lines 93-94) ─────────────

def test_client_ros2_execute_invokes_feedback_callback(monkeypatch):
    """_ros2_execute(): rclpy.spin_until_future_complete invokes _fb_callback →
    lines 93-94 (feedback_received.append + logger.info) are executed."""
    import json as _json
    from unittest.mock import MagicMock
    fake_rclpy, fake_ac = _make_full_ros2_mocks(monkeypatch)
    fake_ac.wait_for_server.return_value = True

    # Setup goal handle that is accepted + returns a result
    fake_goal_handle = MagicMock()
    fake_goal_handle.accepted = True
    expected_result = {'status': 'completed'}
    fake_result_resp = MagicMock()
    fake_result_resp.result.result_json = _json.dumps(expected_result)
    fake_result_future = MagicMock()
    fake_result_future.result.return_value = fake_result_resp
    fake_goal_handle.get_result_async.return_value = fake_result_future

    fake_goal_future = MagicMock()
    fake_goal_future.result.return_value = fake_goal_handle

    # Capture the feedback_callback passed to send_goal_async
    captured_fb_callbacks = []

    def _send_goal_side_effect(goal, feedback_callback=None):
        if feedback_callback:
            captured_fb_callbacks.append(feedback_callback)
        return fake_goal_future

    fake_ac.send_goal_async.side_effect = _send_goal_side_effect

    # On the first spin call, invoke the captured callback (simulates ROS 2 feedback)
    spin_call_count = [0]

    def _spin_side_effect(node, future):
        spin_call_count[0] += 1
        if spin_call_count[0] == 1 and captured_fb_callbacks:
            fake_fb = MagicMock()
            fake_fb.feedback.current_event = 'primitive.entered'
            captured_fb_callbacks[0](fake_fb)  # → lines 93-94

    fake_rclpy.spin_until_future_complete.side_effect = _spin_side_effect

    client = ETDSkillActionClient('etd.pickplace.basic')
    result = client.send_goal({'chsProfile': 'small_box'}, dry_run=False)

    assert result['status'] == 'completed'
    assert len(captured_fb_callbacks) == 1
    assert spin_call_count[0] == 2  # goal spin + result spin
    fake_rclpy.shutdown.assert_called_once()
