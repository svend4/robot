"""ETD Reference Validator — validates a skill package against JSON schemas and semantic rules."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from jsonschema import Draft202012Validator
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

REQUIRED_FILES = [
    'manifest.yaml', 'skill.json', 'chs_profiles.json',
    'capabilities.json', 'execution_contract.json',
    'telemetry/events.json', 'tests/acceptance_tests.yaml',
]
FORBIDDEN_CAPS = frozenset({
    'command.servo_torque',
    'command.joint_limit_override',
    'command.collision_disable',
    'command.emergency_stop_override',
    'command.balance_core_override',
    'command.locomotion_override',
    'command.safety_zone_disable',
})
LIFECYCLE_EVENTS = frozenset({'skill.started', 'skill.completed', 'skill.aborted', 'skill.failed'})
SCHEMAS_DIR = Path(__file__).resolve().parent / 'schemas'

_SCHEMA_MAP: Dict[str, str] = {
    'manifest.yaml':           'manifest.schema.json',
    'skill.json':              'skill.schema.json',
    'chs_profiles.json':       'chs_profiles.schema.json',
    'capabilities.json':       'capabilities.schema.json',
    'execution_contract.json': 'execution_contract.schema.json',
}


@dataclass
class RuntimeContext:
    runtime_version: str = '0.1.0'
    robot_class: str = 'humanoid'
    available_services: List[str] = field(default_factory=list)
    platform_profile: str = 'generic'


@dataclass
class ValidationReport:
    valid: bool
    package_path: str
    schema: Dict[str, bool]
    schema_errors: Dict[str, List[str]]
    semantic_checks: Dict[str, bool]
    compatibility: Dict[str, Any]
    warnings: List[str]
    errors: List[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def _load(path: Path) -> Any:
    if path.suffix in ('.yaml', '.yml'):
        return yaml.safe_load(path.read_text(encoding='utf-8'))
    return json.loads(path.read_text(encoding='utf-8'))


def _load_schema(schema_filename: str) -> Optional[Dict]:
    schema_path = SCHEMAS_DIR / schema_filename
    if schema_path.exists():
        return json.loads(schema_path.read_text(encoding='utf-8'))
    return None


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split('.')[:3])
    except Exception:
        return (0, 0, 0)


def _min_runtime(spec: str) -> Optional[str]:
    m = re.search(r'>=\s*([0-9]+\.[0-9]+\.[0-9]+)', spec or '')
    return m.group(1) if m else None


def _jsonschema_validate(doc: Any, schema: Dict) -> List[str]:
    if not _JSONSCHEMA_AVAILABLE:
        return []
    errors: List[str] = []
    try:
        validator = Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
            path = ' -> '.join(str(p) for p in err.absolute_path) or '(root)'
            errors.append(f"{path}: {err.message}")
    except Exception as exc:
        errors.append(f"schema engine error: {exc}")
    return errors


class ETDReferenceValidator:
    def __init__(self, runtime_context: RuntimeContext):
        self.ctx = runtime_context

    def validate_package(self, package_path: str | Path) -> ValidationReport:
        p = Path(package_path)
        errors: List[str] = []
        warnings: List[str] = []

        schema_keys = ['manifest', 'skill', 'chs_profiles', 'capabilities', 'execution_contract']
        schema_results: Dict[str, bool] = {k: False for k in schema_keys}
        schema_errors: Dict[str, List[str]] = {k: [] for k in schema_keys}

        semantic = {k: False for k in [
            'required_files_present', 'name_matches_skill_id',
            'version_matches_skill_version', 'default_chs_profile_exists',
            'profile_uniqueness', 'entrypoint_exists',
            'telemetry_has_lifecycle_event', 'capability_safe',
            'primitive_order_nonempty', 'force_windows_valid',
            'payload_within_constraints', 'forbidden_caps_declared',
        ]}

        # ── Required files ────────────────────────────────────────────────────
        missing = [f for f in REQUIRED_FILES if not (p / f).exists()]
        if missing:
            errors += [f'missing required file: {x}' for x in missing]
        else:
            semantic['required_files_present'] = True

        # ── Parse ─────────────────────────────────────────────────────────────
        try:
            manifest   = _load(p / 'manifest.yaml')
            skill      = _load(p / 'skill.json')
            profiles   = _load(p / 'chs_profiles.json')
            caps       = _load(p / 'capabilities.json')
            contract   = _load(p / 'execution_contract.json')
            events_doc = _load(p / 'telemetry/events.json')
        except Exception as exc:
            errors.append(f'parse error: {exc}')
            return ValidationReport(
                False, str(p), schema_results, schema_errors, semantic,
                {'level': 'D', 'score': 0, 'warnings': [], 'errors': [str(exc)]},
                warnings, errors,
            )

        # ── JSON Schema validation ────────────────────────────────────────────
        if not _JSONSCHEMA_AVAILABLE:
            warnings.append('jsonschema not installed — schema validation skipped (pip install jsonschema)')

        file_schema_pairs = [
            ('manifest',          'manifest.yaml',           manifest),
            ('skill',             'skill.json',              skill),
            ('chs_profiles',      'chs_profiles.json',       profiles),
            ('capabilities',      'capabilities.json',       caps),
            ('execution_contract','execution_contract.json', contract),
        ]
        for key, schema_filename, doc in file_schema_pairs:
            schema_def = _load_schema(_SCHEMA_MAP[schema_filename])
            if schema_def is None:
                warnings.append(f'schema file not found for {schema_filename}')
                schema_results[key] = True  # non-blocking
                continue
            if not _JSONSCHEMA_AVAILABLE:
                # fall back to isinstance check only
                schema_results[key] = isinstance(doc, dict)
                continue
            errs = _jsonschema_validate(doc, schema_def)
            if errs:
                schema_errors[key] = errs
                errors.append(f'schema[{key}]: {len(errs)} violation(s)')
            else:
                schema_results[key] = True

        # ── Semantic checks ───────────────────────────────────────────────────
        meta = (manifest.get('metadata') or {}) if isinstance(manifest, dict) else {}

        semantic['name_matches_skill_id'] = (meta.get('name') == skill.get('skillId'))
        semantic['version_matches_skill_version'] = (meta.get('version') == skill.get('version'))

        profile_names = [x.get('name') for x in (profiles.get('profiles') or [])]
        semantic['profile_uniqueness'] = len(profile_names) == len(set(profile_names))
        semantic['default_chs_profile_exists'] = skill.get('defaultChsProfile') in profile_names

        ep_file = (skill.get('entrypoint') or '').split(':')[0]
        semantic['entrypoint_exists'] = bool(ep_file and (p / ep_file).exists())

        manifest_events = set((manifest.get('telemetry') or {}).get('events', []))
        file_events = set(events_doc.get('events', []))
        semantic['telemetry_has_lifecycle_event'] = bool(
            (manifest_events | file_events) & LIFECYCLE_EVENTS
        )

        write_caps = set(caps.get('write', []))
        declared_forbidden = set(caps.get('forbidden', []))
        semantic['capability_safe'] = (
            'command.skill_intent' in write_caps
            and not (write_caps & FORBIDDEN_CAPS)
        )
        semantic['forbidden_caps_declared'] = bool(declared_forbidden & FORBIDDEN_CAPS)

        semantic['primitive_order_nonempty'] = bool(skill.get('primitiveOrder'))

        semantic['force_windows_valid'] = all(
            ('forceWindowN' not in prof)
            or (len(prof['forceWindowN']) == 2 and prof['forceWindowN'][1] >= prof['forceWindowN'][0])
            for prof in (profiles.get('profiles') or [])
        )

        payload_max = (manifest.get('constraints') or {}).get('payloadKgMax')
        semantic['payload_within_constraints'] = (
            payload_max is None
            or all(prof.get('payloadKg', 0) <= payload_max for prof in (profiles.get('profiles') or []))
        )

        for k, v in semantic.items():
            if not v:
                errors.append(f'semantic check failed: {k}')

        # ── Compatibility scoring ─────────────────────────────────────────────
        compat_errors: List[str] = []
        compat_warnings: List[str] = []
        compat = (manifest.get('compatibility') or {})

        if self.ctx.robot_class not in compat.get('robotClass', []):
            compat_errors.append('robot_class_mismatch')

        avail = set(self.ctx.available_services)
        for svc in sorted(set(compat.get('requiresServices', [])) - avail):
            compat_errors.append(f'missing_service:{svc}')
        for svc in sorted(set(compat.get('optionalServices', [])) - avail):
            compat_warnings.append(f'missing_optional_service:{svc}')

        need = _min_runtime(compat.get('runtime', ''))
        if need and _version_tuple(self.ctx.runtime_version) < _version_tuple(need):
            compat_errors.append('runtime_too_old')

        score = max(0.0, 1.0 - 0.15 * len(compat_errors) - 0.03 * len(compat_warnings))
        level = 'D' if compat_errors else ('B' if compat_warnings else 'A')
        compatibility = {
            'level': level,
            'score': round(score, 2),
            'warnings': compat_warnings,
            'errors': compat_errors,
        }

        valid = not errors and level in ('A', 'B')
        return ValidationReport(
            valid, str(p), schema_results, schema_errors,
            semantic, compatibility, warnings, errors,
        )


def load_runtime_context(path: str | Path) -> RuntimeContext:
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    return RuntimeContext(**d)


_CONTEXT_SCHEMA_PATH = Path(__file__).resolve().parent / 'schemas' / 'runtime_context.schema.json'


def validate_runtime_context(path: str | Path) -> tuple[bool, list[str]]:
    """Validate a runtime_context.json file against the ETD context schema.

    Returns (valid: bool, errors: list[str]).
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not _JSONSCHEMA_AVAILABLE:
        return True, []
    schema = json.loads(_CONTEXT_SCHEMA_PATH.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(data)]
    return len(errors) == 0, errors


def main() -> None:
    ap = argparse.ArgumentParser(description='Validate an ETD skill package')
    ap.add_argument('package', help='Path to the skill package directory')
    ap.add_argument('--runtime-context', default='runtime_context.json')
    ap.add_argument('--output', choices=['json', 'pretty'], default='pretty')
    args = ap.parse_args()

    ctx = (
        load_runtime_context(args.runtime_context)
        if Path(args.runtime_context).exists()
        else RuntimeContext(available_services=[])
    )
    rep = ETDReferenceValidator(ctx).validate_package(args.package)

    if args.output == 'json':
        print(rep.to_json())
    else:
        status = 'PASS' if rep.valid else 'FAIL'
        print(f'ETD validation: {status}')
        print(rep.to_json())

    raise SystemExit(0 if rep.valid else 1)


if __name__ == '__main__':
    main()
