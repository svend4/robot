"""Event replay — replay an ETD skill execution log through the Orbit bridge.

Supports both simple string lists (event names only) and rich dicts
(event, skill_id, data, timestamp_ms).  Returns the list of Orbit
envelopes produced after applying the bridge's severity filter.

Usage::

    from sim.event_replay import replay, replay_execution

    # Simple: event names only (all mapped to one skill_id)
    msgs = replay(['skill.started', 'primitive.entered', 'skill.completed'],
                  skill_id='etd.pickplace.basic')

    # Rich: list of dicts with optional data and timestamps
    log = [
        {'event': 'skill.started',     'skill_id': 'etd.pickplace.basic'},
        {'event': 'primitive.entered', 'skill_id': 'etd.pickplace.basic',
         'data': {'primitive': 'approach'}},
        {'event': 'skill.completed',   'skill_id': 'etd.pickplace.basic',
         'data': {'result': 'success', 'items_picked': 1}},
    ]
    msgs = replay_execution(log, robot_id='bot-01', site_id='logistics_cell_a')
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Union

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.orbit_event_bridge import OrbitEventBridge, replay_skill_log


def replay(
    events: List[Union[str, Dict[str, Any]]],
    skill_id: str = 'unknown',
    robot_id: str = 'robot-01',
    site_id: str = 'unknown',
    min_severity: str = 'info',
) -> List[dict]:
    """Replay a sequence of event names or event dicts through the Orbit bridge.

    String entries are treated as event names for *skill_id*.
    Dict entries may supply their own ``skill_id``, ``data``, and ``timestamp_ms``.
    """
    bridge = OrbitEventBridge(robot_id=robot_id, site_id=site_id, min_severity=min_severity)
    normalised = []
    for e in events:
        if isinstance(e, str):
            normalised.append({'event': e, 'skill_id': skill_id})
        else:
            entry = dict(e)
            entry.setdefault('skill_id', skill_id)
            normalised.append(entry)
    return replay_skill_log(normalised, bridge)


def replay_execution(
    log: List[Dict[str, Any]],
    robot_id: str = 'robot-01',
    site_id: str = 'unknown',
    min_severity: str = 'info',
) -> List[dict]:
    """Replay a rich execution log (list of dicts) and return Orbit envelopes."""
    bridge = OrbitEventBridge(robot_id=robot_id, site_id=site_id, min_severity=min_severity)
    return replay_skill_log(log, bridge)


# ── Standard skill lifecycle sequences ───────────────────────────────────────

def nominal_lifecycle(skill_id: str, primitives: List[str]) -> List[Dict[str, Any]]:
    """Build a complete nominal execution log for a skill with the given primitives."""
    log: List[Dict[str, Any]] = [{'event': 'skill.started', 'skill_id': skill_id}]
    for prim in primitives:
        log.append({'event': 'primitive.entered', 'skill_id': skill_id,
                    'data': {'primitive': prim}})
        log.append({'event': 'primitive.exited',  'skill_id': skill_id,
                    'data': {'primitive': prim, 'status': 'ok'}})
    log.append({'event': 'skill.completed', 'skill_id': skill_id,
                'data': {'result': 'success'}})
    return log


def aborted_lifecycle(skill_id: str, primitives_before_abort: List[str],
                      reason: str = 'human_in_forbidden_zone') -> List[Dict[str, Any]]:
    """Build an execution log where the skill aborts mid-execution."""
    log: List[Dict[str, Any]] = [{'event': 'skill.started', 'skill_id': skill_id}]
    for prim in primitives_before_abort:
        log.append({'event': 'primitive.entered', 'skill_id': skill_id,
                    'data': {'primitive': prim}})
        log.append({'event': 'primitive.exited',  'skill_id': skill_id,
                    'data': {'primitive': prim, 'status': 'ok'}})
    log.append({'event': 'skill.aborted', 'skill_id': skill_id, 'data': {'reason': reason}})
    return log


if __name__ == '__main__':
    import json
    skill = 'etd.pickplace.basic'
    log = nominal_lifecycle(skill, ['approach', 'grasp', 'lift', 'move_to_place', 'place', 'retreat'])
    msgs = replay(log, skill_id=skill, site_id='logistics_cell_a')
    print(json.dumps({'skill_id': skill, 'envelopes': len(msgs),
                      'first': msgs[0]['event'], 'last': msgs[-1]['event']}, indent=2))
