"""Hyundai VEX / H-MEX exoskeleton middleware adapter.

Maps ETD service topics to the H-MEX wearable-assist ROS 2 topic namespace.

In ``dry_run=True`` mode (default) all reads return mock responses and
publishes are appended to ``adapter.published``.  The adapter simulates
fatigue progression when ``simulate_fatigue=True`` so tests can exercise
the fatigue-threshold abort path without hardware.

ETD → H-MEX topic mapping::

    ETD service topic              H-MEX ROS 2 topic
    ──────────────────────────────────────────────────────────────
    state.safety_state             /hmex/safety/state
    state.exo_joint_state          /hmex/joints/state
    state.fatigue_monitor          /hmex/biosignal/fatigue
    perception.intent_detector     /hmex/intent/detected
    force_control.torque_assist    /hmex/actuator/torque_cmd
    command.skill_intent           /hmex/skill/intent
    assist.mode_switched           /hmex/assist/mode
    assist.torque_applied          /hmex/actuator/torque_applied
    assist.fatigue_threshold_reached /hmex/biosignal/fatigue_alert
    assist.intent_detected         /hmex/intent/event
    assist.lumbar_mode_entered     /hmex/assist/lumbar_mode
    assist.overhead_mode_entered   /hmex/assist/overhead_mode
    telemetry.events               /hmex/etd/telemetry
    primitive.entered              /hmex/skill/primitive_entered
    primitive.exited               /hmex/skill/primitive_exited
    skill.started                  /hmex/skill/started
    skill.completed                /hmex/skill/completed
    skill.aborted                  /hmex/skill/aborted
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter  # noqa: E402
from adapters.telemetry_sink import NullSink, TelemetrySink  # noqa: E402

_ETD_TO_HMEX: Dict[str, str] = {
    'state.safety_state':              '/hmex/safety/state',
    'state.exo_joint_state':           '/hmex/joints/state',
    'state.fatigue_monitor':           '/hmex/biosignal/fatigue',
    'perception.intent_detector':      '/hmex/intent/detected',
    'force_control.torque_assist':     '/hmex/actuator/torque_cmd',
    'command.skill_intent':            '/hmex/skill/intent',
    'assist.mode_switched':            '/hmex/assist/mode',
    'assist.torque_applied':           '/hmex/actuator/torque_applied',
    'assist.fatigue_threshold_reached': '/hmex/biosignal/fatigue_alert',
    'assist.intent_detected':          '/hmex/intent/event',
    'assist.lumbar_mode_entered':      '/hmex/assist/lumbar_mode',
    'assist.overhead_mode_entered':    '/hmex/assist/overhead_mode',
    'telemetry.events':                '/hmex/etd/telemetry',
    'primitive.entered':               '/hmex/skill/primitive_entered',
    'primitive.exited':                '/hmex/skill/primitive_exited',
    'skill.started':                   '/hmex/skill/started',
    'skill.completed':                 '/hmex/skill/completed',
    'skill.aborted':                   '/hmex/skill/aborted',
}

_DEFAULT_MOCK_STATE: Dict[str, Any] = {
    'state.safety_state': {
        'human_in_forbidden_zone': False,
        'estop_active': False,
        'overload_detected': False,
    },
    'state.exo_joint_state': {
        'lumbar_angle_deg': 0.0,
        'shoulder_angle_deg': 0.0,
        'joint_torques_nm': [0.0, 0.0, 0.0, 0.0],
        'assist_active': False,
    },
    'state.fatigue_monitor': {
        'fatigue_pct': 0,
        'heart_rate_bpm': 72,
        'emg_rms_normalized': 0.15,
    },
    'perception.intent_detector': {
        'mode': 'lumbar',
        'confidence': 0.92,
        'intent_detected': True,
    },
}


class HyundaiExoAdapter(ETDMiddleware):
    """ETD middleware adapter for the Hyundai VEX / H-MEX wearable exoskeleton.

    Parameters
    ----------
    dry_run:
        When True (default), reads from mock state; publishes recorded to
        ``self.published``. No ROS 2 connection attempted.
    telemetry_sink:
        Optional sink for ``telemetry.events`` publishes. Defaults to NullSink.
    simulate_fatigue:
        When True, ``state.fatigue_monitor`` returns progressively higher
        ``fatigue_pct`` on each read (increments by 5 per call). Allows
        tests to trigger the fatigue-threshold abort without hardware.
    """

    required_topics: List[str] = [
        'state.safety_state',
        'state.exo_joint_state',
        'state.fatigue_monitor',
        'perception.intent_detector',
        'command.skill_intent',
        'telemetry.events',
    ]

    def __init__(
        self,
        dry_run: bool = True,
        telemetry_sink: Optional[TelemetrySink] = None,
        simulate_fatigue: bool = False,
    ) -> None:
        self._dry_run = dry_run
        self._mock: Dict[str, Any] = {k: dict(v) for k, v in _DEFAULT_MOCK_STATE.items()}
        self.published: List[Dict[str, Any]] = []
        self._sink: TelemetrySink = telemetry_sink or NullSink()
        self._simulate_fatigue = simulate_fatigue
        self._fatigue_read_count = 0
        self._ros2_node = None
        if not dry_run:
            self._ros2_node = self._init_ros2()

    # ── ETDMiddleware interface ───────────────────────────────────────────────

    def read(self, topic: str) -> Dict[str, Any]:
        if self._dry_run:
            if topic == 'state.fatigue_monitor' and self._simulate_fatigue:
                self._fatigue_read_count += 1
                fatigue_pct = min(100, self._fatigue_read_count * 5)
                return {**self._mock.get(topic, {}), 'fatigue_pct': fatigue_pct}
            return dict(self._mock.get(topic, {}))
        ros_topic = _ETD_TO_HMEX.get(topic, topic)
        return self._ros2_read(ros_topic)

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if topic == 'telemetry.events':
            event_name = message.get('event', topic)
            self._sink.emit(event_name, {k: v for k, v in message.items() if k != 'event'})
        if self._dry_run:
            self.published.append({'topic': topic, 'message': message, 'ts': time.time()})
            return
        ros_topic = _ETD_TO_HMEX.get(topic, topic)
        self._ros2_publish(ros_topic, message)

    def validate(self) -> None:
        if not self._dry_run and self._ros2_node is None:
            raise RuntimeError(
                "HyundaiExoAdapter: ROS 2 node not initialized. "
                "Ensure rclpy is installed and the workspace is sourced."
            )

    # ── Utility helpers ───────────────────────────────────────────────────────

    def inject_state(self, topic: str, patch: Dict[str, Any]) -> None:
        """Merge *patch* into the mock state for *topic*."""
        self._mock[topic] = {**self._mock.get(topic, {}), **patch}

    def set_fatigue(self, fatigue_pct: int) -> None:
        """Directly set the mock fatigue level (0–100)."""
        self.inject_state('state.fatigue_monitor', {'fatigue_pct': fatigue_pct})

    def set_intent(self, mode: str, confidence: float = 0.92) -> None:
        """Set the mock intent detector output."""
        self.inject_state('perception.intent_detector', {
            'mode': mode, 'confidence': confidence, 'intent_detected': True,
        })

    def topic_for(self, etd_topic: str) -> str:
        """Return the H-MEX ROS 2 topic for an ETD service topic."""
        return _ETD_TO_HMEX.get(etd_topic, etd_topic)

    # ── ROS 2 stubs ───────────────────────────────────────────────────────────

    def _init_ros2(self):
        try:
            import rclpy  # type: ignore[import]
            rclpy.init()
            return rclpy.create_node('etd_hyundai_exo_adapter')
        except ImportError:
            raise RuntimeError(
                "rclpy not found. Install ROS 2 Humble and source the workspace, "
                "or use HyundaiExoAdapter(dry_run=True)."
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
