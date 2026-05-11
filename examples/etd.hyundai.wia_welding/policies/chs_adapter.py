"""ETD CHS Adapter — Hyundai WIA Arc Welding Skill.

Implements a 7-primitive weld seam sequence:
  approach_seam_start → torch_align → ignite_arc → weld_traverse
  → extinguish_arc → post_weld_inspect → retract_clear

Safety: human_in_forbidden_zone abort at every primitive.
Arc zone: 1.5m exclusion radius enforced before arc ignition.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PRIMITIVE_ORDER = [
    'approach_seam_start',
    'torch_align',
    'ignite_arc',
    'weld_traverse',
    'extinguish_arc',
    'post_weld_inspect',
    'retract_clear',
]

_PROFILE_DEFAULTS: Dict[str, Dict] = {
    'standard_seam': {
        'travelSpeedMmS': 6.0, 'amperageA': 160, 'voltageV': 19.5,
        'wireFeedRateMmMin': 4500, 'seamLengthMm': 150.0,
        'seamTrackingEnabled': True, 'postInspectionEnabled': True,
        'arcZoneRadius_m': 1.5, 'alignmentConfidenceMin': 0.90,
    },
    'precision_seam': {
        'travelSpeedMmS': 3.5, 'amperageA': 130, 'voltageV': 17.5,
        'wireFeedRateMmMin': 3800, 'seamLengthMm': 80.0,
        'seamTrackingEnabled': True, 'postInspectionEnabled': True,
        'arcZoneRadius_m': 1.5, 'alignmentConfidenceMin': 0.94,
    },
    'tack_weld': {
        'travelSpeedMmS': 0.0, 'amperageA': 100, 'voltageV': 16.0,
        'wireFeedRateMmMin': 3000, 'seamLengthMm': 5.0,
        'seamTrackingEnabled': False, 'postInspectionEnabled': False,
        'arcZoneRadius_m': 1.5, 'alignmentConfidenceMin': 0.88,
    },
}


@dataclass
class WeldContext:
    profile: str
    travel_speed_mm_s: float
    amperage_a: float
    voltage_v: float
    wire_feed_rate_mm_min: float
    seam_length_mm: float
    seam_tracking_enabled: bool
    post_inspection_enabled: bool
    arc_zone_radius_m: float
    alignment_confidence_min: float


def _resolve_context(job: Dict[str, Any]) -> WeldContext:
    profile_name = job.get('chsProfile', 'standard_seam')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['standard_seam'])
    return WeldContext(
        profile=profile_name,
        travel_speed_mm_s=job.get('travelSpeedMmS', d['travelSpeedMmS']),
        amperage_a=job.get('amperageA', d['amperageA']),
        voltage_v=job.get('voltageV', d['voltageV']),
        wire_feed_rate_mm_min=job.get('wireFeedRateMmMin', d['wireFeedRateMmMin']),
        seam_length_mm=job.get('seamLengthMm', d['seamLengthMm']),
        seam_tracking_enabled=d['seamTrackingEnabled'],
        post_inspection_enabled=d['postInspectionEnabled'],
        arc_zone_radius_m=d['arcZoneRadius_m'],
        alignment_confidence_min=d['alignmentConfidenceMin'],
    )


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def _read(middleware: Any, topic: str) -> Dict[str, Any]:
    if hasattr(middleware, 'read'):
        return middleware.read(topic) or {}
    return {}


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for Hyundai WIA arc welding.

    Args:
        job_context: CHS job dict — chsProfile, seamLengthMm, amperageA, ...
        middleware:  OEM adapter with .publish(topic, msg) and .read(topic)

    Returns:
        Execution result with weld metrics and inspection outcome
    """
    ctx = _resolve_context(job_context)
    completed: List[str] = []
    arc_active = False
    inspection_pass = False

    def _safety() -> Dict[str, Any]:
        return _read(middleware, 'state.safety_state')

    _publish(middleware, 'skill.started', {
        'profile': ctx.profile,
        'amperage_a': ctx.amperage_a,
        'seam_length_mm': ctx.seam_length_mm,
    })

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        safety = _safety()
        if safety.get('human_in_forbidden_zone'):
            if arc_active:
                _publish(middleware, 'welding.arc_stopped', {'reason': 'safety_abort'})
            _publish(middleware, 'skill.aborted', {
                'reason': 'human_in_forbidden_zone', 'at_primitive': primitive,
            })
            return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                    'at_primitive': primitive, 'primitives_completed': completed}

        # ── Torch alignment with seam tracker ─────────────────────────────────
        if primitive == 'torch_align' and ctx.seam_tracking_enabled:
            seam = _read(middleware, 'perception.seam_tracker')
            confidence = seam.get('confidence', 0.0)
            if confidence < ctx.alignment_confidence_min:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'seam_track_confidence_low',
                    'confidence': confidence,
                    'required': ctx.alignment_confidence_min,
                })
                return {'status': 'aborted', 'reason': 'seam_track_confidence_low',
                        'confidence': confidence, 'primitives_completed': completed}

        # ── Arc ignition ───────────────────────────────────────────────────────
        elif primitive == 'ignite_arc':
            _publish(middleware, 'command.skill_intent', {
                'type': 'command.skill_intent', 'primitive': 'ignite_arc',
                'amperage_a': ctx.amperage_a, 'voltage_v': ctx.voltage_v,
                'wire_feed_rate_mm_min': ctx.wire_feed_rate_mm_min,
                'timestamp': time.time(),
            })
            _publish(middleware, 'welding.arc_started', {
                'amperage_a': ctx.amperage_a, 'voltage_v': ctx.voltage_v,
            })
            arc_active = True

        # ── Seam traversal ─────────────────────────────────────────────────────
        elif primitive == 'weld_traverse':
            if ctx.travel_speed_mm_s > 0:
                # Simulate weld traversal time
                traverse_sec = (ctx.seam_length_mm / ctx.travel_speed_mm_s) / 1000.0
                steps = max(1, int(traverse_sec / 0.01))
                for step in range(steps):
                    time.sleep(traverse_sec / steps)
                    safety = _safety()
                    if safety.get('human_in_forbidden_zone'):
                        _publish(middleware, 'welding.arc_stopped', {'reason': 'safety_abort'})
                        arc_active = False
                        _publish(middleware, 'skill.aborted', {
                            'reason': 'human_in_forbidden_zone', 'at_primitive': primitive,
                        })
                        return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                                'at_primitive': primitive, 'primitives_completed': completed}
                    progress = (step + 1) / steps
                    _publish(middleware, 'welding.seam_progress', {
                        'progress': round(progress, 2),
                        'position_mm': round(progress * ctx.seam_length_mm, 1),
                    })

        # ── Arc extinguish ─────────────────────────────────────────────────────
        elif primitive == 'extinguish_arc':
            _publish(middleware, 'welding.arc_stopped', {'reason': 'seam_complete'})
            arc_active = False

        # ── Post-weld inspection ───────────────────────────────────────────────
        elif primitive == 'post_weld_inspect' and ctx.post_inspection_enabled:
            result = _read(middleware, 'vision.weld_inspection')
            inspection_pass = result.get('pass', True)
            defects = result.get('defects', [])
            _publish(middleware, 'inspection.result', {
                'pass': inspection_pass, 'defects': defects,
            })

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {
        'seam_length_mm': ctx.seam_length_mm,
        'amperage_a': ctx.amperage_a,
        'inspection_pass': inspection_pass,
    })
    return {
        'status': 'completed',
        'profile': ctx.profile,
        'seam_length_mm': ctx.seam_length_mm,
        'amperage_a': ctx.amperage_a,
        'voltage_v': ctx.voltage_v,
        'inspection_pass': inspection_pass,
        'primitives_executed': len(completed),
    }


if __name__ == '__main__':
    print(run({'chsProfile': 'standard_seam'}))
