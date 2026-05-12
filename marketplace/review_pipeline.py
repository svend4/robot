"""ETD Automated Review Pipeline — pre-publication package audit.

On submission, runs four sequential checks and produces a structured
``ReviewResult``. Human review is required when ``riskLevel: high`` or
when the safety boundary check finds issues.

Pipeline stages
---------------
1. **Schema validation** — ``ETDReferenceValidator`` with a generic context.
   Blocks if any schema or semantic check fails.
2. **Capability audit** — verifies that `command.skill_intent` is in the
   write list, no forbidden capabilities are written, and all declared
   forbidden caps are from the ETD forbidden set.
3. **Safety boundary check** — inspects risk level, payload limits, force
   window values, and human-aware constraints.
4. **Compatibility matrix** — lists which robot classes and station profiles
   the package is compatible with given the declared service requirements.

Usage::

    from marketplace.review_pipeline import ReviewPipeline
    from pathlib import Path

    result = ReviewPipeline().run(Path('examples/etd.hyundai.wia_welding'))
    print(result.summary())
    if result.human_review_required:
        print('⚠ Manual review required')
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from etd_reference_validator import (
    ETDReferenceValidator,
    FORBIDDEN_CAPS,
    RuntimeContext,
)

_REQUIRED_WRITE_CAP = 'command.skill_intent'

_HIGH_RISK_FORBIDDEN_WRITE = frozenset({
    'command.servo_torque',
    'command.joint_limit_override',
    'command.collision_disable',
    'command.emergency_stop_override',
    'command.balance_core_override',
    'command.locomotion_override',
    'command.safety_zone_disable',
})

_ALL_ROBOT_CLASSES = [
    'humanoid', 'mobile_manipulator', 'fixed_manipulator',
    'dual_arm', 'amr', 'exoskeleton', 'cobot',
]


@dataclass
class StageResult:
    name: str
    passed: bool = False
    findings: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    skill_id: str
    version: str
    package_path: str
    stages: List[StageResult] = field(default_factory=list)
    compat_matrix: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = 'unknown'
    human_review_required: bool = False

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.stages)

    @property
    def blocking_findings(self) -> List[str]:
        findings = []
        for s in self.stages:
            if not s.passed:
                findings.extend(s.findings)
        return findings

    def summary(self) -> str:
        status = 'PASS' if self.passed else 'FAIL'
        lines = [
            f'Review: {status}  |  {self.skill_id} v{self.version}',
            f'Risk level: {self.risk_level}  |  Human review: {"yes" if self.human_review_required else "no"}',
        ]
        for s in self.stages:
            mark = '✓' if s.passed else '✗'
            lines.append(f'  {mark} {s.name}')
            for f in s.findings:
                lines.append(f'      ! {f}')
            for w in s.warnings:
                lines.append(f'      ~ {w}')
        if self.compat_matrix:
            lines.append(f'  Compatible robot classes : {", ".join(self.compat_matrix.get("robot_classes", []))}')
            lines.append(f'  Compatible station count : {self.compat_matrix.get("station_count", 0)}')
        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'version': self.version,
            'package_path': self.package_path,
            'passed': self.passed,
            'risk_level': self.risk_level,
            'human_review_required': self.human_review_required,
            'stages': [
                {
                    'name': s.name,
                    'passed': s.passed,
                    'findings': s.findings,
                    'warnings': s.warnings,
                }
                for s in self.stages
            ],
            'compat_matrix': self.compat_matrix,
        }


class ReviewPipeline:
    """Run the automated ETD package review pipeline.

    Parameters
    ----------
    station_profiles_dir:
        Path to the directory containing station profile JSON files.
        Defaults to ``<repo_root>/station_profiles``.
    """

    def __init__(self, station_profiles_dir: Optional[Path] = None) -> None:
        _root = Path(__file__).resolve().parents[1]
        self._station_dir = station_profiles_dir or (_root / 'station_profiles')

    def run(self, package_path: Path) -> ReviewResult:
        """Execute all pipeline stages and return a ``ReviewResult``."""
        p = package_path if isinstance(package_path, Path) else Path(package_path)

        # Parse manifest and skill.json for metadata
        manifest = _load(p / 'manifest.yaml') if (p / 'manifest.yaml').exists() else {}
        skill = _load(p / 'skill.json') if (p / 'skill.json').exists() else {}
        caps = _load(p / 'capabilities.json') if (p / 'capabilities.json').exists() else {}
        profiles_doc = _load(p / 'chs_profiles.json') if (p / 'chs_profiles.json').exists() else {}

        meta = (manifest.get('metadata') or {}) if isinstance(manifest, dict) else {}
        skill_id = meta.get('name', skill.get('skillId', p.name))
        version = meta.get('version', skill.get('version', '0.0.0'))
        risk_level = meta.get('riskLevel', skill.get('riskLevel', 'unknown'))

        result = ReviewResult(
            skill_id=skill_id,
            version=version,
            package_path=str(p),
            risk_level=risk_level,
        )

        result.stages.append(self._stage_schema(p))
        result.stages.append(self._stage_capabilities(caps))
        result.stages.append(self._stage_safety(manifest, profiles_doc, risk_level))
        result.compat_matrix = self._build_compat_matrix(manifest, caps)

        result.human_review_required = (
            risk_level == 'high'
            or not result.passed
            or any(not s.passed for s in result.stages)
        )

        return result

    # ── Stage 1: Schema validation ────────────────────────────────────────────

    def _stage_schema(self, p: Path) -> StageResult:
        stage = StageResult(name='schema_validation')
        ctx = RuntimeContext(
            available_services=list(_ALL_SERVICES),
            robot_class='humanoid',
        )
        try:
            report = ETDReferenceValidator(ctx).validate_package(p)
            if report.valid:
                stage.passed = True
            else:
                stage.findings.extend(report.errors[:10])  # cap at 10
                stage.warnings.extend(report.warnings)
        except Exception as exc:
            stage.findings.append(f'validator_exception: {exc}')
        return stage

    # ── Stage 2: Capability audit ─────────────────────────────────────────────

    def _stage_capabilities(self, caps: Dict[str, Any]) -> StageResult:
        stage = StageResult(name='capability_audit')
        findings = []
        warnings = []

        write_caps = set(caps.get('write', []))
        declared_forbidden = set(caps.get('forbidden', []))

        if _REQUIRED_WRITE_CAP not in write_caps:
            findings.append(f'missing required write cap: {_REQUIRED_WRITE_CAP}')

        bad_write = write_caps & _HIGH_RISK_FORBIDDEN_WRITE
        if bad_write:
            findings.append(f'forbidden caps in write list: {sorted(bad_write)}')

        undeclared_forbidden = (write_caps & FORBIDDEN_CAPS) - declared_forbidden
        if undeclared_forbidden:
            warnings.append(
                f'forbidden caps used but not declared in "forbidden" list: '
                f'{sorted(undeclared_forbidden)}'
            )

        extra_forbidden = declared_forbidden - FORBIDDEN_CAPS
        if extra_forbidden:
            warnings.append(f'declared forbidden not in ETD standard set: {sorted(extra_forbidden)}')

        stage.findings = findings
        stage.warnings = warnings
        stage.passed = len(findings) == 0
        return stage

    # ── Stage 3: Safety boundary check ───────────────────────────────────────

    def _stage_safety(
        self,
        manifest: Dict[str, Any],
        profiles_doc: Dict[str, Any],
        risk_level: str,
    ) -> StageResult:
        stage = StageResult(name='safety_boundary')
        findings = []
        warnings = []

        if risk_level == 'high':
            warnings.append('riskLevel=high: human review mandatory')

        constraints = (manifest.get('constraints') or {}) if isinstance(manifest, dict) else {}
        payload_max = constraints.get('payloadKgMax')

        for prof in (profiles_doc.get('profiles') or []):
            pw = prof.get('forceWindowN')
            if pw and isinstance(pw, list) and len(pw) == 2:
                if pw[0] < 0:
                    findings.append(f'profile {prof.get("name","?")}: negative force window lower bound')
                if pw[1] < pw[0]:
                    findings.append(f'profile {prof.get("name","?")}: force window upper < lower')
                if pw[1] > 500:
                    warnings.append(f'profile {prof.get("name","?")}: force window upper > 500N (high force)')

            if payload_max is not None and prof.get('payloadKg', 0) > payload_max:
                findings.append(
                    f'profile {prof.get("name","?")}: payloadKg {prof["payloadKg"]} '
                    f'exceeds constraint {payload_max}'
                )

            if prof.get('arcZoneRadius_m', 1.0) < 1.0:
                findings.append(
                    f'profile {prof.get("name","?")}: arcZoneRadius_m < 1.0m (safety minimum)'
                )

        stage.findings = findings
        stage.warnings = warnings
        stage.passed = len(findings) == 0
        return stage

    # ── Stage 4: Compatibility matrix ─────────────────────────────────────────

    def _build_compat_matrix(
        self,
        manifest: Dict[str, Any],
        caps: Dict[str, Any],
    ) -> Dict[str, Any]:
        compat = (manifest.get('compatibility') or {}) if isinstance(manifest, dict) else {}
        declared_classes = compat.get('robotClass', [])
        required_services = set(compat.get('requiresServices', []))
        optional_services = set(compat.get('optionalServices', []))
        runtime_req = compat.get('runtime', '')

        # Load station profiles and check compatibility
        compatible_stations = []
        for profile_file in sorted(self._station_dir.glob('*.json')):
            try:
                profile = json.loads(profile_file.read_text(encoding='utf-8'))
                profile_services = set(profile.get('availableServices', []))
                if required_services.issubset(profile_services):
                    compatible_stations.append(profile.get('stationId', profile_file.stem))
            except Exception:
                pass

        return {
            'robot_classes': declared_classes,
            'required_services': sorted(required_services),
            'optional_services': sorted(optional_services),
            'runtime_constraint': runtime_req,
            'compatible_stations': compatible_stations,
            'station_count': len(compatible_stations),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(path: Path) -> Any:
    if path.suffix in ('.yaml', '.yml'):
        return yaml.safe_load(path.read_text(encoding='utf-8'))
    return json.loads(path.read_text(encoding='utf-8'))


# Broad service set for schema-validation stage (we want to test against a
# permissive context so we see schema issues not missing-service issues)
_ALL_SERVICES = [
    'manipulation.arm_control', 'perception.part_alignment', 'perception.object_pose',
    'force_control.contact_feedback', 'workflow.job_context', 'state.robot_pose',
    'state.arm_state', 'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
    'perception.seam_tracker', 'welding.torch_control', 'welding.arc_monitor',
    'state.exo_joint_state', 'state.fatigue_monitor', 'perception.intent_detector',
    'force_control.torque_assist', 'state.balance_state', 'perception.scene_map',
    'navigation.waypoints', 'state.robot_pose', 'state.battery',
    'telemetry.events', 'telemetry.metrics', 'workflow.qc_report', 'vision.weld_inspection',
]
