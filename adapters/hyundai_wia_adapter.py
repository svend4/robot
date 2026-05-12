"""Hyundai WIA H-Motion middleware adapter.

Maps ETD service topics to the H-Motion ROS 2 topic namespace.

In ``dry_run=True`` mode (the default when ROS 2 is unavailable) all reads
return values from an internal mock-state table and all publishes are
recorded to ``adapter.published`` for inspection.  This makes the adapter
fully testable without a physical robot.

For real hardware integration::

    source /opt/ros/humble/setup.bash
    colcon build --packages-select etd_ros2_bridge
    from adapters.hyundai_wia_adapter import HyundaiWIAAdapter
    mw = HyundaiWIAAdapter(dry_run=False)

ETD → H-Motion topic mapping::

    ETD service topic                H-Motion ROS 2 topic
    ──────────────────────────────────────────────────────────────
    perception.seam_tracker          /hmotion/perception/seam_tracker
    welding.torch_control            /hmotion/welding/torch_control
    welding.arc_monitor              /hmotion/welding/arc_monitor
    welding.arc_started              /hmotion/welding/arc_started
    welding.arc_stopped              /hmotion/welding/arc_stopped
    welding.seam_progress            /hmotion/welding/seam_progress
    state.safety_state               /hmotion/safety/state
    state.arm_state                  /hmotion/arm/state
    state.wrist_state                /hmotion/arm/wrist_state
    manipulation.arm_control         /hmotion/arm/control
    force_control.contact_feedback   /hmotion/force/contact
    command.skill_intent             /hmotion/skill/intent
    telemetry.events                 /hmotion/etd/telemetry
    safety.zone_monitor              /hmotion/safety/zone
    workflow.job_context             /hmotion/workflow/job
    vision.weld_inspection           /hmotion/vision/weld_inspection
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from the repo root without installation
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter  # noqa: E402
from adapters.telemetry_sink import NullSink, TelemetrySink  # noqa: E402

_ETD_TO_HMOTION: Dict[str, str] = {
    'perception.seam_tracker':        '/hmotion/perception/seam_tracker',
    'welding.torch_control':          '/hmotion/welding/torch_control',
    'welding.arc_monitor':            '/hmotion/welding/arc_monitor',
    'welding.arc_started':            '/hmotion/welding/arc_started',
    'welding.arc_stopped':            '/hmotion/welding/arc_stopped',
    'welding.seam_progress':          '/hmotion/welding/seam_progress',
    'state.safety_state':             '/hmotion/safety/state',
    'state.arm_state':                '/hmotion/arm/state',
    'state.wrist_state':              '/hmotion/arm/wrist_state',
    'manipulation.arm_control':       '/hmotion/arm/control',
    'force_control.contact_feedback': '/hmotion/force/contact',
    'command.skill_intent':           '/hmotion/skill/intent',
    'telemetry.events':               '/hmotion/etd/telemetry',
    'safety.zone_monitor':            '/hmotion/safety/zone',
    'workflow.job_context':           '/hmotion/workflow/job',
    'vision.weld_inspection':         '/hmotion/vision/weld_inspection',
}

_DEFAULT_MOCK_STATE: Dict[str, Any] = {
    'perception.seam_tracker': {
        'confidence': 0.95, 'offset_mm': 0.3, 'seam_detected': True,
    },
    'state.safety_state': {
        'human_in_forbidden_zone': False, 'arc_zone_clear': True,
        'estop_active': False, 'collision_detected': False,
    },
    'state.arm_state': {
        'joint_positions': [0.0] * 6, 'in_motion': False, 'at_target': True,
    },
    'state.wrist_state': {
        'wrist_angle_deg': 0.0, 'contact_active': False,
    },
    'force_control.contact_feedback': {
        'normal_force_n': 5.0, 'tangential_force_n': 1.2,
    },
    'vision.weld_inspection': {
        'pass': True, 'defects': [], 'bead_width_mm': 4.8,
    },
    'welding.arc_monitor': {
        'arc_on': False, 'actual_amperage_a': 0.0, 'actual_voltage_v': 0.0,
    },
    'workflow.job_context': {
        'job_id': 'mock-job-001', 'operator_id': 'etd-test',
    },
    'safety.zone_monitor': {
        'zones_clear': True, 'nearest_person_m': 3.5,
    },
}


class HyundaiWIAAdapter(ETDMiddleware):
    """ETD middleware adapter for the Hyundai WIA H-Motion welding cobot.

    Parameters
    ----------
    dry_run:
        When True (default), reads come from an internal mock-state table and
        publishes are appended to ``self.published``. No ROS 2 connection is
        attempted — safe to use in CI and tests.
    telemetry_sink:
        Optional TelemetrySink to receive ``telemetry.events`` publishes in
        addition to the normal publish path. Defaults to NullSink.
    """

    required_topics: List[str] = [
        'perception.seam_tracker',
        'state.safety_state',
        'command.skill_intent',
        'telemetry.events',
        'welding.torch_control',
    ]

    def __init__(
        self,
        dry_run: bool = True,
        telemetry_sink: Optional[TelemetrySink] = None,
    ) -> None:
        self._dry_run = dry_run
        self._mock: Dict[str, Any] = {k: dict(v) for k, v in _DEFAULT_MOCK_STATE.items()}
        self.published: List[Dict[str, Any]] = []
        self._sink: TelemetrySink = telemetry_sink or NullSink()
        self._ros2_node = None
        if not dry_run:
            self._ros2_node = self._init_ros2()

    # ── ETDMiddleware interface ───────────────────────────────────────────────

    def read(self, topic: str) -> Dict[str, Any]:
        """Return the latest value for *topic*.

        In dry_run mode returns from the mock-state table.
        In live mode reads from the H-Motion ROS 2 topic.
        """
        if self._dry_run:
            return dict(self._mock.get(topic, {}))
        ros_topic = _ETD_TO_HMOTION.get(topic, topic)
        return self._ros2_read(ros_topic)

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Send *message* to *topic*.

        If *topic* is ``telemetry.events`` the event is also forwarded to the
        configured TelemetrySink so it can be streamed to file / MQTT / bus.
        """
        if topic == 'telemetry.events':
            event_name = message.get('event', topic)
            self._sink.emit(event_name, {k: v for k, v in message.items() if k != 'event'})

        if self._dry_run:
            self.published.append({'topic': topic, 'message': message, 'ts': time.time()})
            return
        ros_topic = _ETD_TO_HMOTION.get(topic, topic)
        self._ros2_publish(ros_topic, message)

    def validate(self) -> None:
        """Pass in dry_run mode; check ROS 2 node is live in live mode."""
        if not self._dry_run and self._ros2_node is None:
            raise RuntimeError(
                "HyundaiWIAAdapter: ROS 2 node not initialized. "
                "Ensure rclpy is installed and the workspace is sourced."
            )

    # ── Utility helpers ───────────────────────────────────────────────────────

    def inject_state(self, topic: str, patch: Dict[str, Any]) -> None:
        """Merge *patch* into the mock state for *topic*.

        Useful in tests and simulation to trigger safety events::

            adapter.inject_state('state.safety_state',
                                 {'human_in_forbidden_zone': True})
        """
        self._mock[topic] = {**self._mock.get(topic, {}), **patch}

    def topic_for(self, etd_topic: str) -> str:
        """Return the H-Motion ROS 2 topic name for an ETD service topic."""
        return _ETD_TO_HMOTION.get(etd_topic, etd_topic)

    # ── ROS 2 stubs (override with real rclpy logic for live integration) ─────

    def _init_ros2(self):
        try:
            import rclpy  # type: ignore[import]
            rclpy.init()
            return rclpy.create_node('etd_hyundai_wia_adapter')
        except ImportError:
            raise RuntimeError(
                "rclpy not found. Install ROS 2 Humble and source the workspace, "
                "or use HyundaiWIAAdapter(dry_run=True)."
            )

    def _ros2_read(self, ros_topic: str) -> Dict[str, Any]:
        """Read from a live ROS 2 topic (requires real rclpy subscriber logic)."""
        raise NotImplementedError(
            f"Live ROS 2 read not implemented for {ros_topic}. "
            "Override _ros2_read() with rclpy subscriber / service call logic."
        )

    def _ros2_publish(self, ros_topic: str, message: Dict[str, Any]) -> None:
        """Publish to a live ROS 2 topic (requires real rclpy publisher logic)."""
        raise NotImplementedError(
            f"Live ROS 2 publish not implemented for {ros_topic}. "
            "Override _ros2_publish() with rclpy publisher logic."
        )
