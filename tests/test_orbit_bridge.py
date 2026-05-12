"""Tests for adapters/orbit_event_bridge.py."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.orbit_event_bridge import (
    to_enterprise_event,
    OrbitEventBridge,
    replay_skill_log,
)


# ── to_enterprise_event ───────────────────────────────────────────────────────

def test_envelope_required_fields():
    e = to_enterprise_event('skill.started', 'etd.pickplace.basic')
    for key in ('source', 'event', 'skill_id', 'robot_id', 'site_id',
                'severity', 'sequence', 'timestamp_ms', 'correlation_id', 'data'):
        assert key in e, f'missing key: {key}'


def test_envelope_source_constant():
    e = to_enterprise_event('skill.started', 'etd.x')
    assert e['source'] == 'etd-runtime'


def test_envelope_severity_mapping():
    assert to_enterprise_event('skill.started',   'x')['severity'] == 'info'
    assert to_enterprise_event('skill.completed', 'x')['severity'] == 'info'
    assert to_enterprise_event('skill.aborted',   'x')['severity'] == 'warn'
    assert to_enterprise_event('skill.failed',    'x')['severity'] == 'error'
    assert to_enterprise_event('safety.violation','x')['severity'] == 'critical'
    assert to_enterprise_event('primitive.entered','x')['severity'] == 'debug'


def test_envelope_unknown_event_defaults_to_info():
    e = to_enterprise_event('custom.event', 'etd.x')
    assert e['severity'] == 'info'


def test_envelope_site_id_forwarded():
    e = to_enterprise_event('skill.started', 'etd.x', site_id='hmgma-line-3')
    assert e['site_id'] == 'hmgma-line-3'


def test_envelope_robot_id_forwarded():
    e = to_enterprise_event('skill.started', 'etd.x', robot_id='atlas-07')
    assert e['robot_id'] == 'atlas-07'


def test_envelope_data_forwarded():
    e = to_enterprise_event('skill.completed', 'etd.x', data={'result': 'success'})
    assert e['data']['result'] == 'success'


def test_envelope_empty_data_default():
    e = to_enterprise_event('skill.started', 'etd.x')
    assert e['data'] == {}


def test_envelope_unique_correlation_ids():
    ids = {to_enterprise_event('skill.started', 'etd.x')['correlation_id'] for _ in range(10)}
    assert len(ids) == 10


def test_envelope_explicit_timestamp():
    e = to_enterprise_event('skill.started', 'etd.x', timestamp_ms=999_000)
    assert e['timestamp_ms'] == 999_000


# ── OrbitEventBridge — basic ──────────────────────────────────────────────────

def test_bridge_ingest_returns_envelope():
    b = OrbitEventBridge()
    env = b.ingest('skill.started', 'etd.pickplace.basic')
    assert env is not None
    assert env['event'] == 'skill.started'


def test_bridge_pending_count():
    b = OrbitEventBridge()
    assert b.pending() == 0
    b.ingest('skill.started', 'etd.x')
    assert b.pending() == 1
    b.ingest('skill.completed', 'etd.x')
    assert b.pending() == 2


def test_bridge_flush_returns_and_clears():
    b = OrbitEventBridge()
    b.ingest('skill.started', 'etd.x')
    b.ingest('skill.completed', 'etd.x')
    msgs = b.flush()
    assert len(msgs) == 2
    assert b.pending() == 0


def test_bridge_sequence_increments():
    b = OrbitEventBridge()
    b.ingest('skill.started',   'etd.x')
    b.ingest('skill.completed', 'etd.x')
    out = b.flush()
    assert out[0]['sequence'] == 1
    assert out[1]['sequence'] == 2


def test_bridge_sequence_persists_across_flushes():
    b = OrbitEventBridge()
    b.ingest('skill.started', 'etd.x')
    b.flush()
    b.ingest('skill.completed', 'etd.x')
    out = b.flush()
    assert out[0]['sequence'] == 2


def test_bridge_reset_clears_buffer_and_sequence():
    b = OrbitEventBridge()
    b.ingest('skill.started', 'etd.x')
    b.reset()
    assert b.pending() == 0
    b.ingest('skill.started', 'etd.x')
    out = b.flush()
    assert out[0]['sequence'] == 1


# ── OrbitEventBridge — severity filter ───────────────────────────────────────

def test_bridge_debug_filtered_at_info_level():
    b = OrbitEventBridge(min_severity='info')
    env = b.ingest('primitive.entered', 'etd.x')
    assert env is None
    assert b.pending() == 0


def test_bridge_info_passes_at_info_level():
    b = OrbitEventBridge(min_severity='info')
    env = b.ingest('skill.started', 'etd.x')
    assert env is not None


def test_bridge_critical_bypasses_filter():
    b = OrbitEventBridge(min_severity='error')
    # 'skill.aborted' is in _CRITICAL_EVENTS even though severity='warn' < 'error'
    env = b.ingest('skill.aborted', 'etd.x')
    assert env is not None


def test_bridge_safety_violation_always_passes():
    b = OrbitEventBridge(min_severity='critical')
    env = b.ingest('safety.violation', 'etd.x')
    assert env is not None


def test_bridge_warn_filtered_at_error_level():
    b = OrbitEventBridge(min_severity='error')
    # 'telemetry.metrics' has severity 'info' and is NOT a critical event
    env = b.ingest('telemetry.metrics', 'etd.x')
    assert env is None


# ── OrbitEventBridge — on_flush callback ──────────────────────────────────────

def test_bridge_on_flush_callback_called():
    received = []
    b = OrbitEventBridge(on_flush=received.append)
    b.ingest('skill.started',   'etd.x')
    b.ingest('skill.completed', 'etd.x')
    b.flush()
    assert len(received) == 2
    assert received[0]['event'] == 'skill.started'


def test_bridge_on_flush_not_called_when_empty():
    called = []
    b = OrbitEventBridge(on_flush=lambda e: called.append(e))
    b.flush()
    assert called == []


# ── OrbitEventBridge — metadata forwarding ───────────────────────────────────

def test_bridge_robot_and_site_forwarded():
    b = OrbitEventBridge(robot_id='atlas-01', site_id='hmgma-line-3')
    env = b.ingest('skill.started', 'etd.atlas.humanoid_walkfetch')
    assert env['robot_id'] == 'atlas-01'
    assert env['site_id'] == 'hmgma-line-3'


# ── replay_skill_log ──────────────────────────────────────────────────────────

def test_replay_returns_all_events():
    log = [
        {'event': 'skill.started',   'skill_id': 'etd.pickplace.basic'},
        {'event': 'skill.completed', 'skill_id': 'etd.pickplace.basic',
         'data': {'result': 'success'}},
    ]
    b = OrbitEventBridge()
    msgs = replay_skill_log(log, b)
    assert len(msgs) == 2


def test_replay_data_forwarded():
    log = [{'event': 'skill.completed', 'skill_id': 'etd.x', 'data': {'items': 3}}]
    b = OrbitEventBridge()
    msgs = replay_skill_log(log, b)
    assert msgs[0]['data']['items'] == 3


def test_replay_respects_filter():
    log = [
        {'event': 'primitive.entered', 'skill_id': 'etd.x'},
        {'event': 'skill.started',     'skill_id': 'etd.x'},
    ]
    b = OrbitEventBridge(min_severity='info')
    msgs = replay_skill_log(log, b)
    assert len(msgs) == 1
    assert msgs[0]['event'] == 'skill.started'


def test_replay_missing_skill_id_defaults():
    log = [{'event': 'skill.started'}]
    b = OrbitEventBridge()
    msgs = replay_skill_log(log, b)
    assert msgs[0]['skill_id'] == 'unknown'


# ── Additional severity and timestamp coverage ─────────────────────────────────

def test_bridge_safety_warning_bypasses_filter():
    b = OrbitEventBridge(min_severity='error')
    # 'safety.warning' is in _CRITICAL_EVENTS → always passes regardless of filter
    env = b.ingest('safety.warning', 'etd.x')
    assert env is not None
    assert b.pending() == 1


def test_bridge_ingest_with_explicit_timestamp():
    b = OrbitEventBridge()
    env = b.ingest('skill.started', 'etd.x', timestamp_ms=42_000)
    assert env is not None
    assert env['timestamp_ms'] == 42_000


# ── Remaining severity mappings ────────────────────────────────────────────────

def test_envelope_primitive_exited_is_debug():
    e = to_enterprise_event('primitive.exited', 'etd.x')
    assert e['severity'] == 'debug'


def test_envelope_telemetry_heartbeat_is_debug():
    e = to_enterprise_event('telemetry.heartbeat', 'etd.x')
    assert e['severity'] == 'debug'


def test_envelope_telemetry_metrics_is_info():
    e = to_enterprise_event('telemetry.metrics', 'etd.x')
    assert e['severity'] == 'info'


def test_envelope_safety_warning_is_warn():
    e = to_enterprise_event('safety.warning', 'etd.x')
    assert e['severity'] == 'warn'


def test_bridge_primitive_exited_filtered_at_info():
    b = OrbitEventBridge(min_severity='info')
    env = b.ingest('primitive.exited', 'etd.x')
    assert env is None
    assert b.pending() == 0


def test_bridge_telemetry_heartbeat_filtered_at_info():
    b = OrbitEventBridge(min_severity='info')
    env = b.ingest('telemetry.heartbeat', 'etd.x')
    assert env is None


def test_bridge_telemetry_metrics_passes_at_info():
    b = OrbitEventBridge(min_severity='info')
    env = b.ingest('telemetry.metrics', 'etd.x')
    assert env is not None
    assert env['event'] == 'telemetry.metrics'


# ── to_enterprise_event: timestamp_ms=0 preserved (is not None check) ─────────

def test_envelope_timestamp_zero_is_preserved():
    """timestamp_ms=0 is falsy but not None — the 'is not None' guard must preserve it."""
    e = to_enterprise_event('skill.started', 'etd.x', timestamp_ms=0)
    # If the code used `if timestamp_ms:` instead of `if timestamp_ms is not None:`,
    # 0 would be overwritten by the current time. This test asserts 0 is kept.
    assert e['timestamp_ms'] == 0


# ── replay_skill_log: event without 'data' key → data or {} ─────────────────

def test_replay_skill_log_event_without_data_key():
    """Event dict with no 'data' key → e.get('data') returns None → data or {} → envelope data={}."""
    log = [{'event': 'skill.started', 'skill_id': 'etd.x'}]  # no 'data' key
    b = OrbitEventBridge()
    msgs = replay_skill_log(log, b)
    assert len(msgs) == 1
    assert msgs[0]['data'] == {}
