"""CHS adapter for etd.inspect.vision — vision inspection / QA skill.

Key difference from pickplace/assembly:
  - No physical manipulation — camera-only skill
  - Structured scan path, multi-frame evidence capture
  - Confidence-gated classification
  - QA result reporting to workflow bus
  - CV model call is stubbed — replace with ONNX/TensorRT in production
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PRIMITIVE_ORDER = [
    'approach_viewpoint',
    'scan_target',
    'capture_evidence',
    'classify_result',
    'report_quality',
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'barcode_qa': {
        'scanMode': 'barcode',
        'captureCount': 3,
        'confidenceThreshold': 0.88,
        'bodyMode': 'stable_scan',
        'armMode': 'scan_arc',
        'wristMode': 'camera_align',
        'lightingMode': 'structured',
        'scanDwellMs': 400,
    },
    'defect_scan': {
        'scanMode': 'surface_defect',
        'captureCount': 6,
        'confidenceThreshold': 0.92,
        'bodyMode': 'micro_stable',
        'armMode': 'vision_sweep',
        'wristMode': 'camera_align',
        'lightingMode': 'uniform_diffuse',
        'scanDwellMs': 800,
    },
}


@dataclass
class InspectionContext:
    profile: str
    scan_mode: str
    capture_count: int
    confidence_threshold: float
    body_mode: str
    arm_mode: str
    wrist_mode: str
    lighting_mode: str
    scan_dwell_ms: int


@dataclass
class QCResult:
    pass_qc: bool
    confidence: float
    defects_found: List[Dict] = field(default_factory=list)
    captures: int = 0
    scan_mode: str = ''


def _resolve_context(job: Dict[str, Any]) -> InspectionContext:
    profile_name = job.get('chsProfile', 'barcode_qa')
    d = _PROFILE_DEFAULTS.get(profile_name, _PROFILE_DEFAULTS['barcode_qa'])
    return InspectionContext(
        profile=profile_name,
        scan_mode=job.get('scanMode', d['scanMode']),
        capture_count=job.get('captureCount', d['captureCount']),
        confidence_threshold=d['confidenceThreshold'],
        body_mode=d['bodyMode'], arm_mode=d['armMode'], wrist_mode=d['wristMode'],
        lighting_mode=d['lightingMode'], scan_dwell_ms=d['scanDwellMs'],
    )


def _classify_barcode(captures: List[Any]) -> QCResult:
    """Stub: in production call the barcode decoder service."""
    confidence = round(0.94 + random.uniform(-0.03, 0.03), 3)
    return QCResult(pass_qc=confidence >= 0.88, confidence=confidence,
                    captures=len(captures), scan_mode='barcode')


def _classify_defects(captures: List[Any]) -> QCResult:
    """Stub: in production call CV defect model (ONNX / TensorRT / remote inference API)."""
    confidence = round(0.93 + random.uniform(-0.04, 0.04), 3)
    defects: List[Dict] = []
    if random.random() < 0.08:
        defects.append({'type': 'scratch', 'bbox': [120, 80, 180, 110], 'severity': 'minor'})
    return QCResult(pass_qc=(len(defects) == 0 and confidence >= 0.92),
                    confidence=confidence, defects_found=defects,
                    captures=len(captures), scan_mode='surface_defect')


def _publish(middleware: Any, event: str, extra: Optional[Dict] = None) -> None:
    if hasattr(middleware, 'publish'):
        middleware.publish('telemetry.events', {'event': event, **(extra or {})})


def run(job_context: Dict[str, Any], middleware: Any = None) -> Dict[str, Any]:
    """ETD runtime entry point for vision inspection.

    Args:
        job_context: CHS dict — chsProfile, partId, scanMode, captureCount, ...
        middleware:  OEM adapter with .publish(topic, msg) and .read(topic)

    Returns:
        QA result: pass_qc, confidence, defects, captures
    """
    ctx = _resolve_context(job_context)
    captures: List[Dict] = []
    completed: List[str] = []
    qc_result: QCResult = QCResult(False, 0.0)

    def _safety_state() -> Dict[str, Any]:
        return (middleware.read('state.safety_state') or {}) if hasattr(middleware, 'read') else {}

    _publish(middleware, 'skill.started', {
        'profile': ctx.profile, 'scan_mode': ctx.scan_mode,
        'part_id': job_context.get('partId', 'unknown'),
    })

    for primitive in PRIMITIVE_ORDER:
        _publish(middleware, 'primitive.entered', {'primitive': primitive})

        safety = _safety_state()
        if safety.get('human_in_forbidden_zone'):
            _publish(middleware, 'skill.aborted', {
                'reason': 'human_in_forbidden_zone', 'at_primitive': primitive,
            })
            return {'status': 'aborted', 'reason': 'human_in_forbidden_zone',
                    'at_primitive': primitive, 'primitives_completed': completed}

        if primitive == 'scan_target':
            intent = {
                'type': 'command.skill_intent', 'primitive': 'scan_target',
                'body_mode': ctx.body_mode, 'arm_mode': ctx.arm_mode,
                'wrist_mode': ctx.wrist_mode, 'lighting_mode': ctx.lighting_mode,
                'timestamp': time.time(),
            }
            if hasattr(middleware, 'publish'):
                middleware.publish('command.skill_intent', intent)

        elif primitive == 'capture_evidence':
            dwell = ctx.scan_dwell_ms / 1000.0 / max(ctx.capture_count, 1)
            for i in range(ctx.capture_count):
                time.sleep(dwell)
                frame = middleware.read('perception.camera_frame') if hasattr(middleware, 'read') else None
                captures.append({'frame': i, 'timestamp': time.time(), 'source': frame})

        elif primitive == 'classify_result':
            qc_result = (_classify_barcode(captures) if ctx.scan_mode == 'barcode'
                         else _classify_defects(captures))
            if qc_result.confidence < ctx.confidence_threshold:
                _publish(middleware, 'skill.aborted', {
                    'reason': 'low_classification_confidence',
                    'confidence': qc_result.confidence,
                    'threshold': ctx.confidence_threshold,
                })
                return {
                    'status': 'aborted', 'reason': 'low_classification_confidence',
                    'confidence': qc_result.confidence, 'primitives_completed': completed,
                }

        elif primitive == 'report_quality':
            report = {
                'partId': job_context.get('partId', 'unknown'),
                'profile': ctx.profile, 'pass_qc': qc_result.pass_qc,
                'confidence': qc_result.confidence, 'defects': qc_result.defects_found,
                'captures': qc_result.captures, 'timestamp': time.time(),
            }
            if hasattr(middleware, 'publish'):
                middleware.publish('workflow.qc_report', report)

        completed.append(primitive)
        _publish(middleware, 'primitive.exited', {'primitive': primitive})

    _publish(middleware, 'skill.completed', {'pass_qc': qc_result.pass_qc})
    return {
        'status': 'completed', 'profile': ctx.profile,
        'pass_qc': qc_result.pass_qc, 'confidence': qc_result.confidence,
        'defects_found': qc_result.defects_found, 'captures_taken': qc_result.captures,
    }


if __name__ == '__main__':
    result = run({'chsProfile': 'defect_scan', 'partId': 'PART-0042'})
    print(json.dumps(result, indent=2, default=str))
