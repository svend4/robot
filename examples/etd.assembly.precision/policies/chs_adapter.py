"""CHS adapter for etd.assembly.precision — precision insertion/assembly skill.

Key difference from pickplace:
  - Force-controlled insertion phases (peg-in-hole, connector)
  - Vision alignment stage before insertion
  - Contact seek with adaptive force ramp
  - Rejection if alignment confidence is below threshold
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

PRIMITIVE_ORDER = [
    'approach_preposition',
    'vision_align',
    'contact_seek',
    'insertion_push',
    'seat_verify',
    'retract_clear',
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'peg_in_hole': {
        'payloadKg': 0.8,
        'forceWindowN': [5, 20],
        'targetDepthMm': 18,
        'precisionMm': 0.5,
        'alignmentConfidenceMin': 0.90,
        'bodyMode': 'rigid_stable',
        'armMode': 'insertion_axis_hold',
        'wristMode': 'micro_adjust',
        'insertionSpeedMmS': 2.0,
        'seatForceN': 15.0,
    },
    'connector_insert': {
        'payloadKg': 0.4,
        'forceWindowN': [4, 15],
        'targetDepthMm': 12,
        'precisionMm': 0.3,
        'alignmentConfidenceMin': 0.92,
        'bodyMode': 'micro_stable',
        'armMode': 'slow_axis_approach',
        'wristMode': 'soft_contact',
        'insertionSpeedMmS': 1.5,
        'seatForceN': 10.0,
    },
}

MIN_CONFIDENCE = 0.82


@dataclass
class AssemblyContext:
    profile: str
    payload_kg: float
    force_window: Tuple[float, float]
    target_depth_mm: float
    precision_mm: float
    alignment_confidence_min: float
    body_mode: str
    arm_mode: str
    wrist_mode: str
    insertion_speed_mm_s: float
    seat_force_n: float


def _resolve_context(job: Dict[str, Any]) -> AssemblyContext:
    profile_name = job.get('chsProfile', 'peg_in_hole')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['peg_in_hole'])
    return AssemblyContext(
        profile=profile_name,
        payload_kg=job.get('payloadKg', d['payloadKg']),
        force_window=tuple(job.get('forceWindowN', d['forceWindowN'])),
        target_depth_mm=job.get('targetDepthMm', d['targetDepthMm']),
        precision_mm=job.get('precisionMm', d['precisionMm']),
        alignment_confidence_min=d['alignmentConfidenceMin'],
        body_mode=d['bodyMode'],
        arm_mode=d['armMode'],
        wrist_mode=d['wristMode'],
        insertion_speed_mm_s=d['insertionSpeedMmS'],
        seat_force_n=d['seatForceN'],
    )


def _read_perception(middleware: Any, topic: str) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read(topic) or {}
    # Simulation defaults
    return {'confidence': 0.95, 'offset_mm': 0.2, 'aligned': True}


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for precision assembly.

    Args:
        job_context: CHS job dict — chsProfile, payloadKg, targetDepthMm, ...
        middleware:  OEM adapter with .publish(topic, msg) and .read(topic)

    Returns:
        Execution result with insertion metrics
    """
    ctx = _resolve_context(job_context)
    completed: List[str] = []

    _publish(middleware, 'skill.started', {'profile': ctx.profile, 'precision_mm': ctx.precision_mm})

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        # ── Vision alignment gate ─────────────────────────────────────────────
        if primitive == 'vision_align':
            perception = _read_perception(middleware, 'perception.part_alignment')
            confidence = perception.get('confidence', 0.0)
            offset_mm = perception.get('offset_mm', 99.0)

            if confidence < ctx.alignment_confidence_min:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'alignment_confidence_below_threshold',
                    'confidence': confidence,
                    'required': ctx.alignment_confidence_min,
                })
                return {
                    'status': 'aborted',
                    'reason': 'alignment_confidence_below_threshold',
                    'confidence': confidence,
                    'primitives_completed': completed,
                }

            if offset_mm > ctx.precision_mm * 3:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'alignment_offset_too_large',
                    'offset_mm': offset_mm,
                    'limit_mm': ctx.precision_mm * 3,
                })
                return {
                    'status': 'aborted',
                    'reason': 'alignment_offset_too_large',
                    'offset_mm': offset_mm,
                    'primitives_completed': completed,
                }

        # ── Force-controlled insertion ────────────────────────────────────────
        elif primitive == 'insertion_push':
            intent = {
                'type': 'command.skill_intent',
                'primitive': 'insertion_push',
                'force_window_n': list(ctx.force_window),
                'target_depth_mm': ctx.target_depth_mm,
                'speed_mm_s': ctx.insertion_speed_mm_s,
                'body_mode': ctx.body_mode,
                'arm_mode': ctx.arm_mode,
                'wrist_mode': ctx.wrist_mode,
                'timestamp': time.time(),
            }
            if hasattr(middleware, 'publish'):
                middleware.publish('command.skill_intent', intent)

        # ── Seating verification ──────────────────────────────────────────────
        elif primitive == 'seat_verify':
            contact = _read_perception(middleware, 'force_control.contact_feedback')
            current_force = contact.get('normal_force_n', 0.0)
            if current_force < ctx.seat_force_n * 0.8:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'insufficient_seating_force',
                    'measured_n': current_force,
                    'required_n': ctx.seat_force_n,
                })
                return {
                    'status': 'aborted',
                    'reason': 'insufficient_seating_force',
                    'measured_force_n': current_force,
                    'primitives_completed': completed,
                }

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {
        'target_depth_mm': ctx.target_depth_mm,
        'seat_force_n': ctx.seat_force_n,
    })
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'target_depth_mm': ctx.target_depth_mm,
        'precision_mm': ctx.precision_mm,
        'primitives_executed': len(completed),
    }


if __name__ == '__main__':
    result = run({'chsProfile': 'peg_in_hole'})
    print(json.dumps(result, indent=2, default=str))
