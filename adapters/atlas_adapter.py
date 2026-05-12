"""Boston Dynamics Atlas / Orbit middleware adapter.

Maps ETD service topics to the BD Orbit fleet-management and Atlas ROS 2
topic namespace.

Boston Dynamics Atlas at HMGMA (planned 2028) uses:
  - BD Orbit  — fleet orchestration, mission dispatch, telemetry bus
  - rclpy     — ROS 2 topics for on-robot sensor/actuator bridging
  - Spot SDK  — optional; used for auxiliary perception and state queries

In ``dry_run=True`` mode (default) all reads return mock responses and
publishes are appended to ``adapter.published``, allowing the Atlas
walk-fetch skill to run fully in CI.

ETD → Orbit / Atlas ROS 2 topic mapping::

    ETD service topic              Orbit / Atlas ROS 2 topic
    ─────────────────────────────────────────────────────────────────
    state.safety_state             /atlas/safety/state
    state.balance_state            /atlas/body/balance_state
    perception.scene_map           /atlas/perception/scene_map
    perception.object_pose         /atlas/perception/object_pose
    command.skill_intent           /orbit/skill/intent
    locomotion.walking_started     /atlas/locomotion/walking_started
    locomotion.target_reached      /atlas/locomotion/target_reached
    grasp.contact_detected         /atlas/manipulation/contact_detected
    grasp.object_secured           /atlas/manipulation/object_secured
    carry.balanced                 /atlas/body/carry_balanced
    handover.offered               /atlas/manipulation/handover_offered
    handover.accepted              /atlas/manipulation/handover_accepted
    delivery.deposited             /atlas/manipulation/deposited
    telemetry.events               /orbit/etd/telemetry
    primitive.entered              /orbit/skill/primitive_entered
    primitive.exited               /orbit/skill/primitive_exited
    skill.started                  /orbit/skill/started
    skill.completed                /orbit/skill/completed
    skill.aborted                  /orbit/skill/aborted
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter  # noqa: E402
from adapters.telemetry_sink import NullSink, TelemetrySink  # noqa: E402

_ETD_TO_ORBIT: Dict[str, str] = {
    'state.safety_state':         '/atlas/safety/state',
    'state.balance_state':        '/atlas/body/balance_state',
    'perception.scene_map':       '/atlas/perception/scene_map',
    'perception.object_pose':     '/atlas/perception/object_pose',
    'command.skill_intent':       '/orbit/skill/intent',
    'locomotion.walking_started': '/atlas/locomotion/walking_started',
    'locomotion.target_reached':  '/atlas/locomotion/target_reached',
    'grasp.contact_detected':     '/atlas/manipulation/contact_detected',
    'grasp.object_secured':       '/atlas/manipulation/object_secured',
    'carry.balanced':             '/atlas/body/carry_balanced',
    'handover.offered':           '/atlas/manipulation/handover_offered',
    'handover.accepted':          '/atlas/manipulation/handover_accepted',
    'delivery.deposited':         '/atlas/manipulation/deposited',
    'telemetry.events':           '/orbit/etd/telemetry',
    'primitive.entered':          '/orbit/skill/primitive_entered',
    'primitive.exited':           '/orbit/skill/primitive_exited',
    'skill.started':              '/orbit/skill/started',
    'skill.completed':            '/orbit/skill/completed',
    'skill.aborted':              '/orbit/skill/aborted',
}

_DEFAULT_MOCK_STATE: Dict[str, Any] = {
    'state.safety_state': {
        'human_in_forbidden_zone': False,
        'balance_fault': False,
        'estop_active': False,
        'collision_detected': False,
        'human_ready_signal': True,
        'human_distance_m': 3.0,
    },
    'state.balance_state': {
        'stable': True,
        'com_height_m': 1.2,
        'stance': 'bipedal',
        'balance_score': 0.97,
    },
    'perception.scene_map': {
        'map_ready': True,
        'target_visible': True,
        'target_id': 'mock_object_001',
    },
    'perception.object_pose': {
        'x_m': 1.5, 'y_m': 0.0, 'z_m': 0.8,
        'confidence': 0.91,
        'object_id': 'mock_object_001',
    },
}


class AtlasAdapter(ETDMiddleware):
    """ETD middleware adapter for the Boston Dynamics Atlas humanoid robot.

    Bridges ETD service topics to the BD Orbit fleet orchestration layer
    and Atlas ROS 2 topic namespace.

    Parameters
    ----------
    dry_run:
        When True (default), reads from mock state; publishes recorded to
        ``self.published``. No BD SDK / ROS 2 connection attempted.
    telemetry_sink:
        Optional TelemetrySink for ``telemetry.events`` publishes.
    orbit_endpoint:
        Orbit REST API base URL (e.g. ``http://orbit.local:5001``).
        Only used in live mode.
    """

    required_topics: List[str] = [
        'state.safety_state',
        'state.balance_state',
        'perception.scene_map',
        'perception.object_pose',
        'command.skill_intent',
        'telemetry.events',
    ]

    def __init__(
        self,
        dry_run: bool = True,
        telemetry_sink: Optional[TelemetrySink] = None,
        orbit_endpoint: str = 'http://localhost:5001',
    ) -> None:
        self._dry_run = dry_run
        self._mock: Dict[str, Any] = {k: dict(v) for k, v in _DEFAULT_MOCK_STATE.items()}
        self.published: List[Dict[str, Any]] = []
        self._sink: TelemetrySink = telemetry_sink or NullSink()
        self._orbit_endpoint = orbit_endpoint
        self._ros2_node = None
        if not dry_run:
            self._ros2_node = self._init_ros2()

    # ── ETDMiddleware interface ───────────────────────────────────────────────

    def read(self, topic: str) -> Dict[str, Any]:
        if self._dry_run:
            return dict(self._mock.get(topic, {}))
        ros_topic = _ETD_TO_ORBIT.get(topic, topic)
        return self._ros2_read(ros_topic)

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if topic == 'telemetry.events':
            event_name = message.get('event', topic)
            self._sink.emit(event_name, {k: v for k, v in message.items() if k != 'event'})
        if self._dry_run:
            self.published.append({'topic': topic, 'message': message, 'ts': time.time()})
            return
        ros_topic = _ETD_TO_ORBIT.get(topic, topic)
        self._ros2_publish(ros_topic, message)

    def validate(self) -> None:
        if not self._dry_run and self._ros2_node is None:
            raise RuntimeError(
                "AtlasAdapter: ROS 2 node not initialized. "
                "Ensure rclpy is installed and the workspace is sourced."
            )

    # ── Utility helpers ───────────────────────────────────────────────────────

    def inject_state(self, topic: str, patch: Dict[str, Any]) -> None:
        """Merge *patch* into the mock state for *topic*."""
        self._mock[topic] = {**self._mock.get(topic, {}), **patch}

    def set_balance(self, stable: bool, balance_score: float = 0.97) -> None:
        """Set the mock balance state."""
        self.inject_state('state.balance_state', {
            'stable': stable, 'balance_score': balance_score,
        })

    def set_object_pose(
        self, x_m: float, y_m: float, z_m: float, confidence: float = 0.91
    ) -> None:
        """Set the mock object pose for perception."""
        self.inject_state('perception.object_pose', {
            'x_m': x_m, 'y_m': y_m, 'z_m': z_m, 'confidence': confidence,
        })
        self.inject_state('perception.scene_map', {
            'map_ready': True, 'target_visible': True,
        })

    def topic_for(self, etd_topic: str) -> str:
        """Return the Orbit / Atlas ROS 2 topic for an ETD service topic."""
        return _ETD_TO_ORBIT.get(etd_topic, etd_topic)

    # ── ROS 2 / Orbit stubs ───────────────────────────────────────────────────

    def _init_ros2(self):
        try:
            import rclpy  # type: ignore[import]
            rclpy.init()
            return rclpy.create_node('etd_atlas_adapter')
        except ImportError:
            raise RuntimeError(
                "rclpy not found. Install ROS 2 Humble and source the workspace, "
                "or use AtlasAdapter(dry_run=True)."
            )

    def _ros2_read(self, ros_topic: str) -> Dict[str, Any]:
        raise NotImplementedError(
            f"Live ROS 2 read not implemented for {ros_topic}. "
            "Override _ros2_read() with rclpy subscriber or Orbit REST call."
        )

    def _ros2_publish(self, ros_topic: str, message: Dict[str, Any]) -> None:
        raise NotImplementedError(
            f"Live ROS 2 publish not implemented for {ros_topic}. "
            "Override _ros2_publish() with rclpy publisher or Orbit REST call."
        )
