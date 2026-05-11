"""Fake middleware endpoint — in-process mock of the OEM robot middleware.

Simulates the request/response contract of a real robot cell controller:
- validates the skill intent request (bounded, allowed commands, station known)
- returns an execution handle with a fake execution_id
- supports cancel, status query, and result retrieval

Used by sim demos, acceptance tests, and integration fixtures that need
a middleware layer without real hardware.

Usage::

    from sim.fake_middleware_endpoint import FakeMiddleware

    mw = FakeMiddleware(station_id='logistics_cell_a')
    handle = mw.send_request({'bounded': True, 'request_type': 'skill_intent',
                              'payload': {'family': 'pickplace'}})
    assert handle['accepted']
    result = mw.get_result(handle['execution_id'])
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_FORBIDDEN_COMMANDS = frozenset({'servo_torque', 'collision_disable', 'emergency_stop_override'})
_KNOWN_STATIONS = frozenset({
    'logistics_cell_a', 'assembly_station_a', 'cobot_zone_a',
    'weld_station_a', 'mobed_logistics_a', 'humanoid_hmgma_a',
    'unknown',  # legacy default
})


@dataclass
class FakeMiddleware:
    """Stateful in-process mock of a robot cell OEM middleware controller.

    Args:
        station_id:   Station this middleware is bound to.
        latency_ms:   Simulated processing latency (does NOT actually sleep — just
                      recorded in response metadata).
        fail_rate:    Fraction of requests to reject with a simulated fault (0.0–1.0).
    """
    station_id: str = 'unknown'
    latency_ms: int = 0
    fail_rate:  float = 0.0

    _executions: Dict[str, dict] = field(default_factory=dict, init=False, repr=False)

    def send_request(self, request: dict) -> dict:
        """Validate and accept (or reject) a skill intent request.

        Returns a response dict with ``accepted`` bool and ``execution_id`` on success.
        """
        import random

        if not request.get('bounded'):
            return {'accepted': False, 'reason': 'unbounded_request', 'execution_id': None}

        if request.get('station_id', self.station_id) not in _KNOWN_STATIONS:
            return {'accepted': False, 'reason': 'unknown_station', 'execution_id': None}

        payload = request.get('payload', {})
        for forbidden in _FORBIDDEN_COMMANDS:
            if forbidden in payload:
                return {'accepted': False, 'reason': f'forbidden_command:{forbidden}',
                        'execution_id': None}

        if self.fail_rate > 0.0 and random.random() < self.fail_rate:
            return {'accepted': False, 'reason': 'simulated_fault', 'execution_id': None}

        exec_id = f'exec-{uuid.uuid4().hex[:8]}'
        self._executions[exec_id] = {
            'execution_id': exec_id,
            'station_id':   request.get('station_id', self.station_id),
            'request_type': request.get('request_type', 'skill_intent'),
            'status':       'running',
            'started_at':   time.time(),
            'latency_ms':   self.latency_ms,
            'payload':      payload,
        }
        return {'accepted': True, 'execution_id': exec_id,
                'latency_ms': self.latency_ms}

    def complete(self, execution_id: str, result: str = 'success',
                 data: dict | None = None) -> bool:
        """Mark an execution as complete (called by test harness to simulate completion)."""
        if execution_id not in self._executions:
            return False
        self._executions[execution_id].update({
            'status':       result,
            'completed_at': time.time(),
            'result_data':  data or {},
        })
        return True

    def get_status(self, execution_id: str) -> Optional[dict]:
        """Return the current status record for an execution, or None if unknown."""
        return self._executions.get(execution_id)

    def get_result(self, execution_id: str) -> Optional[dict]:
        """Return the result dict once an execution is no longer 'running', else None."""
        record = self._executions.get(execution_id)
        if record is None or record['status'] == 'running':
            return None
        return record

    def cancel(self, execution_id: str) -> bool:
        """Cancel a running execution. Returns True if it was running, False otherwise."""
        record = self._executions.get(execution_id)
        if record and record['status'] == 'running':
            record['status'] = 'cancelled'
            record['completed_at'] = time.time()
            return True
        return False

    def active_count(self) -> int:
        return sum(1 for r in self._executions.values() if r['status'] == 'running')


# ── Module-level default instance (used by legacy send_request import) ────────

_default = FakeMiddleware()


def send_request(request: dict) -> dict:
    """Legacy function-level interface — delegates to the default FakeMiddleware."""
    return _default.send_request(request)
