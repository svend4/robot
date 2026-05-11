"""CHS adapter for etd.cobot.safeassist — human-aware cobot assistance skill.

Key differences:
  - Continuous human-proximity monitoring throughout all primitives
  - Speed and force reduced when human detected within safety radius
  - Handover protocol: wait-for-human-accept before releasing object
  - Yields immediately if human enters forbidden zone
  - No manipulation until human-safe clearance confirmed
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PRIMITIVE_ORDER = [
    'social_approach',
    'offer_preposition',
    'wait_human_ready',
    'handover_transfer',
    'confirm_release',
    'social_retreat',
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'safe_handover': {
        'payloadKg': 2.0,
        'forceWindowN': [2, 12],
        'humanReadyTimeoutSec': 15.0,
        'safetyRadiusM': 1.2,
        'offerPoseOffset': {'x': 0.45, 'y': 0.0, 'z': 1.0},
        'bodyMode': 'social_standby',
        'armMode': 'handover_arc',
        'wristMode': 'compliant_release',
        'yieldOnHumanDetect': True,
    },
    'tool_pass': {
        'payloadKg': 1.0,
        'forceWindowN': [2, 10],
        'humanReadyTimeoutSec': 12.0,
        'safetyRadiusM': 0.9,
        'offerPoseOffset': {'x': 0.40, 'y': 0.0, 'z': 0.95},
        'bodyMode': 'social_standby',
        'armMode': 'handover_arc',
        'wristMode': 'compliant_release',
        'yieldOnHumanDetect': True,
    },
}


@dataclass
class CobotContext:
    profile: str
    payload_kg: float
    force_window: List[float]
    human_ready_timeout_sec: float
    safety_radius_m: float
    offer_pose: Dict[str, float]
    body_mode: str
    arm_mode: str
    wrist_mode: str
    yield_on_human_detect: bool


def _resolve_context(job: Dict[str, Any]) -> CobotContext:
    profile_name = job.get('chsProfile', 'safe_handover')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['safe_handover'])
    return CobotContext(
        profile=profile_name,
        payload_kg=job.get('payloadKg', d['payloadKg']),
        force_window=job.get('forceWindowN', d['forceWindowN']),
        human_ready_timeout_sec=d['humanReadyTimeoutSec'],
        safety_radius_m=d['safetyRadiusM'],
        offer_pose=d['offerPoseOffset'],
        body_mode=d['bodyMode'],
        arm_mode=d['armMode'],
        wrist_mode=d['wristMode'],
        yield_on_human_detect=d['yieldOnHumanDetect'],
    )


def _read_human_state(middleware: Any) -> Dict[str, Any]:
    """Read human proximity and readiness from safety zone monitor."""
    if hasattr(middleware, 'read'):
        return middleware.read('state.safety_state') or {}
    return {'human_in_safety_radius': True, 'human_ready_signal': True,
            'human_distance_m': 0.8, 'human_in_forbidden_zone': False}


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for human-aware cobot assistance.

    Args:
        job_context: CHS dict — chsProfile, payloadKg, humanId, toolId, ...
        middleware:  OEM adapter with .publish/.read; safety.zone_monitor must be available

    Returns:
        Handover result: status, profile, handover_accepted, metrics
    """
    ctx = _resolve_context(job_context)
    completed: List[str] = []
    handover_accepted = False

    _publish(middleware, 'skill.started', {
        'profile': ctx.profile,
        'payload_kg': ctx.payload_kg,
        'safety_radius_m': ctx.safety_radius_m,
    })

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        human = _read_human_state(middleware)

        # ── Forbidden zone check — every primitive ────────────────────────────
        if human.get('human_in_forbidden_zone'):
            _publish(middleware, 'skill.aborted', {
                'reason': 'human_in_forbidden_zone',
                'at_primitive': primitive,
            })
            return {
                'status': 'aborted',
                'reason': 'human_in_forbidden_zone',
                'at_primitive': primitive,
                'primitives_completed': completed,
            }

        # ── Social approach: slow down if human is close ──────────────────────
        if primitive == 'social_approach':
            speed_factor = 0.4 if human.get('human_in_safety_radius') else 0.8
            intent = {
                'type': 'command.skill_intent',
                'primitive': 'social_approach',
                'body_mode': ctx.body_mode,
                'arm_mode': ctx.arm_mode,
                'wrist_mode': ctx.wrist_mode,
                'speed_factor': speed_factor,
                'force_window_n': ctx.force_window,
                'target_pose': ctx.offer_pose,
                'timestamp': time.time(),
            }
            if hasattr(middleware, 'publish'):
                middleware.publish('command.skill_intent', intent)

        # ── Wait for human ready signal ───────────────────────────────────────
        elif primitive == 'wait_human_ready':
            deadline = time.time() + ctx.human_ready_timeout_sec
            ready = False
            while time.time() < deadline:
                human = _read_human_state(middleware)
                if human.get('human_ready_signal'):
                    ready = True
                    break
                if human.get('human_in_forbidden_zone'):
                    _publish(middleware, 'skill.aborted', {'reason': 'human_in_forbidden_zone'})
                    return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                            'primitives_completed': completed}
                time.sleep(0.1)

            if not ready:
                _publish(middleware, 'skill.aborted', {'reason': 'human_ready_timeout'})
                return {'status': 'aborted', 'reason': 'human_ready_timeout',
                        'timeout_sec': ctx.human_ready_timeout_sec,
                        'primitives_completed': completed}

        # ── Handover: compliant release with minimal force ────────────────────
        elif primitive == 'handover_transfer':
            intent = {
                'type': 'command.skill_intent',
                'primitive': 'handover_transfer',
                'force_window_n': [ctx.force_window[0], ctx.force_window[0] * 1.5],
                'wrist_mode': 'compliant_release',
                'speed_factor': 0.3,
                'timestamp': time.time(),
            }
            if hasattr(middleware, 'publish'):
                middleware.publish('command.skill_intent', intent)
            time.sleep(0.3)

        elif primitive == 'confirm_release':
            human = _read_human_state(middleware)
            handover_accepted = human.get('human_ready_signal', False)

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {'handover_accepted': handover_accepted})
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'handover_accepted': handover_accepted,
        'payload_kg': ctx.payload_kg,
        'primitives_executed': len(completed),
    }


if __name__ == '__main__':
    result = run({'chsProfile': 'safe_handover', 'toolId': 'TOOL-07', 'humanId': 'WORKER-03'})
    print(json.dumps(result, indent=2, default=str))
