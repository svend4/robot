"""Tests for HyundaiMobEDAdapter and HyundaiExoAdapter."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter
from adapters.hyundai_mobed_adapter import HyundaiMobEDAdapter, _ETD_TO_HRISE
from adapters.hyundai_exo_adapter import HyundaiExoAdapter, _ETD_TO_HMEX
from adapters.telemetry_sink import FileSink, NullSink


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_skill(skill_dir: str):
    path = ROOT / 'examples' / skill_dir / 'policies' / 'chs_adapter.py'
    mod_name = skill_dir.replace('.', '_') + '_adapter'
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── HyundaiMobEDAdapter ───────────────────────────────────────────────────────

class TestHyundaiMobEDAdapter:
    def test_is_etd_middleware_subclass(self):
        assert issubclass(HyundaiMobEDAdapter, ETDMiddleware)

    def test_instantiates_without_ros2(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        assert adapter._dry_run is True

    def test_validate_passes_dry_run(self):
        HyundaiMobEDAdapter(dry_run=True).validate()

    def test_load_middleware_adapter_accepts_it(self):
        mw = load_middleware_adapter(HyundaiMobEDAdapter(dry_run=True))
        assert isinstance(mw, HyundaiMobEDAdapter)

    def test_read_safety_state(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        s = adapter.read('state.safety_state')
        assert s['human_in_forbidden_zone'] is False
        assert 'estop_active' in s

    def test_read_robot_pose(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        pose = adapter.read('state.robot_pose')
        assert 'x_m' in pose and 'y_m' in pose
        assert 'heading_deg' in pose

    def test_read_unknown_topic_returns_empty(self):
        assert HyundaiMobEDAdapter(dry_run=True).read('unknown.xyz') == {}

    def test_read_returns_copy(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        s = adapter.read('state.safety_state')
        s['human_in_forbidden_zone'] = True
        assert adapter.read('state.safety_state')['human_in_forbidden_zone'] is False

    def test_publish_records_to_list(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        adapter.publish('command.skill_intent', {'type': 'skill_intent'})
        assert len(adapter.published) == 1
        assert adapter.published[0]['topic'] == 'command.skill_intent'

    def test_inject_state_updates_mock(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        assert adapter.read('state.safety_state')['human_in_forbidden_zone'] is True

    def test_inject_state_merges_preserves_other_keys(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'new_key': 42})
        s = adapter.read('state.safety_state')
        assert s['new_key'] == 42
        assert 'estop_active' in s

    def test_set_pose_updates_mock(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        adapter.set_pose(5.0, 3.0, heading_deg=90.0)
        pose = adapter.read('state.robot_pose')
        assert pose['x_m'] == 5.0
        assert pose['y_m'] == 3.0
        assert pose['heading_deg'] == 90.0

    def test_initial_pose_sets_at_construction(self):
        adapter = HyundaiMobEDAdapter(dry_run=True, initial_pose={'x_m': 10.0, 'y_m': -2.0})
        pose = adapter.read('state.robot_pose')
        assert pose['x_m'] == 10.0
        assert pose['y_m'] == -2.0

    def test_topic_for_known_topic(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        assert adapter.topic_for('state.robot_pose') == '/hrise/localization/pose'
        assert adapter.topic_for('command.skill_intent') == '/hrise/skill/intent'

    def test_topic_for_unknown_returns_original(self):
        assert HyundaiMobEDAdapter(dry_run=True).topic_for('unknown.t') == 'unknown.t'

    def test_all_required_topics_in_mapping(self):
        for t in HyundaiMobEDAdapter.required_topics:
            assert t in _ETD_TO_HRISE, f'{t} not in H-Rise topic mapping'

    def test_telemetry_forwarded_to_sink(self):
        captured = []
        from adapters.telemetry_sink import TelemetrySink

        class _Cap(TelemetrySink):
            def emit(self, event, payload): captured.append(event)

        adapter = HyundaiMobEDAdapter(dry_run=True, telemetry_sink=_Cap())
        adapter.publish('telemetry.events', {'event': 'skill.started'})
        assert 'skill.started' in captured

    def test_live_mode_raises_without_rclpy(self):
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {'rclpy': None}):
            with pytest.raises((RuntimeError, ImportError)):
                HyundaiMobEDAdapter(dry_run=False)

    def test_validate_raises_when_ros2_node_none(self):
        adapter = HyundaiMobEDAdapter.__new__(HyundaiMobEDAdapter)
        adapter._dry_run = False
        adapter._ros2_node = None
        with pytest.raises(RuntimeError, match='ROS 2 node'):
            adapter.validate()


class TestMobEDSkillIntegration:
    def _run_transport(self, adapter, profile='standard_carry'):
        mod = _load_skill('etd.hyundai.mobed_transport')
        return mod.run({'chsProfile': profile}, middleware=adapter)

    def test_standard_carry_completes(self):
        result = self._run_transport(HyundaiMobEDAdapter(dry_run=True))
        assert result['status'] == 'completed'

    def test_abort_on_human_in_forbidden_zone(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        result = self._run_transport(adapter)
        assert result['status'] == 'aborted'
        assert result['reason'] == 'human_in_forbidden_zone'

    def test_events_recorded_in_published(self):
        adapter = HyundaiMobEDAdapter(dry_run=True)
        self._run_transport(adapter)
        events = [p['message'].get('event') for p in adapter.published
                  if p['topic'] == 'telemetry.events']
        assert 'skill.started' in events
        assert 'skill.completed' in events

    def test_telemetry_sink_receives_lifecycle_events(self, tmp_path):
        log = tmp_path / 'mobed.jsonl'
        adapter = HyundaiMobEDAdapter(dry_run=True, telemetry_sink=FileSink(log))
        self._run_transport(adapter)
        events = [json.loads(l)['event'] for l in log.read_text().strip().splitlines()]
        assert 'skill.started' in events
        assert 'skill.completed' in events


# ── HyundaiExoAdapter ─────────────────────────────────────────────────────────

class TestHyundaiExoAdapter:
    def test_is_etd_middleware_subclass(self):
        assert issubclass(HyundaiExoAdapter, ETDMiddleware)

    def test_instantiates_without_ros2(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        assert adapter._dry_run is True

    def test_validate_passes_dry_run(self):
        HyundaiExoAdapter(dry_run=True).validate()

    def test_load_middleware_adapter_accepts_it(self):
        mw = load_middleware_adapter(HyundaiExoAdapter(dry_run=True))
        assert isinstance(mw, HyundaiExoAdapter)

    def test_read_safety_state(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        s = adapter.read('state.safety_state')
        assert s['human_in_forbidden_zone'] is False

    def test_read_exo_joint_state(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        j = adapter.read('state.exo_joint_state')
        assert 'lumbar_angle_deg' in j
        assert 'joint_torques_nm' in j

    def test_read_fatigue_monitor(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        f = adapter.read('state.fatigue_monitor')
        assert 'fatigue_pct' in f

    def test_read_intent_detector(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        intent = adapter.read('perception.intent_detector')
        assert 'mode' in intent
        assert intent['confidence'] > 0

    def test_read_unknown_topic_returns_empty(self):
        assert HyundaiExoAdapter(dry_run=True).read('unknown.xyz') == {}

    def test_publish_records_to_list(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        adapter.publish('command.skill_intent', {'type': 'skill_intent'})
        assert len(adapter.published) == 1

    def test_inject_state_updates_mock(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        assert adapter.read('state.safety_state')['human_in_forbidden_zone'] is True

    def test_set_fatigue_updates_mock(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        adapter.set_fatigue(75)
        assert adapter.read('state.fatigue_monitor')['fatigue_pct'] == 75

    def test_set_intent_updates_mock(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        adapter.set_intent('overhead', confidence=0.88)
        intent = adapter.read('perception.intent_detector')
        assert intent['mode'] == 'overhead'
        assert intent['confidence'] == 0.88

    def test_simulate_fatigue_increments_each_read(self):
        adapter = HyundaiExoAdapter(dry_run=True, simulate_fatigue=True)
        f1 = adapter.read('state.fatigue_monitor')['fatigue_pct']
        f2 = adapter.read('state.fatigue_monitor')['fatigue_pct']
        assert f2 > f1

    def test_simulate_fatigue_caps_at_100(self):
        adapter = HyundaiExoAdapter(dry_run=True, simulate_fatigue=True)
        for _ in range(25):  # 25 * 5 = 125 > 100
            adapter.read('state.fatigue_monitor')
        assert adapter.read('state.fatigue_monitor')['fatigue_pct'] == 100

    def test_topic_for_known_topic(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        assert adapter.topic_for('state.exo_joint_state') == '/hmex/joints/state'
        assert adapter.topic_for('perception.intent_detector') == '/hmex/intent/detected'

    def test_topic_for_unknown_returns_original(self):
        assert HyundaiExoAdapter(dry_run=True).topic_for('unknown.t') == 'unknown.t'

    def test_all_required_topics_in_mapping(self):
        for t in HyundaiExoAdapter.required_topics:
            assert t in _ETD_TO_HMEX, f'{t} not in H-MEX topic mapping'

    def test_telemetry_forwarded_to_sink(self):
        captured = []
        from adapters.telemetry_sink import TelemetrySink

        class _Cap(TelemetrySink):
            def emit(self, event, payload): captured.append(event)

        adapter = HyundaiExoAdapter(dry_run=True, telemetry_sink=_Cap())
        adapter.publish('telemetry.events', {'event': 'skill.started'})
        assert 'skill.started' in captured

    def test_live_mode_raises_without_rclpy(self):
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {'rclpy': None}):
            with pytest.raises((RuntimeError, ImportError)):
                HyundaiExoAdapter(dry_run=False)

    def test_validate_raises_when_ros2_node_none(self):
        adapter = HyundaiExoAdapter.__new__(HyundaiExoAdapter)
        adapter._dry_run = False
        adapter._ros2_node = None
        with pytest.raises(RuntimeError, match='ROS 2 node'):
            adapter.validate()


class TestExoSkillIntegration:
    def _run_exo(self, adapter, profile='lumbar_support'):
        mod = _load_skill('etd.hyundai.vest_exoskeleton')
        return mod.run({'chsProfile': profile}, middleware=adapter)

    def test_lumbar_support_completes(self):
        result = self._run_exo(HyundaiExoAdapter(dry_run=True))
        assert result['status'] == 'completed'

    def test_abort_on_human_in_forbidden_zone(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        result = self._run_exo(adapter)
        assert result['status'] == 'aborted'

    def test_events_recorded_in_published(self):
        adapter = HyundaiExoAdapter(dry_run=True)
        self._run_exo(adapter)
        events = [p['message'].get('event') for p in adapter.published
                  if p['topic'] == 'telemetry.events']
        assert 'skill.started' in events
        assert 'skill.completed' in events

    def test_telemetry_sink_receives_lifecycle_events(self, tmp_path):
        log = tmp_path / 'exo.jsonl'
        adapter = HyundaiExoAdapter(dry_run=True, telemetry_sink=FileSink(log))
        self._run_exo(adapter)
        events = [json.loads(l)['event'] for l in log.read_text().strip().splitlines()]
        assert 'skill.started' in events
        assert 'skill.completed' in events
