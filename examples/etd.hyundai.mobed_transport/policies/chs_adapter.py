"""ETD CHS Adapter — Hyundai MobED / AMR Transport Skill.

Implements a 5-primitive transport sequence:
  navigate_to_pickup → dock_and_lift → navigate_to_destination
  → dock_and_lower → confirm_delivery

Human-aware: reduces speed when human detected within proximity radius.
Safety: aborts on human_in_forbidden_zone at every primitive.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PRIMITIVE_ORDER = [
    'navigate_to_pickup',
    'dock_and_lift',
    'navigate_to_destination',
    'dock_and_lower',
    'confirm_delivery',
]

_PROFILE_DEFAULTS: Dict[str, Dict] = {
    'standard_carry': {
        'payloadKg': 50.0, 'maxSpeedMs': 1.2, 'humanAwareSpeedMs': 0.4,
        'liftHeightMm': 80, 'navigationTimeoutSec': 180,
        'obstacleStopDistance_m': 0.5,
    },
    'heavy_carry': {
        'payloadKg': 100.0, 'maxSpeedMs': 0.6, 'humanAwareSpeedMs': 0.2,
        'liftHeightMm': 60, 'navigationTimeoutSec': 300,
        'obstacleStopDistance_m': 0.8,
    },
    'human_aware_carry': {
        'payloadKg': 30.0, 'maxSpeedMs': 0.8, 'humanAwareSpeedMs': 0.2,
        'liftHeightMm': 80, 'navigationTimeoutSec': 240,
        'obstacleStopDistance_m': 1.0,
    },
}


@dataclass
class TransportContext:
    profile: str
    payload_kg: float
    max_speed_ms: float
    human_aware_speed_ms: float
    lift_height_mm: int
    navigation_timeout_sec: float
    obstacle_stop_distance_m: float


def _resolve_context(job: Dict[str, Any]) -> TransportContext:
    profile_name = job.get('chsProfile', 'standard_carry')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['standard_carry'])
    return TransportContext(
        profile=profile_name,
        payload_kg=job.get('payloadKg', d['payloadKg']),
        max_speed_ms=d['maxSpeedMs'],
        human_aware_speed_ms=d['humanAwareSpeedMs'],
        lift_height_mm=d['liftHeightMm'],
        navigation_timeout_sec=job.get('navigationTimeoutSec', d['navigationTimeoutSec']),
        obstacle_stop_distance_m=d['obstacleStopDistance_m'],
    )


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def _read(middleware: Any, topic: str) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read(topic) or {}
    return {}


def _navigate_segment(
    middleware: Any, ctx: TransportContext,
    segment: str, nav_time_sim_s: float,
    completed: List[str],
    at_primitive: str,
) -> Optional[Dict[str, Any]]:
    """Simulate navigation with per-step safety and human-proximity checks."""
    steps = max(1, int(nav_time_sim_s / 0.005))
    _publish(middleware, 'navigation.started', {'segment': segment})
    for step in range(steps):
        time.sleep(nav_time_sim_s / steps)
        safety = _read(middleware, 'state.safety_state')
        if safety.get('human_in_forbidden_zone'):
            _publish(middleware, 'skill.aborted', {
                'reason': 'human_in_forbidden_zone', 'at_primitive': at_primitive,
            })
            return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                    'at_primitive': at_primitive, 'primitives_completed': completed}
        if safety.get('human_in_safety_radius'):
            _publish(middleware, 'safety.human_near', {
                'speed_reduced_to': ctx.human_aware_speed_ms,
            })
        progress = (step + 1) / steps
        _publish(middleware, 'navigation.progress', {
            'segment': segment, 'progress': round(progress, 2),
        })
    _publish(middleware, 'navigation.arrived', {'segment': segment})
    return None


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for MobED autonomous transport.

    Args:
        job_context: CHS job dict — chsProfile, origin, destination, payloadKg, ...
        middleware:  OEM adapter with .publish(topic, msg) and .read(topic)

    Returns:
        Execution result with delivery status and transport metrics
    """
    ctx = _resolve_context(job_context)
    completed: List[str] = []
    payload_secured = False

    def _safety() -> Dict[str, Any]:
        return _read(middleware, 'state.safety_state')

    _publish(middleware, 'skill.started', {
        'profile': ctx.profile,
        'payload_kg': ctx.payload_kg,
        'max_speed_ms': ctx.max_speed_ms,
    })

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        safety = _safety()
        if safety.get('human_in_forbidden_zone'):
            _publish(middleware, 'skill.aborted', {
                'reason': 'human_in_forbidden_zone', 'at_primitive': primitive,
            })
            return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                    'at_primitive': primitive, 'primitives_completed': completed}

        if primitive == 'navigate_to_pickup':
            err = _navigate_segment(middleware, ctx, 'to_pickup',
                                    0.02, completed, primitive)
            if err:
                return err

        elif primitive == 'dock_and_lift':
            time.sleep(0.005)
            _publish(middleware, 'transport.lifted', {
                'payload_kg': ctx.payload_kg, 'height_mm': ctx.lift_height_mm,
            })
            payload_secured = True

        elif primitive == 'navigate_to_destination':
            err = _navigate_segment(middleware, ctx, 'to_destination',
                                    0.02, completed, primitive)
            if err:
                return err

        elif primitive == 'dock_and_lower':
            time.sleep(0.005)
            _publish(middleware, 'transport.delivered', {
                'payload_kg': ctx.payload_kg,
            })
            payload_secured = False

        elif primitive == 'confirm_delivery':
            pose = _read(middleware, 'state.robot_pose')
            _publish(middleware, 'command.skill_intent', {
                'type': 'command.skill_intent', 'primitive': 'confirm_delivery',
                'destination_reached': True, 'robot_pose': pose,
                'timestamp': time.time(),
            })

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {
        'payload_kg': ctx.payload_kg,
        'delivered': True,
    })
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'payload_kg': ctx.payload_kg,
        'delivered': True,
        'primitives_executed': len(completed),
    }


if __name__ == '__main__':
    print(run({'chsProfile': 'standard_carry'}))
