"""CHS adapter for etd.atlas.humanoid_walkfetch — Boston Dynamics Atlas humanoid fetch skill.

This skill coordinates the full walk-and-fetch task cycle for Atlas:
  1. Localize target in scene map
  2. Plan collision-free walk path (BVS — whole-body locomotion)
  3. Walk to target location
  4. Stabilize stance at target
  5. Approach object with arm (SVS — arm trajectory)
  6. Grasp object (MVS — wrist/force control)
  7. Adopt secure carry posture
  8. Walk to destination (gait adapts to payload)
  9. Deposit to bin or hand over to human

Hyundai context:
  At HMGMA (Hyundai Motor Group Manufacturing Alabama), Atlas is planned for
  deployment in sequencing tasks by 2028. This skill covers the application-layer
  intent emission for such tasks — the OEM locomotion and balance core remain
  under Boston Dynamics / Hyundai certified control at all times.

Safety boundary:
  This skill NEVER overrides: balance core, locomotion core, emergency stop,
  collision detection, or certified torque limits. It only emits skill_intent
  signals which the OEM stack interprets and executes within its own safety envelope.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

PRIMITIVE_ORDER = [
    'localize_target',
    'plan_walk_path',
    'walk_to_target',
    'stabilize_stance',
    'approach_object',
    'grasp_object',
    'secure_carry_posture',
    'walk_to_destination',
    'deposit_or_handover',
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'sequencing_carry': {
        'payloadKg': 5.0,
        'forceWindowN': [15, 60],
        'walkSpeedMs': 0.8,
        'humanAwareRadius': 2.0,
        'deliveryMode': 'deposit',
        'bodyMode': 'walk_carry_stable',
        'armMode': 'carry_arc',
        'wristMode': 'secure_grip',
        'graspConfidenceMin': 0.85,
    },
    'precision_fetch': {
        'payloadKg': 2.0,
        'forceWindowN': [5, 20],
        'walkSpeedMs': 0.4,
        'humanAwareRadius': 2.5,
        'deliveryMode': 'deposit',
        'bodyMode': 'micro_stable',
        'armMode': 'slow_arc',
        'wristMode': 'minimal_force',
        'graspConfidenceMin': 0.92,
    },
    'human_handover': {
        'payloadKg': 3.0,
        'forceWindowN': [5, 30],
        'walkSpeedMs': 0.5,
        'humanAwareRadius': 1.5,
        'deliveryMode': 'handover',
        'bodyMode': 'social_standby',
        'armMode': 'handover_arc',
        'wristMode': 'compliant_release',
        'graspConfidenceMin': 0.85,
        'humanReadyTimeoutSec': 20.0,
    },
}


@dataclass
class AtlasContext:
    profile: str
    payload_kg: float
    force_window: Tuple[float, float]
    walk_speed_ms: float
    human_aware_radius: float
    delivery_mode: str
    body_mode: str
    arm_mode: str
    wrist_mode: str
    grasp_confidence_min: float
    human_ready_timeout: float
    fetch_target: Dict[str, Any]
    destination: Dict[str, Any]


def _resolve_context(job: Dict[str, Any]) -> AtlasContext:
    profile_name = job.get('chsProfile', 'sequencing_carry')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['sequencing_carry'])
    return AtlasContext(
        profile=profile_name,
        payload_kg=job.get('payloadKg', d['payloadKg']),
        force_window=tuple(job.get('forceWindowN', d['forceWindowN'])),
        walk_speed_ms=d['walkSpeedMs'],
        human_aware_radius=d['humanAwareRadius'],
        delivery_mode=d['deliveryMode'],
        body_mode=d['bodyMode'],
        arm_mode=d['armMode'],
        wrist_mode=d['wristMode'],
        grasp_confidence_min=d['graspConfidenceMin'],
        human_ready_timeout=d.get('humanReadyTimeoutSec', 15.0),
        fetch_target=job.get('fetchTarget', {'x': 3.0, 'y': 1.5, 'frame': 'world_map'}),
        destination=job.get('deliveryDestination', {'x': 8.0, 'y': 0.0, 'frame': 'world_map'}),
    )


def _read_state(middleware: Any, topic: str) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read(topic) or {}
    # Simulation defaults — realistic Atlas state
    defaults = {
        'state.robot_pose': {'x': 0.0, 'y': 0.0, 'heading_deg': 0.0},
        'state.balance_state': {'stable': True, 'com_margin': 0.12, 'gait': 'stand'},
        'state.safety_state': {
            'human_in_forbidden_zone': False, 'human_ready_signal': True,
            'human_distance_m': 3.5, 'human_in_safety_radius': False,
        },
        'perception.object_pose': {
            'confidence': 0.96, 'x': 3.0, 'y': 1.5, 'z': 0.8,
            'object_class': 'automotive_part', 'mass_estimate_kg': 4.5,
        },
        'perception.scene_map': {'map_ready': True, 'obstacles': []},
    }
    return defaults.get(topic, {})


def _emit_intent(middleware: Any, primitive: str, ctx: AtlasContext, extra: Optional[Dict] = None) -> None:
    intent = {
        'type': 'command.skill_intent',
        'primitive': primitive,
        'body_mode': ctx.body_mode,
        'arm_mode': ctx.arm_mode,
        'wrist_mode': ctx.wrist_mode,
        'payload_kg': ctx.payload_kg,
        'force_window_n': list(ctx.force_window),
        'walk_speed_ms': ctx.walk_speed_ms,
        'timestamp': time.time(),
        **(extra or {}),
    }
    if hasattr(middleware, 'publish'):
        middleware.publish('command.skill_intent', intent)


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for Atlas humanoid walk-and-fetch.

    Args:
        job_context: CHS job dict — chsProfile, fetchTarget, deliveryDestination,
                     payloadKg, humanId (for handover), priority
        middleware:  OEM adapter with .publish(topic, msg) and .read(topic)
                     The locomotion.walk_planner and balance_state must be available.

    Returns:
        Execution result: status, primitives_executed, delivery_mode, handover_accepted
    """
    ctx = _resolve_context(job_context)
    completed: List[str] = []
    grasp_confidence = 0.0
    handover_accepted = False

    _publish(middleware, 'skill.started', {
        'profile': ctx.profile,
        'fetch_target': ctx.fetch_target,
        'destination': ctx.destination,
        'payload_kg': ctx.payload_kg,
        'delivery_mode': ctx.delivery_mode,
    })

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        # ── Safety gate: check at every primitive ─────────────────────────────
        safety = _read_state(middleware, 'state.safety_state')
        if safety.get('human_in_forbidden_zone'):
            _publish(middleware, 'skill.aborted', {
                'reason': 'human_in_forbidden_zone', 'at_primitive': primitive,
            })
            return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                    'at_primitive': primitive, 'primitives_completed': completed}

        # ── Balance gate: check if Atlas is stable ────────────────────────────
        balance = _read_state(middleware, 'state.balance_state')
        if not balance.get('stable', True):
            _publish(middleware, 'skill.aborted', {
                'reason': 'balance_loss_detected', 'at_primitive': primitive,
                'com_margin': balance.get('com_margin', 0),
            })
            return {'status': 'aborted', 'reason': 'balance_loss_detected',
                    'primitives_completed': completed}

        # ── Primitive-specific logic ──────────────────────────────────────────

        if primitive == 'localize_target':
            scene = _read_state(middleware, 'perception.scene_map')
            if not scene.get('map_ready', False):
                _publish(middleware, 'skill.aborted', {'reason': 'localization_failure'})
                return {'status': 'aborted', 'reason': 'localization_failure',
                        'primitives_completed': completed}
            obj_pose = _read_state(middleware, 'perception.object_pose')
            grasp_confidence = obj_pose.get('confidence', 0.0)

        elif primitive == 'plan_walk_path':
            _emit_intent(middleware, 'plan_walk_path', ctx, {
                'target': ctx.fetch_target,
                'avoid_obstacles': True,
                'human_aware_radius': ctx.human_aware_radius,
            })

        elif primitive == 'walk_to_target':
            _emit_intent(middleware, 'walk_to_target', ctx, {
                'target': ctx.fetch_target,
                'walk_speed_ms': ctx.walk_speed_ms,
                'body_mode': 'walk_stable',
            })
            _publish(middleware, 'locomotion.walking_started', {'target': ctx.fetch_target})
            # Simulate walking time proportional to distance
            dist = ((ctx.fetch_target.get('x', 0)**2 + ctx.fetch_target.get('y', 0)**2) ** 0.5)
            time.sleep(min(dist / max(ctx.walk_speed_ms, 0.1) * 0.001, 0.05))  # scaled for sim
            _publish(middleware, 'locomotion.target_reached', {'target': ctx.fetch_target})

        elif primitive == 'stabilize_stance':
            _emit_intent(middleware, 'stabilize_stance', ctx, {'body_mode': 'rigid_stable'})

        elif primitive == 'approach_object':
            obj_pose = _read_state(middleware, 'perception.object_pose')
            grasp_confidence = obj_pose.get('confidence', grasp_confidence)
            if grasp_confidence < ctx.grasp_confidence_min:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'grasp_confidence_low',
                    'confidence': grasp_confidence,
                    'required': ctx.grasp_confidence_min,
                })
                return {'status': 'aborted', 'reason': 'grasp_confidence_low',
                        'confidence': grasp_confidence, 'primitives_completed': completed}
            _emit_intent(middleware, 'approach_object', ctx, {
                'object_pose': obj_pose, 'arm_mode': ctx.arm_mode,
            })

        elif primitive == 'grasp_object':
            _emit_intent(middleware, 'grasp_object', ctx, {
                'force_window_n': list(ctx.force_window),
                'wrist_mode': ctx.wrist_mode,
            })
            _publish(middleware, 'grasp.contact_detected', {'payload_kg': ctx.payload_kg})
            time.sleep(0.05)
            _publish(middleware, 'grasp.object_secured', {
                'payload_kg': ctx.payload_kg, 'confidence': grasp_confidence,
            })

        elif primitive == 'secure_carry_posture':
            _emit_intent(middleware, 'secure_carry_posture', ctx, {
                'payload_kg': ctx.payload_kg,
                'body_mode': ctx.body_mode,
            })
            _publish(middleware, 'carry.balanced', {'payload_kg': ctx.payload_kg})

        elif primitive == 'walk_to_destination':
            _emit_intent(middleware, 'walk_to_destination', ctx, {
                'target': ctx.destination,
                'walk_speed_ms': ctx.walk_speed_ms * 0.85,  # slower when carrying
                'body_mode': ctx.body_mode,
            })
            _publish(middleware, 'locomotion.walking_started', {'target': ctx.destination})
            dist = ((ctx.destination.get('x', 0)**2 + ctx.destination.get('y', 0)**2) ** 0.5)
            time.sleep(min(dist / max(ctx.walk_speed_ms, 0.1) * 0.001, 0.05))
            _publish(middleware, 'locomotion.target_reached', {'target': ctx.destination})

        elif primitive == 'deposit_or_handover':
            if ctx.delivery_mode == 'handover':
                _publish(middleware, 'handover.offered', {
                    'human_id': job_context.get('humanId', 'unknown'),
                    'payload_kg': ctx.payload_kg,
                })
                deadline = time.time() + ctx.human_ready_timeout
                while time.time() < deadline:
                    human = _read_state(middleware, 'state.safety_state')
                    if human.get('human_ready_signal'):
                        handover_accepted = True
                        break
                    time.sleep(0.05)
                _emit_intent(middleware, 'handover_release', ctx, {
                    'wrist_mode': 'compliant_release', 'force_window_n': [2, 10],
                })
                _publish(middleware, 'handover.accepted' if handover_accepted else 'skill.aborted', {
                    'handover_accepted': handover_accepted,
                })
                if not handover_accepted:
                    return {'status': 'aborted', 'reason': 'handover_timeout',
                            'primitives_completed': completed}
            else:
                _emit_intent(middleware, 'deposit', ctx, {
                    'target': ctx.destination, 'release_mode': 'controlled',
                })
                _publish(middleware, 'delivery.deposited', {
                    'destination': ctx.destination, 'payload_kg': ctx.payload_kg,
                })

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {
        'delivery_mode': ctx.delivery_mode,
        'payload_kg': ctx.payload_kg,
        'handover_accepted': handover_accepted,
        'primitives_executed': len(completed),
    })
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'delivery_mode': ctx.delivery_mode,
        'payload_kg': ctx.payload_kg,
        'grasp_confidence': round(grasp_confidence, 3),
        'handover_accepted': handover_accepted,
        'primitives_executed': len(completed),
    }


if __name__ == '__main__':
    for profile in ['sequencing_carry', 'precision_fetch', 'human_handover']:
        print(f'\n--- Profile: {profile} ---')
        result = run({
            'chsProfile': profile,
            'fetchTarget': {'x': 3.0, 'y': 1.5, 'frame': 'world_map'},
            'deliveryDestination': {'x': 8.0, 'y': 0.0, 'frame': 'world_map'},
            'humanId': 'WORKER-01',
        })
        print(json.dumps(result, indent=2, default=str))
