"""Tests for AtlasAdapter, adapter registry, and skill_action_server wiring."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter
from adapters.atlas_adapter import AtlasAdapter, _ETD_TO_ORBIT
from adapters.registry import (
    NullMiddleware,
    get_adapter_class,
    get_adapter_for_skill,
    list_registrations,
    register_adapter,
)
from adapters.telemetry_sink import FileSink, NullSink


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_atlas_skill():
    path = ROOT / 'examples' / 'etd.atlas.humanoid_walkfetch' / 'policies' / 'chs_adapter.py'
    mod_name = 'etd_atlas_humanoid_walkfetch_adapter'
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── AtlasAdapter ──────────────────────────────────────────────────────────────

class TestAtlasAdapter:
    def test_is_etd_middleware_subclass(self):
        assert issubclass(AtlasAdapter, ETDMiddleware)

    def test_instantiates_without_ros2(self):
        adapter = AtlasAdapter(dry_run=True)
        assert adapter._dry_run is True

    def test_validate_passes_dry_run(self):
        AtlasAdapter(dry_run=True).validate()

    def test_load_middleware_adapter_accepts_it(self):
        mw = load_middleware_adapter(AtlasAdapter(dry_run=True))
        assert isinstance(mw, AtlasAdapter)

    def test_read_safety_state(self):
        adapter = AtlasAdapter(dry_run=True)
        s = adapter.read('state.safety_state')
        assert s['human_in_forbidden_zone'] is False
        assert 'balance_fault' in s

    def test_read_balance_state(self):
        adapter = AtlasAdapter(dry_run=True)
        b = adapter.read('state.balance_state')
        assert b['stable'] is True
        assert 'balance_score' in b

    def test_read_scene_map(self):
        adapter = AtlasAdapter(dry_run=True)
        m = adapter.read('perception.scene_map')
        assert m['map_ready'] is True
        assert m['target_visible'] is True

    def test_read_object_pose(self):
        adapter = AtlasAdapter(dry_run=True)
        p = adapter.read('perception.object_pose')
        assert 'x_m' in p and 'confidence' in p

    def test_read_unknown_topic_returns_empty(self):
        assert AtlasAdapter(dry_run=True).read('unknown.xyz') == {}

    def test_read_returns_copy(self):
        adapter = AtlasAdapter(dry_run=True)
        s = adapter.read('state.safety_state')
        s['human_in_forbidden_zone'] = True
        assert adapter.read('state.safety_state')['human_in_forbidden_zone'] is False

    def test_publish_records_to_list(self):
        adapter = AtlasAdapter(dry_run=True)
        adapter.publish('command.skill_intent', {'type': 'skill_intent'})
        assert len(adapter.published) == 1
        assert adapter.published[0]['topic'] == 'command.skill_intent'

    def test_inject_state_updates_mock(self):
        adapter = AtlasAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        assert adapter.read('state.safety_state')['human_in_forbidden_zone'] is True

    def test_inject_state_preserves_other_keys(self):
        adapter = AtlasAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'new_key': 'x'})
        assert 'human_in_forbidden_zone' in adapter.read('state.safety_state')

    def test_set_balance(self):
        adapter = AtlasAdapter(dry_run=True)
        adapter.set_balance(stable=False, balance_score=0.3)
        b = adapter.read('state.balance_state')
        assert b['stable'] is False
        assert b['balance_score'] == 0.3

    def test_set_object_pose(self):
        adapter = AtlasAdapter(dry_run=True)
        adapter.set_object_pose(2.0, 1.0, 0.9, confidence=0.95)
        p = adapter.read('perception.object_pose')
        assert p['x_m'] == 2.0
        assert p['confidence'] == 0.95
        assert adapter.read('perception.scene_map')['target_visible'] is True

    def test_topic_for_known(self):
        adapter = AtlasAdapter(dry_run=True)
        assert adapter.topic_for('command.skill_intent') == '/orbit/skill/intent'
        assert adapter.topic_for('state.balance_state') == '/atlas/body/balance_state'

    def test_topic_for_unknown_returns_original(self):
        assert AtlasAdapter(dry_run=True).topic_for('x.y') == 'x.y'

    def test_all_required_topics_in_mapping(self):
        for t in AtlasAdapter.required_topics:
            assert t in _ETD_TO_ORBIT, f'{t} not in Orbit topic mapping'

    def test_telemetry_forwarded_to_sink(self):
        captured = []
        from adapters.telemetry_sink import TelemetrySink

        class _Cap(TelemetrySink):
            def emit(self, event, payload): captured.append(event)

        adapter = AtlasAdapter(dry_run=True, telemetry_sink=_Cap())
        adapter.publish('telemetry.events', {'event': 'skill.started'})
        assert 'skill.started' in captured

    def test_orbit_endpoint_stored(self):
        adapter = AtlasAdapter(dry_run=True, orbit_endpoint='http://my-orbit:5001')
        assert adapter._orbit_endpoint == 'http://my-orbit:5001'

    def test_live_mode_raises_without_rclpy(self):
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {'rclpy': None}):
            with pytest.raises((RuntimeError, ImportError)):
                AtlasAdapter(dry_run=False)

    def test_validate_raises_when_ros2_node_none(self):
        adapter = AtlasAdapter.__new__(AtlasAdapter)
        adapter._dry_run = False
        adapter._ros2_node = None
        with pytest.raises(RuntimeError, match='ROS 2 node'):
            adapter.validate()


class TestAtlasSkillIntegration:
    def _run_fetch(self, adapter, profile='sequencing_carry'):
        mod = _load_atlas_skill()
        return mod.run({'chsProfile': profile}, middleware=adapter)

    def test_sequencing_carry_completes(self):
        result = self._run_fetch(AtlasAdapter(dry_run=True))
        assert result['status'] == 'completed'

    def test_abort_on_human_in_forbidden_zone(self):
        adapter = AtlasAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        result = self._run_fetch(adapter)
        assert result['status'] == 'aborted'

    def test_events_include_skill_lifecycle(self):
        adapter = AtlasAdapter(dry_run=True)
        self._run_fetch(adapter)
        events = [p['message'].get('event') for p in adapter.published
                  if p['topic'] == 'telemetry.events']
        assert 'skill.started' in events
        assert 'skill.completed' in events

    def test_file_sink_captures_events(self, tmp_path):
        log = tmp_path / 'atlas.jsonl'
        adapter = AtlasAdapter(dry_run=True, telemetry_sink=FileSink(log))
        self._run_fetch(adapter)
        events = [json.loads(l)['event'] for l in log.read_text().strip().splitlines()]
        assert 'skill.started' in events
        assert 'skill.completed' in events


# ── Adapter Registry ──────────────────────────────────────────────────────────

class TestAdapterRegistry:
    def test_get_adapter_class_hyundai_wia(self):
        from adapters.hyundai_wia_adapter import HyundaiWIAAdapter
        assert get_adapter_class('etd.hyundai.wia_welding') is HyundaiWIAAdapter

    def test_get_adapter_class_hyundai_mobed(self):
        from adapters.hyundai_mobed_adapter import HyundaiMobEDAdapter
        assert get_adapter_class('etd.hyundai.mobed_transport') is HyundaiMobEDAdapter

    def test_get_adapter_class_hyundai_exo(self):
        from adapters.hyundai_exo_adapter import HyundaiExoAdapter
        assert get_adapter_class('etd.hyundai.vest_exoskeleton') is HyundaiExoAdapter

    def test_get_adapter_class_atlas_prefix(self):
        assert get_adapter_class('etd.atlas.humanoid_walkfetch') is AtlasAdapter

    def test_get_adapter_class_unknown_returns_null(self):
        assert get_adapter_class('etd.pickplace.basic') is NullMiddleware

    def test_get_adapter_class_unknown_prefix_returns_null(self):
        assert get_adapter_class('com.unknown.skill') is NullMiddleware

    def test_get_adapter_for_skill_returns_instance(self):
        adapter = get_adapter_for_skill('etd.hyundai.wia_welding', dry_run=True)
        from adapters.hyundai_wia_adapter import HyundaiWIAAdapter
        assert isinstance(adapter, HyundaiWIAAdapter)

    def test_get_adapter_for_skill_null_middleware(self):
        adapter = get_adapter_for_skill('etd.pickplace.basic')
        assert isinstance(adapter, NullMiddleware)

    def test_get_adapter_for_skill_passes_dry_run(self):
        adapter = get_adapter_for_skill('etd.atlas.humanoid_walkfetch', dry_run=True)
        assert isinstance(adapter, AtlasAdapter)
        assert adapter._dry_run is True

    def test_get_adapter_for_skill_passes_telemetry_sink(self):
        sink = NullSink()
        adapter = get_adapter_for_skill(
            'etd.hyundai.wia_welding', dry_run=True, telemetry_sink=sink
        )
        assert adapter._sink is sink

    def test_register_adapter_custom_prefix(self):
        class _TestAdapter(ETDMiddleware):
            def read(self, topic): return {}
            def publish(self, topic, msg): pass

        register_adapter('test.custom.prefix', _TestAdapter)
        assert get_adapter_class('test.custom.prefix.skill') is _TestAdapter

    def test_register_adapter_exact_match(self):
        class _ExactAdapter(ETDMiddleware):
            def read(self, topic): return {}
            def publish(self, topic, msg): pass

        register_adapter('test.exact.skill', _ExactAdapter, exact=True)
        assert get_adapter_class('test.exact.skill') is _ExactAdapter
        assert get_adapter_class('test.exact.skill.sub') is NullMiddleware

    def test_register_adapter_rejects_non_etd_middleware(self):
        with pytest.raises(TypeError, match='ETDMiddleware'):
            register_adapter('test.bad', object)  # type: ignore[arg-type]

    def test_list_registrations_contains_builtins(self):
        regs = list_registrations()
        keys = [r['key'] for r in regs]
        assert 'etd.hyundai.wia_welding' in keys
        assert 'etd.hyundai.mobed_transport' in keys
        assert 'etd.hyundai.vest_exoskeleton' in keys
        assert 'etd.atlas' in keys

    def test_null_middleware_read_returns_empty(self):
        mw = NullMiddleware()
        assert mw.read('state.safety_state') == {}

    def test_null_middleware_publish_no_op(self):
        NullMiddleware().publish('command.skill_intent', {'x': 1})  # must not raise


# ── skill_action_server wiring ─────────────────────────────────────────────────

class TestSkillActionServerRegistryWiring:
    def _make_server(self, skill_id):
        bridge_path = (
            ROOT / 'integrations' / 'ros2' / 'etd_ros2_bridge'
            / 'etd_ros2_bridge' / 'skill_action_server.py'
        )
        mod_name = 'etd_ros2_bridge_server'
        spec = importlib.util.spec_from_file_location(mod_name, bridge_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod.ETDSkillActionServer(skill_id)

    def test_resolve_middleware_returns_wia_for_wia_skill(self):
        server = self._make_server('etd.hyundai.wia_welding')
        mw = server._resolve_middleware(dry_run=True)
        from adapters.hyundai_wia_adapter import HyundaiWIAAdapter
        assert isinstance(mw, HyundaiWIAAdapter)

    def test_resolve_middleware_returns_atlas_for_atlas_skill(self):
        server = self._make_server('etd.atlas.humanoid_walkfetch')
        mw = server._resolve_middleware(dry_run=True)
        assert isinstance(mw, AtlasAdapter)

    def test_resolve_middleware_returns_null_for_generic(self):
        server = self._make_server('etd.pickplace.basic')
        mw = server._resolve_middleware(dry_run=True)
        assert isinstance(mw, NullMiddleware)

    def test_execute_goal_uses_auto_middleware(self):
        server = self._make_server('etd.hyundai.wia_welding')
        result = server.execute_goal({'chsProfile': 'tack_weld'})
        assert result['status'] == 'completed'

    def test_execute_goal_explicit_middleware_takes_precedence(self):
        from adapters.hyundai_wia_adapter import HyundaiWIAAdapter
        explicit = HyundaiWIAAdapter(dry_run=True)
        explicit.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        server = self._make_server('etd.hyundai.wia_welding')
        result = server.execute_goal({'chsProfile': 'tack_weld'}, middleware=explicit)
        assert result['status'] == 'aborted'
