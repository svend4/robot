"""Hyundai MobED H-Rise middleware adapter.

Maps ETD service topics to the H-Rise AMR ROS 2 topic namespace.

In ``dry_run=True`` mode (default) all reads return mock responses and
publishes are appended to ``adapter.published``.  This allows the MobED
transport skill to be exercised in CI without a physical robot.

ETD → H-Rise topic mapping::

    ETD service topic            H-Rise ROS 2 topic
    ────────────────────────────────────────────────────────────
    state.robot_pose             /hrise/localization/pose
    state.safety_state           /hrise/safety/state
    state.battery                /hrise/power/battery
    navigation.waypoints         /hrise/navigation/waypoints
    navigation.started           /hrise/navigation/started
    navigation.progress          /hrise/navigation/progress
    navigation.arrived           /hrise/navigation/arrived
    command.skill_intent         /hrise/skill/intent
    transport.lifted             /hrise/payload/lifted
    transport.delivered          /hrise/payload/delivered
    safety.human_near            /hrise/safety/human_near
    telemetry.events             /hrise/etd/telemetry
    primitive.entered            /hrise/skill/primitive_entered
    primitive.exited             /hrise/skill/primitive_exited
    skill.started                /hrise/skill/started
    skill.completed              /hrise/skill/completed
    skill.aborted                /hrise/skill/aborted
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter  # noqa: E402
from adapters.telemetry_sink import NullSink, TelemetrySink  # noqa: E402

_ETD_TO_HRISE: Dict[str, str] = {
    'state.robot_pose':         '/hrise/localization/pose',
    'state.safety_state':       '/hrise/safety/state',
    'state.battery':            '/hrise/power/battery',
    'navigation.waypoints':     '/hrise/navigation/waypoints',
    'navigation.started':       '/hrise/navigation/started',
    'navigation.progress':      '/hrise/navigation/progress',
    'navigation.arrived':       '/hrise/navigation/arrived',
    'command.skill_intent':     '/hrise/skill/intent',
    'transport.lifted':         '/hrise/payload/lifted',
    'transport.delivered':      '/hrise/payload/delivered',
    'safety.human_near':        '/hrise/safety/human_near',
    'telemetry.events':         '/hrise/etd/telemetry',
    'primitive.entered':        '/hrise/skill/primitive_entered',
    'primitive.exited':         '/hrise/skill/primitive_exited',
    'skill.started':            '/hrise/skill/started',
    'skill.completed':          '/hrise/skill/completed',
    'skill.aborted':            '/hrise/skill/aborted',
}

_DEFAULT_MOCK_STATE: Dict[str, Any] = {
    'state.robot_pose': {
        'x_m': 0.0, 'y_m': 0.0, 'heading_deg': 0.0,
        'localization_quality': 0.98,
    },
    'state.safety_state': {
        'human_in_forbidden_zone': False,
        'human_in_safety_radius': False,
        'estop_active': False,
        'obstacle_detected': False,
        'human_distance_m': 3.0,
    },
    'state.battery': {
        'charge_pct': 85.0, 'voltage_v': 48.2, 'estimated_range_m': 4200,
    },
    'navigation.waypoints': {
        'waypoints': [], 'active': False,
    },
}


class HyundaiMobEDAdapter(ETDMiddleware):
    """ETD middleware adapter for the Hyundai MobED H-Rise AMR platform.

    Parameters
    ----------
    dry_run:
        When True (default), reads from mock state; publishes recorded to
        ``self.published``. No ROS 2 connection attempted.
    telemetry_sink:
        Optional sink for ``telemetry.events`` publishes. Defaults to NullSink.
    initial_pose:
        Optional dict to override the default mock robot pose at construction.
    """

    required_topics: List[str] = [
        'state.robot_pose',
        'state.safety_state',
        'command.skill_intent',
        'telemetry.events',
    ]

    def __init__(
        self,
        dry_run: bool = True,
        telemetry_sink: Optional[TelemetrySink] = None,
        initial_pose: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._dry_run = dry_run
        self._mock: Dict[str, Any] = {k: dict(v) for k, v in _DEFAULT_MOCK_STATE.items()}
        if initial_pose:
            self._mock['state.robot_pose'].update(initial_pose)
        self.published: List[Dict[str, Any]] = []
        self._sink: TelemetrySink = telemetry_sink or NullSink()
        self._ros2_node = None
        if not dry_run:
            self._ros2_node = self._init_ros2()

    # ── ETDMiddleware interface ───────────────────────────────────────────────

    def read(self, topic: str) -> Dict[str, Any]:
        if self._dry_run:
            return dict(self._mock.get(topic, {}))
        ros_topic = _ETD_TO_HRISE.get(topic, topic)
        return self._ros2_read(ros_topic)

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if topic == 'telemetry.events':
            event_name = message.get('event', topic)
            self._sink.emit(event_name, {k: v for k, v in message.items() if k != 'event'})
        if self._dry_run:
            self.published.append({'topic': topic, 'message': message, 'ts': time.time()})
            return
        ros_topic = _ETD_TO_HRISE.get(topic, topic)
        self._ros2_publish(ros_topic, message)

    def validate(self) -> None:
        if not self._dry_run and self._ros2_node is None:
            raise RuntimeError(
                "HyundaiMobEDAdapter: ROS 2 node not initialized. "
                "Ensure rclpy is installed and the workspace is sourced."
            )

    # ── Utility helpers ───────────────────────────────────────────────────────

    def inject_state(self, topic: str, patch: Dict[str, Any]) -> None:
        """Merge *patch* into the mock state for *topic*."""
        self._mock[topic] = {**self._mock.get(topic, {}), **patch}

    def set_pose(self, x_m: float, y_m: float, heading_deg: float = 0.0) -> None:
        """Convenience helper to update the mock robot pose."""
        self.inject_state('state.robot_pose', {
            'x_m': x_m, 'y_m': y_m, 'heading_deg': heading_deg,
        })

    def topic_for(self, etd_topic: str) -> str:
        """Return the H-Rise ROS 2 topic for an ETD service topic."""
        return _ETD_TO_HRISE.get(etd_topic, etd_topic)

    # ── ROS 2 stubs ───────────────────────────────────────────────────────────

    def _init_ros2(self):
        try:
            import rclpy  # type: ignore[import]
            rclpy.init()
            return rclpy.create_node('etd_hyundai_mobed_adapter')
        except ImportError:
            raise RuntimeError(
                "rclpy not found. Install ROS 2 Humble and source the workspace, "
                "or use HyundaiMobEDAdapter(dry_run=True)."
            )

    def _ros2_read(self, ros_topic: str) -> Dict[str, Any]:
        raise NotImplementedError(
            f"Live ROS 2 read not implemented for {ros_topic}. "
            "Override _ros2_read() with rclpy subscriber / service call logic."
        )

    def _ros2_publish(self, ros_topic: str, message: Dict[str, Any]) -> None:
        raise NotImplementedError(
            f"Live ROS 2 publish not implemented for {ros_topic}. "
            "Override _ros2_publish() with rclpy publisher logic."
        )
