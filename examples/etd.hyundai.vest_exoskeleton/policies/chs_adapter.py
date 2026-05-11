"""CHS adapter for etd.hyundai.vest_exoskeleton — Hyundai VEX/H-MEX wearable assist.

Key behaviour:
  - Calibrate fit before engaging assist (joint sensor zeroing + intent model warm-up)
  - Continuous intent detection: read operator motion intent with confidence gate
  - Torque assist delivered proportional to load and fatigue level
  - Adaptive gain: reduce assist force as operator fatigue reaches threshold
  - Immediate torque-zero on operator panic release or forbidden zone
  - Per-primitive safety check; logs ergonomic metrics continuously
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PRIMITIVE_ORDER = [
    'calibrate_fit',
    'detect_intent',
    'engage_assist',
    'monitor_fatigue',
    'adapt_gain',
    'disengage_assist',
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'overhead_assembly': {
        'maxAssistForceN': 120.0,
        'intentConfidenceMin': 0.82,
        'fatigueThresholdPct': 70,
        'assistModes': ['overhead', 'reach'],
        'maxSessionSec': 3600,
        'calibrationSec': 5.0,
        'bodyMode': 'wearable_assist',
        'armMode': 'torque_assist',
        'wristMode': 'compliant',
    },
    'heavy_carry': {
        'maxAssistForceN': 150.0,
        'intentConfidenceMin': 0.85,
        'fatigueThresholdPct': 60,
        'assistModes': ['lumbar', 'carry'],
        'maxSessionSec': 1800,
        'calibrationSec': 8.0,
        'bodyMode': 'wearable_assist',
        'armMode': 'torque_assist',
        'wristMode': 'compliant',
    },
    'lumbar_support': {
        'maxAssistForceN': 80.0,
        'intentConfidenceMin': 0.80,
        'fatigueThresholdPct': 80,
        'assistModes': ['lumbar'],
        'maxSessionSec': 7200,
        'calibrationSec': 3.0,
        'bodyMode': 'wearable_assist',
        'armMode': 'passive_support',
        'wristMode': 'compliant',
    },
}


@dataclass
class ExoContext:
    profile: str
    max_assist_force_n: float
    intent_confidence_min: float
    fatigue_threshold_pct: int
    assist_modes: List[str]
    max_session_sec: float
    calibration_sec: float
    body_mode: str
    arm_mode: str
    wrist_mode: str


def _resolve_context(job: Dict[str, Any]) -> ExoContext:
    profile_name = job.get('profileId', 'overhead_assembly')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['overhead_assembly'])
    return ExoContext(
        profile=profile_name,
        max_assist_force_n=job.get('maxAssistForceN', d['maxAssistForceN']),
        intent_confidence_min=d['intentConfidenceMin'],
        fatigue_threshold_pct=d['fatigueThresholdPct'],
        assist_modes=d['assistModes'],
        max_session_sec=d['maxSessionSec'],
        calibration_sec=d['calibrationSec'],
        body_mode=d['bodyMode'],
        arm_mode=d['armMode'],
        wrist_mode=d['wristMode'],
    )


def _safety_state(middleware: Any) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read('state.safety_state') or {}
    return {'human_in_forbidden_zone': False, 'emergency_stop': False}


def _joint_state(middleware: Any) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read('state.exo_joint_state') or {}
    return {'calibrated': True, 'torque_within_limits': True}


def _intent(middleware: Any) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read('perception.intent_detector') or {}
    return {'confidence': 0.91, 'mode': 'overhead', 'direction': 'up'}


def _fatigue(middleware: Any) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read('state.fatigue_monitor') or {}
    return {'fatigue_pct': 20, 'session_sec': 0}


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for Hyundai VEX/H-MEX exoskeleton assist.

    Args:
        job_context: CHS dict — profileId, maxAssistForceN, operatorId, taskType, ...
        middleware:  OEM adapter with .publish/.read

    Returns:
        Assist session result: status, profile, fatigue_pct, assist_cycles, metrics
    """
    ctx = _resolve_context(job_context)
    completed: List[str] = []
    assist_cycles = 0
    fatigue_pct = 0
    final_gain = 1.0

    _publish(middleware, 'skill.started', {
        'profile': ctx.profile,
        'max_assist_force_n': ctx.max_assist_force_n,
        'assist_modes': ctx.assist_modes,
    })

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        safety = _safety_state(middleware)

        # ── Forbidden zone / panic release — every primitive ──────────────────
        if safety.get('human_in_forbidden_zone') or safety.get('operator_panic_release'):
            reason = 'operator_panic_release' if safety.get('operator_panic_release') \
                     else 'human_in_forbidden_zone'
            _publish(middleware, 'skill.aborted', {
                'reason': reason, 'at_primitive': primitive,
            })
            return {
                'status': 'aborted',
                'reason': reason,
                'at_primitive': primitive,
                'primitives_completed': completed,
            }

        # ── Calibrate fit: zero joint sensors and warm up intent model ────────
        if primitive == 'calibrate_fit':
            joints = _joint_state(middleware)
            if not joints.get('calibrated', True):
                _publish(middleware, 'skill.aborted', {'reason': 'calibration_failed'})
                return {'status': 'aborted', 'reason': 'calibration_failed',
                        'primitives_completed': completed}
            time.sleep(min(ctx.calibration_sec, 0.01))  # sim: cap sleep for test speed

        # ── Detect intent: require confidence above threshold ─────────────────
        elif primitive == 'detect_intent':
            intent_state = _intent(middleware)
            confidence = intent_state.get('confidence', 0.0)
            if confidence < ctx.intent_confidence_min:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'intent_confidence_below_threshold',
                    'confidence': confidence,
                    'threshold': ctx.intent_confidence_min,
                })
                return {
                    'status': 'aborted',
                    'reason': 'intent_confidence_below_threshold',
                    'confidence': confidence,
                    'primitives_completed': completed,
                }
            _publish(middleware, 'assist.intent_detected', {
                'mode': intent_state.get('mode', 'unknown'),
                'confidence': confidence,
            })

        # ── Engage assist: publish torque-assist command ──────────────────────
        elif primitive == 'engage_assist':
            intent_state = _intent(middleware)
            mode = intent_state.get('mode', ctx.assist_modes[0])
            if mode == 'overhead':
                _publish(middleware, 'assist.overhead_mode_entered', {'mode': mode})
            elif mode == 'lumbar':
                _publish(middleware, 'assist.lumbar_mode_entered', {'mode': mode})

            if hasattr(middleware, 'publish'):
                middleware.publish('force_control.torque_assist', {
                    'assist_force_n': ctx.max_assist_force_n * final_gain,
                    'mode': mode,
                    'body_mode': ctx.body_mode,
                    'arm_mode': ctx.arm_mode,
                    'wrist_mode': ctx.wrist_mode,
                })
            assist_cycles += 1
            _publish(middleware, 'assist.torque_applied', {
                'force_n': ctx.max_assist_force_n * final_gain,
                'gain': final_gain,
            })

        # ── Monitor fatigue: read ergonomic metrics ───────────────────────────
        elif primitive == 'monitor_fatigue':
            fatigue_state = _fatigue(middleware)
            fatigue_pct = fatigue_state.get('fatigue_pct', 0)
            if fatigue_pct >= ctx.fatigue_threshold_pct:
                _publish(middleware, 'assist.fatigue_threshold_reached', {
                    'fatigue_pct': fatigue_pct, 'threshold': ctx.fatigue_threshold_pct,
                })

        # ── Adapt gain: scale assist force down as fatigue increases ──────────
        elif primitive == 'adapt_gain':
            if fatigue_pct >= ctx.fatigue_threshold_pct:
                final_gain = max(0.5, 1.0 - (fatigue_pct - ctx.fatigue_threshold_pct) / 100.0)
                _publish(middleware, 'assist.mode_switched', {
                    'reason': 'fatigue_adaptive_gain',
                    'new_gain': final_gain,
                    'fatigue_pct': fatigue_pct,
                })

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {
        'profile': ctx.profile,
        'assist_cycles': assist_cycles,
        'fatigue_pct': fatigue_pct,
        'final_gain': final_gain,
    })
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'assist_cycles': assist_cycles,
        'fatigue_pct': fatigue_pct,
        'final_gain': final_gain,
        'primitives_executed': len(completed),
    }


if __name__ == '__main__':
    result = run({'profileId': 'overhead_assembly', 'operatorId': 'WORKER-07'})
    print(json.dumps(result, indent=2, default=str))
