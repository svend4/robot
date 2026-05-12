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
