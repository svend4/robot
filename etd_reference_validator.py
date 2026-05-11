from __future__ import annotations
import argparse, json, re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

REQUIRED = ['manifest.yaml','skill.json','chs_profiles.json','capabilities.json','execution_contract.json','telemetry/events.json','tests/acceptance_tests.yaml']
FORBIDDEN = {'command.servo_torque','command.joint_limit_override','command.collision_disable','command.emergency_stop_override','command.balance_core_override'}
LIFECYCLE = {'skill.started','skill.completed','skill.aborted','skill.failed'}

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
    schema: Dict[str,bool]
    semantic_checks: Dict[str,bool]
    compatibility: Dict[str,Any]
    warnings: List[str]
    errors: List[str]
    def to_json(self): return json.dumps(asdict(self), indent=2, ensure_ascii=False)

def load(path: Path):
    if path.suffix in ('.yaml','.yml'):
        return yaml.safe_load(path.read_text(encoding='utf-8'))
    return json.loads(path.read_text(encoding='utf-8'))

def version_tuple(v: str):
    try: return tuple(int(x) for x in v.split('.')[:3])
    except Exception: return (0,0,0)

def min_runtime(spec: str) -> str | None:
    m = re.search(r'>=\s*([0-9]+\.[0-9]+\.[0-9]+)', spec or '')
    return m.group(1) if m else None

class ETDReferenceValidator:
    def __init__(self, runtime_context: RuntimeContext):
        self.ctx = runtime_context
    def validate_package(self, package_path: str | Path) -> ValidationReport:
        p = Path(package_path)
        errors, warnings = [], []
        schema = {k: False for k in ['manifest','skill','chs_profiles','capabilities','execution_contract']}
        semantic = {k: False for k in ['required_files_present','name_matches_skill_id','version_matches_skill_version','default_chs_profile_exists','profile_uniqueness','entrypoint_exists','telemetry_has_lifecycle_event','capability_safe','primitive_order_nonempty','force_windows_valid','payload_within_constraints']}
        missing = [f for f in REQUIRED if not (p/f).exists()]
        if missing: errors += [f'missing required file: {x}' for x in missing]
        else: semantic['required_files_present'] = True
        try:
            manifest, skill, profiles, caps, contract, events = [load(p/x) for x in ['manifest.yaml','skill.json','chs_profiles.json','capabilities.json','execution_contract.json','telemetry/events.json']]
        except Exception as e:
            errors.append(f'parse error: {e}')
            return ValidationReport(False, str(p), schema, semantic, {'level':'D','score':0,'warnings':[],'errors':errors}, warnings, errors)
        schema['manifest'] = isinstance(manifest, dict) and manifest.get('kind') == 'SkillPackage' and 'metadata' in manifest and 'compatibility' in manifest
        schema['skill'] = isinstance(skill, dict) and skill.get('skillId','').startswith('etd.') and skill.get('entrypoint')
        schema['chs_profiles'] = isinstance(profiles.get('profiles'), list) and len(profiles['profiles']) > 0
        schema['capabilities'] = isinstance(caps.get('read'), list) and isinstance(caps.get('write'), list)
        schema['execution_contract'] = all(k in contract for k in ['body_mode','arm_mode','wrist_mode','primitive','speed_profile','force_profile','timeout_sec'])
        if not all(schema.values()): errors.append('schema check failed')
        semantic['name_matches_skill_id'] = manifest['metadata'].get('name') == skill.get('skillId')
        semantic['version_matches_skill_version'] = manifest['metadata'].get('version') == skill.get('version')
        names = [x.get('name') for x in profiles['profiles']]
        semantic['profile_uniqueness'] = len(names) == len(set(names))
        semantic['default_chs_profile_exists'] = skill.get('defaultChsProfile') in names
        ep_file = skill.get('entrypoint','').split(':')[0]
        semantic['entrypoint_exists'] = bool(ep_file and (p/ep_file).exists())
        manifest_events = set(manifest.get('telemetry',{}).get('emits',[]))
        file_events = set(events.get('events',[]))
        semantic['telemetry_has_lifecycle_event'] = bool((manifest_events | file_events) & LIFECYCLE)
        write_caps = set(caps.get('write',[]))
        semantic['capability_safe'] = 'command.skill_intent' in write_caps and not (write_caps & FORBIDDEN)
        semantic['primitive_order_nonempty'] = bool(skill.get('primitiveOrder'))
        semantic['force_windows_valid'] = all((('forceWindowN' not in prof) or (len(prof['forceWindowN']) == 2 and prof['forceWindowN'][1] >= prof['forceWindowN'][0])) for prof in profiles['profiles'])
        payload_max = manifest.get('constraints',{}).get('payloadKgMax')
        semantic['payload_within_constraints'] = True if payload_max is None else all(prof.get('payloadKg',0) <= payload_max for prof in profiles['profiles'])
        for k,v in semantic.items():
            if not v: errors.append(f'semantic check failed: {k}')
        compat_errors, compat_warnings = [], []
        compat = manifest.get('compatibility',{})
        if self.ctx.robot_class not in compat.get('robotClass',[]): compat_errors.append('robot_class_mismatch')
        req = set(compat.get('requiresServices',[])); avail = set(self.ctx.available_services)
        for svc in sorted(req-avail): compat_errors.append(f'missing_service:{svc}')
        for svc in sorted(set(compat.get('optionalServices',[]))-avail): compat_warnings.append(f'missing_optional_service:{svc}')
        need = min_runtime(compat.get('runtime',''))
        if need and version_tuple(self.ctx.runtime_version) < version_tuple(need): compat_errors.append('runtime_too_old')
        score = max(0.0, 1.0 - 0.15*len(compat_errors) - 0.03*len(compat_warnings))
        level = 'D' if compat_errors else ('B' if compat_warnings else 'A')
        comp = {'level':level,'score':round(score,2),'warnings':compat_warnings,'errors':compat_errors}
        valid = not errors and level in ['A','B']
        return ValidationReport(valid, str(p), schema, semantic, comp, warnings, errors)

def load_runtime_context(path: str | Path) -> RuntimeContext:
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    return RuntimeContext(**d)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('package')
    ap.add_argument('--runtime-context', default='runtime_context.json')
    ap.add_argument('--output', choices=['json','pretty'], default='pretty')
    args = ap.parse_args()
    ctx = load_runtime_context(args.runtime_context) if Path(args.runtime_context).exists() else RuntimeContext(available_services=[])
    rep = ETDReferenceValidator(ctx).validate_package(args.package)
    if args.output == 'json': print(rep.to_json())
    else:
        print('ETD validation:', 'PASS' if rep.valid else 'FAIL')
        print(rep.to_json())
    raise SystemExit(0 if rep.valid else 1)
if __name__ == '__main__': main()
