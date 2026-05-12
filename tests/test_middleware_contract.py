"""Tests for ETDMiddleware contract, HyundaiWIAAdapter, and TelemetrySink."""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from etd_middleware_contract import ETDMiddleware, load_middleware_adapter
from adapters.telemetry_sink import (
    ConsoleSink, FileSink, MultiSink, NullSink, TelemetrySink,
)
from adapters.hyundai_wia_adapter import HyundaiWIAAdapter, _ETD_TO_HMOTION


# ── Helpers ───────────────────────────────────────────────────────────────────

class _GoodAdapter(ETDMiddleware):
    required_topics = ['state.safety_state', 'command.skill_intent']
    def read(self, topic):
        return {'ok': True}
    def publish(self, topic, msg):
        pass


class _MissingTopicAdapter(ETDMiddleware):
    required_topics = ['state.safety_state', 'nonexistent.topic']
    def read(self, topic):
        return {}
    def publish(self, topic, msg):
        pass
    def _is_topic_available(self, topic):
        return topic == 'state.safety_state'


# ── ETDMiddleware contract ────────────────────────────────────────────────────

class TestETDMiddlewareContract:
    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            ETDMiddleware()

    def test_concrete_subclass_instantiates(self):
        adapter = _GoodAdapter()
        assert isinstance(adapter, ETDMiddleware)

    def test_read_and_publish_callable(self):
        adapter = _GoodAdapter()
        assert adapter.read('state.safety_state') == {'ok': True}
        adapter.publish('command.skill_intent', {'type': 'skill_intent'})

    def test_validate_passes_when_topics_available(self):
        adapter = _GoodAdapter()
        adapter.validate()  # must not raise

    def test_validate_raises_for_unavailable_topics(self):
        adapter = _MissingTopicAdapter()
        with pytest.raises(RuntimeError, match='nonexistent.topic'):
            adapter.validate()

    def test_default_is_topic_available_returns_true(self):
        adapter = _GoodAdapter()
        assert adapter._is_topic_available('any.topic') is True

    def test_required_topics_default_empty(self):
        class _MinimalAdapter(ETDMiddleware):
            def read(self, topic): return {}
            def publish(self, topic, msg): pass
        assert _MinimalAdapter.required_topics == []


# ── load_middleware_adapter ────────────────────────────────────────────────────

class TestLoadMiddlewareAdapter:
    def test_returns_same_adapter(self):
        adapter = _GoodAdapter()
        result = load_middleware_adapter(adapter)
        assert result is adapter

    def test_raises_type_error_for_non_middleware(self):
        with pytest.raises(TypeError, match='ETDMiddleware'):
            load_middleware_adapter(object())  # type: ignore[arg-type]

    def test_raises_runtime_error_for_missing_topics(self):
        with pytest.raises(RuntimeError, match='nonexistent.topic'):
            load_middleware_adapter(_MissingTopicAdapter())

    def test_calls_validate(self):
        called = []
        class _TrackAdapter(ETDMiddleware):
            def read(self, topic): return {}
            def publish(self, topic, msg): pass
            def validate(self): called.append(True)
        load_middleware_adapter(_TrackAdapter())
        assert called == [True]


# ── HyundaiWIAAdapter — dry_run mode ─────────────────────────────────────────

class TestHyundaiWIAAdapterDryRun:
    def test_instantiates_without_ros2(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        assert adapter._dry_run is True

    def test_is_etd_middleware_subclass(self):
        assert issubclass(HyundaiWIAAdapter, ETDMiddleware)

    def test_validate_passes_in_dry_run(self):
        HyundaiWIAAdapter(dry_run=True).validate()  # must not raise

    def test_load_middleware_adapter_accepts_dry_run(self):
        adapter = load_middleware_adapter(HyundaiWIAAdapter(dry_run=True))
        assert isinstance(adapter, HyundaiWIAAdapter)

    def test_read_returns_mock_safety_state(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        state = adapter.read('state.safety_state')
        assert state['human_in_forbidden_zone'] is False
        assert 'estop_active' in state

    def test_read_returns_mock_seam_tracker(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        seam = adapter.read('perception.seam_tracker')
        assert seam['confidence'] > 0
        assert seam['seam_detected'] is True

    def test_read_unknown_topic_returns_empty_dict(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        assert adapter.read('nonexistent.topic') == {}

    def test_read_returns_copy_not_reference(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        s1 = adapter.read('state.safety_state')
        s1['human_in_forbidden_zone'] = True
        s2 = adapter.read('state.safety_state')
        assert s2['human_in_forbidden_zone'] is False

    def test_publish_records_to_published_list(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        adapter.publish('command.skill_intent', {'type': 'skill_intent'})
        assert len(adapter.published) == 1
        assert adapter.published[0]['topic'] == 'command.skill_intent'

    def test_publish_multiple_records_all(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        for i in range(3):
            adapter.publish('telemetry.events', {'event': f'ev{i}'})
        assert len(adapter.published) == 3

    def test_inject_state_updates_mock(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        state = adapter.read('state.safety_state')
        assert state['human_in_forbidden_zone'] is True

    def test_inject_state_merges_not_replaces(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'custom_field': 99})
        state = adapter.read('state.safety_state')
        assert state['custom_field'] == 99
        assert 'human_in_forbidden_zone' in state  # original fields preserved

    def test_inject_state_new_topic(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        adapter.inject_state('custom.topic', {'value': 42})
        assert adapter.read('custom.topic')['value'] == 42

    def test_topic_for_known_etd_topic(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        assert adapter.topic_for('perception.seam_tracker') == '/hmotion/perception/seam_tracker'
        assert adapter.topic_for('state.safety_state') == '/hmotion/safety/state'
        assert adapter.topic_for('command.skill_intent') == '/hmotion/skill/intent'

    def test_topic_for_unknown_returns_original(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        assert adapter.topic_for('unknown.topic') == 'unknown.topic'

    def test_all_required_topics_in_mapping(self):
        for t in HyundaiWIAAdapter.required_topics:
            assert t in _ETD_TO_HMOTION, f'{t} not in topic mapping'

    def test_telemetry_events_forwarded_to_sink(self):
        captured = []

        class _CaptureSink(TelemetrySink):
            def emit(self, event, payload):
                captured.append((event, payload))

        adapter = HyundaiWIAAdapter(dry_run=True, telemetry_sink=_CaptureSink())
        adapter.publish('telemetry.events', {'event': 'skill.started', 'profile': 'standard_seam'})
        assert len(captured) == 1
        assert captured[0][0] == 'skill.started'
        assert captured[0][1]['profile'] == 'standard_seam'

    def test_non_telemetry_publish_not_forwarded_to_sink(self):
        captured = []

        class _CaptureSink(TelemetrySink):
            def emit(self, event, payload):
                captured.append(event)

        adapter = HyundaiWIAAdapter(dry_run=True, telemetry_sink=_CaptureSink())
        adapter.publish('command.skill_intent', {'type': 'skill_intent'})
        assert captured == []


class TestHyundaiWIAAdapterLiveMode:
    def test_live_mode_raises_without_rclpy(self):
        import importlib
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {'rclpy': None}):
            with pytest.raises((RuntimeError, ImportError)):
                HyundaiWIAAdapter(dry_run=False)

    def test_validate_raises_when_ros2_node_none(self):
        adapter = HyundaiWIAAdapter.__new__(HyundaiWIAAdapter)
        adapter._dry_run = False
        adapter._ros2_node = None
        adapter._mock = {}
        adapter.published = []
        from adapters.telemetry_sink import NullSink
        adapter._sink = NullSink()
        with pytest.raises(RuntimeError, match='ROS 2 node'):
            adapter.validate()


# ── TelemetrySink ─────────────────────────────────────────────────────────────

class TestNullSink:
    def test_emit_does_not_raise(self):
        sink = NullSink()
        sink.emit('skill.started', {'x': 1})  # must not raise

    def test_close_does_not_raise(self):
        NullSink().close()


class TestConsoleSink:
    def test_emit_writes_json_to_stdout(self, capsys):
        sink = ConsoleSink()
        sink.emit('skill.started', {'profile': 'standard_seam'})
        out = capsys.readouterr().out
        data = json.loads(out.strip())
        assert data['event'] == 'skill.started'
        assert data['profile'] == 'standard_seam'

    def test_emit_multiple_events(self, capsys):
        sink = ConsoleSink()
        sink.emit('ev1', {})
        sink.emit('ev2', {})
        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 2


class TestFileSink:
    def test_emit_writes_json_lines(self, tmp_path):
        path = tmp_path / 'telemetry.jsonl'
        sink = FileSink(path)
        sink.emit('skill.started', {'profile': 'tack_weld'})
        sink.emit('skill.completed', {'seam_length_mm': 5.0})
        sink.close()

        lines = path.read_text(encoding='utf-8').strip().splitlines()
        assert len(lines) == 2
        d0 = json.loads(lines[0])
        assert d0['event'] == 'skill.started'
        assert d0['profile'] == 'tack_weld'
        assert 'timestamp' in d0

    def test_emit_appends_to_existing(self, tmp_path):
        path = tmp_path / 'run.jsonl'
        FileSink(path).emit('ev1', {})
        FileSink(path).emit('ev2', {})
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / 'nested' / 'deep' / 'run.jsonl'
        sink = FileSink(path)
        sink.emit('ev', {})
        sink.close()
        assert path.exists()


class TestMultiSink:
    def test_fan_out_to_all_sinks(self):
        captured = []

        class _RecordSink(TelemetrySink):
            def __init__(self, tag):
                self.tag = tag
            def emit(self, event, payload):
                captured.append(self.tag)

        multi = MultiSink([_RecordSink('a'), _RecordSink('b'), _RecordSink('c')])
        multi.emit('skill.started', {})
        assert captured == ['a', 'b', 'c']

    def test_failing_sink_does_not_block_others(self):
        captured = []

        class _BadSink(TelemetrySink):
            def emit(self, event, payload):
                raise RuntimeError('boom')

        class _GoodSink(TelemetrySink):
            def emit(self, event, payload):
                captured.append(event)

        multi = MultiSink([_BadSink(), _GoodSink()])
        multi.emit('skill.started', {})  # must not raise
        assert captured == ['skill.started']

    def test_close_calls_all_sinks(self):
        closed = []

        class _TrackSink(TelemetrySink):
            def __init__(self, tag): self.tag = tag
            def emit(self, e, p): pass
            def close(self): closed.append(self.tag)

        MultiSink([_TrackSink('x'), _TrackSink('y')]).close()
        assert closed == ['x', 'y']

    def test_empty_multi_sink_is_valid(self):
        MultiSink([]).emit('ev', {})  # must not raise


# ── Integration: WIA adapter + skill adapter ──────────────────────────────────

class TestWIAAdapterWithWeldSkill:
    """Run the WIA weld chs_adapter using HyundaiWIAAdapter as middleware."""

    def _run_weld(self, adapter, profile='tack_weld'):
        import importlib.util
        adapter_path = ROOT / 'examples' / 'etd.hyundai.wia_welding' / 'policies' / 'chs_adapter.py'
        spec = importlib.util.spec_from_file_location('wia_chs_adapter', adapter_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['wia_chs_adapter'] = mod  # register so dataclass annotation lookup works
        spec.loader.exec_module(mod)
        return mod.run({'chsProfile': profile}, middleware=adapter)

    def test_tack_weld_completes(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        result = self._run_weld(adapter, profile='tack_weld')
        assert result['status'] == 'completed'

    def test_events_recorded_in_published(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        self._run_weld(adapter, profile='tack_weld')
        events = [p['message'].get('event') for p in adapter.published
                  if p['topic'] == 'telemetry.events']
        assert 'skill.started' in events
        assert 'skill.completed' in events

    def test_abort_on_human_in_zone(self):
        adapter = HyundaiWIAAdapter(dry_run=True)
        adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
        result = self._run_weld(adapter, profile='tack_weld')
        assert result['status'] == 'aborted'
        assert result['reason'] == 'human_in_forbidden_zone'

    def test_telemetry_sink_receives_skill_events(self, tmp_path):
        log = tmp_path / 'weld.jsonl'
        adapter = HyundaiWIAAdapter(dry_run=True, telemetry_sink=FileSink(log))
        self._run_weld(adapter, profile='tack_weld')
        lines = log.read_text().strip().splitlines()
        events = [json.loads(l)['event'] for l in lines]
        assert 'skill.started' in events
        assert 'skill.completed' in events
