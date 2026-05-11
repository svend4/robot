"""CHS adapter for etd.pickplace.basic — pick-and-place skill.

Implements the task-context (CHS) layer:
  - selects grasp strategy based on payload and fragility
  - adjusts force window and speed profile per CHS profile
  - emits skill_intent for each primitive in the execution sequence
  - monitors safety state between primitives
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PRIMITIVE_ORDER = [
    'approach_arc',
    'guarded_grasp',
    'lift_stabilize',
    'transport_safe',
    'place_release',
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'small_box': {
        'payloadKg': 1.5,
        'forceWindowN': [3, 18],
        'speedFactor': 1.0,
        'graspDwellMs': 200,
        'bodyMode': 'stable_reach',
        'armMode': 'guarded_arc',
        'wristMode': 'adaptive_contact',
    },
    'fragile_item': {
        'payloadKg': 0.8,
        'forceWindowN': [2, 10],
        'speedFactor': 0.6,
        'graspDwellMs': 350,
        'bodyMode': 'micro_stable',
        'armMode': 'slow_arc',
        'wristMode': 'minimal_force',
    },
}


@dataclass
class SkillContext:
    profile: str
    payload_kg: float
    force_window: List[float]
    speed_factor: float
    grasp_dwell_ms: int
    body_mode: str
    arm_mode: str
    wrist_mode: str


def _resolve_context(job: Dict[str, Any]) -> SkillContext:
    profile_name = job.get('chsProfile', 'small_box')
    defaults = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['small_box'])
    fragile = job.get('fragility', 'low') == 'high'
    return SkillContext(
        profile=profile_name,
        payload_kg=job.get('payloadKg', defaults['payloadKg']),
        force_window=job.get('forceWindowN', defaults['forceWindowN']),
        speed_factor=0.5 if fragile else job.get('speedFactor', defaults['speedFactor']),
        grasp_dwell_ms=defaults['graspDwellMs'],
        body_mode='micro_stable' if fragile else defaults['bodyMode'],
        arm_mode='slow_arc' if fragile else defaults['armMode'],
        wrist_mode='minimal_force' if fragile else defaults['wristMode'],
    )


def _build_intent(primitive: str, ctx: SkillContext) -> Dict[str, Any]:
    return {
        'type': 'command.skill_intent',
        'primitive': primitive,
        'body_mode': ctx.body_mode,
        'arm_mode': ctx.arm_mode,
        'wrist_mode': ctx.wrist_mode,
        'payload_kg': ctx.payload_kg,
        'force_window_n': ctx.force_window,
        'speed_factor': ctx.speed_factor,
        'timestamp': time.time(),
    }


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point.

    Args:
        job_context: CHS job dict — chsProfile, payloadKg, fragility, destination, priority
        middleware:  OEM adapter with .publish(topic, msg) and .read(topic) methods

    Returns:
        Execution result: status, profile, primitives_executed
    """
    ctx = _resolve_context(job_context)
    results: List[Dict] = []

    def _publish(event: str, extra: Optional[Dict] = None) -> None:
        if hasattr(middleware, 'publish'):
            middleware.publish('telemetry.events', {'event': event, **(extra or {})})

    def _read_safety() -> Dict[str, Any]:
        if hasattr(middleware, 'read'):
            return middleware.read('state.safety_state') or {}
        return {}

    _publish('skill.started', {'profile': ctx.profile})

    for primitive in PRIMITIVE_ORDER:
        _publish('primitive.entered', {'primitive': primitive})
        intent = _build_intent(primitive, ctx)
        if hasattr(middleware, 'publish'):
            middleware.publish('command.skill_intent', intent)
        results.append({'primitive': primitive, 'status': 'ok'})

        if primitive == 'guarded_grasp':
            time.sleep(ctx.grasp_dwell_ms / 1000.0)

        safety = _read_safety()
        if safety.get('human_in_forbidden_zone'):
            _publish('skill.aborted', {'reason': 'human_in_forbidden_zone', 'at_primitive': primitive})
            return {
                'status': 'aborted',
                'reason': 'human_in_forbidden_zone',
                'at_primitive': primitive,
                'primitives_completed': results,
            }

        _publish('primitive.exited', {'primitive': primitive})

    _publish('skill.completed')
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'primitives_executed': len(results),
        'payload_kg': ctx.payload_kg,
        'speed_factor': ctx.speed_factor,
    }


if __name__ == '__main__':
    result = run({'chsProfile': 'fragile_item', 'destination': 'output_tray', 'priority': 'normal'})
    print(json.dumps(result, indent=2, default=str))
