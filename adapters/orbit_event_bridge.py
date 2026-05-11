"""Orbit event bridge — translates ETD telemetry events into Orbit-compatible messages.

Orbit is Hyundai/Boston Dynamics' robot operations platform.  This module provides:
  - `to_enterprise_event()` — convert a raw ETD event dict to Orbit envelope format
  - `OrbitEventBridge` — stateful bridge with filtering, buffering, and flush

Usage::

    from adapters.orbit_event_bridge import OrbitEventBridge

    bridge = OrbitEventBridge(robot_id='atlas-01', site_id='hmgma-line-3')
    bridge.ingest('skill.started',   skill_id='etd.atlas.humanoid_walkfetch', data={})
    bridge.ingest('primitive.entered', skill_id='etd.atlas.humanoid_walkfetch',
                  data={'primitive': 'nav_to_pick'})
    bridge.ingest('skill.completed', skill_id='etd.atlas.humanoid_walkfetch',
                  data={'result': 'success'})

    for msg in bridge.flush():
        send_to_orbit(msg)          # caller-provided transport
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# ── Severity mapping ──────────────────────────────────────────────────────────

_SEVERITY: Dict[str, str] = {
    'skill.started':       'info',
    'skill.completed':     'info',
    'skill.aborted':       'warn',
    'skill.failed':        'error',
    'primitive.entered':   'debug',
    'primitive.exited':    'debug',
    'safety.violation':    'critical',
    'safety.warning':      'warn',
    'telemetry.heartbeat': 'debug',
    'telemetry.metrics':   'info',
}

# Events always forwarded regardless of filter level
_CRITICAL_EVENTS = frozenset({
    'skill.aborted', 'skill.failed', 'safety.violation', 'safety.warning',
})

# ── Envelope builder ──────────────────────────────────────────────────────────

def to_enterprise_event(
    event_name: str,
    skill_id: str,
    robot_id: str = 'robot-01',
    data: dict | None = None,
    *,
    site_id: str = 'unknown',
    sequence: int = 0,
    timestamp_ms: int | None = None,
) -> dict:
    """Return an Orbit-compatible enterprise event envelope.

    Schema mirrors the Orbit OpenAPI event ingestion contract:
      source, event, skill_id, robot_id, site_id, severity, sequence,
      timestamp_ms, correlation_id, data
    """
    return {
        'source':         'etd-runtime',
        'event':          event_name,
        'skill_id':       skill_id,
        'robot_id':       robot_id,
        'site_id':        site_id,
        'severity':       _SEVERITY.get(event_name, 'info'),
        'sequence':       sequence,
        'timestamp_ms':   timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
        'correlation_id': str(uuid.uuid4()),
        'data':           data or {},
    }


# ── Stateful bridge ───────────────────────────────────────────────────────────

_LEVEL_ORDER = ('debug', 'info', 'warn', 'error', 'critical')


@dataclass
class OrbitEventBridge:
    """Stateful bridge that ingests ETD telemetry events and buffers Orbit envelopes.

    Args:
        robot_id:     Robot identifier forwarded in every envelope.
        site_id:      Facility / line identifier forwarded in every envelope.
        min_severity: Minimum severity to buffer ('debug'|'info'|'warn'|'error'|'critical').
                      Critical events are always buffered regardless of this setting.
        on_flush:     Optional callback invoked for each envelope during flush().
    """
    robot_id:     str = 'robot-01'
    site_id:      str = 'unknown'
    min_severity: str = 'info'
    on_flush:     Optional[Callable[[dict], None]] = field(default=None, repr=False)

    _buffer:   List[dict] = field(default_factory=list, init=False, repr=False)
    _sequence: int        = field(default=0, init=False, repr=False)

    def ingest(
        self,
        event_name: str,
        skill_id: str,
        data: dict | None = None,
        timestamp_ms: int | None = None,
    ) -> Optional[dict]:
        """Translate one ETD event into an Orbit envelope and buffer it.

        Returns the envelope if it passed the severity filter, else None.
        """
        severity = _SEVERITY.get(event_name, 'info')
        passes_filter = (
            _LEVEL_ORDER.index(severity) >= _LEVEL_ORDER.index(self.min_severity)
            or event_name in _CRITICAL_EVENTS
        )
        if not passes_filter:
            return None

        self._sequence += 1
        envelope = to_enterprise_event(
            event_name,
            skill_id=skill_id,
            robot_id=self.robot_id,
            data=data,
            site_id=self.site_id,
            sequence=self._sequence,
            timestamp_ms=timestamp_ms,
        )
        self._buffer.append(envelope)
        return envelope

    def flush(self) -> List[dict]:
        """Return and clear all buffered envelopes; invoke on_flush callback for each."""
        batch, self._buffer = self._buffer, []
        if self.on_flush:
            for envelope in batch:
                self.on_flush(envelope)
        return batch

    def pending(self) -> int:
        """Return the number of buffered envelopes not yet flushed."""
        return len(self._buffer)

    def reset(self) -> None:
        """Clear buffer and reset sequence counter."""
        self._buffer = []
        self._sequence = 0


# ── Convenience: replay a skill execution log through the bridge ──────────────

def replay_skill_log(
    events: List[Dict[str, Any]],
    bridge: OrbitEventBridge,
) -> List[dict]:
    """Ingest a list of ETD telemetry event dicts through *bridge* and flush.

    Each dict must have at least ``event`` and ``skill_id`` keys.
    Optional keys: ``data``, ``timestamp_ms``.
    """
    for e in events:
        bridge.ingest(
            e['event'],
            skill_id=e.get('skill_id', 'unknown'),
            data=e.get('data'),
            timestamp_ms=e.get('timestamp_ms'),
        )
    return bridge.flush()
