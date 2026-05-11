"""Failure scenarios — demonstrate and verify the four key ETD failure modes.

Each scenario is a self-contained function that drives the relevant adapter or
validator with injected bad conditions and asserts the expected failure outcome.

Scenarios:
  1. missing_service_level_d  — robot runtime missing required services → level D
  2. human_in_forbidden_zone  — safety state injected mid-execution → skill.aborted
  3. payload_out_of_range     — station payload limit exceeded → incompatible
  4. station_family_mismatch  — skill family not allowed at station → incompatible

Usage::

    python sim/failure_scenarios.py          # run all and print summary
    python sim/failure_scenarios.py --json   # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import ETDReferenceValidator, RuntimeContext
from adapters.station_profile_loader import load_station_profile, check_skill_compatible


# ── Scenario 1: missing required services → validation level D ─────────────

def scenario_missing_service_level_d() -> Dict[str, Any]:
    """Validate etd.pickplace.basic with only one available service.

    Expected: valid=False, level='D', at least one missing_service error.
    """
    ctx = RuntimeContext(
        runtime_version='0.1.0',
        robot_class='humanoid',
        available_services=['perception.object_pose'],   # far fewer than required
    )
    rep = ETDReferenceValidator(ctx).validate_package(ROOT / 'examples/etd.pickplace.basic')
    passed = rep.compatibility['level'] == 'D'
    missing_errors = [e for e in rep.compatibility.get('errors', []) if 'missing_service' in e]
    return {
        'scenario':       'missing_service_level_d',
        'passed':         passed,
        'level':          rep.compatibility['level'],
        'missing_errors': missing_errors,
        'detail':         f'{len(missing_errors)} missing service(s) detected' if passed
                          else f'expected level D, got {rep.compatibility["level"]}',
    }


# ── Scenario 2: human in forbidden zone → skill aborted mid-execution ───────

def scenario_human_in_forbidden_zone() -> Dict[str, Any]:
    """Run etd.assembly.precision adapter with human-in-zone injected at 'align'.

    Uses AcceptanceMiddleware from the acceptance runner for clean injection.
    Expected: status='aborted', reason='human_in_forbidden_zone'.
    """
    import importlib.util
    from sim.acceptance_runner import AcceptanceMiddleware

    pkg_path = ROOT / 'examples' / 'etd.assembly.precision'
    spec = importlib.util.spec_from_file_location(
        'chs_adapter_assembly_fs',
        pkg_path / 'policies' / 'chs_adapter.py',
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules['chs_adapter_assembly_fs'] = module
    spec.loader.exec_module(module)

    mw = AcceptanceMiddleware(
        inject_at={'vision_align': {'safety_state': {'human_in_forbidden_zone': True}}}
    )
    try:
        result = module.run(
            middleware=mw,
            job_context={'profileId': 'peg_in_hole', 'targetForceN': 12.0},
        )
        passed = result.get('status') == 'aborted' and result.get('reason') == 'human_in_forbidden_zone'
        return {
            'scenario': 'human_in_forbidden_zone',
            'passed':   passed,
            'status':   result.get('status'),
            'reason':   result.get('reason'),
            'detail':   'human detected at align → aborted correctly' if passed
                        else f'unexpected result: {result}',
        }
    except Exception as exc:
        return {'scenario': 'human_in_forbidden_zone', 'passed': False,
                'status': 'error', 'reason': str(exc), 'detail': str(exc)}


# ── Scenario 3: payload exceeds station limit → incompatible ────────────────

def scenario_payload_out_of_range() -> Dict[str, Any]:
    """Check etd.hyundai.wia_welding (1.5 kg) against weld_station_a (max 2 kg) — OK.
    Then check with 5 kg — should be rejected.

    Expected: compatible=True at 1.5 kg, compatible=False at 5.0 kg.
    """
    profile = load_station_profile(ROOT / 'station_profiles' / 'weld_station_a.json')

    ok = check_skill_compatible(profile, 'weld', payload_kg=1.5,
                                requires_human_aware=False, required_services=[])
    fail = check_skill_compatible(profile, 'weld', payload_kg=5.0,
                                  requires_human_aware=False, required_services=[])
    passed = ok.compatible is True and fail.compatible is False and '2.0' in fail.reason
    return {
        'scenario':       'payload_out_of_range',
        'passed':         passed,
        'ok_at_1_5kg':    ok.compatible,
        'blocked_at_5kg': not fail.compatible,
        'block_reason':   fail.reason,
        'detail':         f'payload gate works correctly (limit={profile.max_payload_kg}kg)' if passed
                          else f'unexpected compat: ok={ok.compatible}, fail={fail.compatible}',
    }


# ── Scenario 4: wrong skill family for station → incompatible ───────────────

def scenario_station_family_mismatch() -> Dict[str, Any]:
    """Check etd.hyundai.mobed_transport (family=transport) against weld_station_a.

    weld_station_a allows ['weld','inspect'], not 'transport' → incompatible.
    """
    profile = load_station_profile(ROOT / 'station_profiles' / 'weld_station_a.json')
    result = check_skill_compatible(profile, 'transport', payload_kg=1.0,
                                    requires_human_aware=False, required_services=[])
    passed = result.compatible is False and 'transport' in result.reason and 'not_allowed' in result.reason
    return {
        'scenario':    'station_family_mismatch',
        'passed':      passed,
        'compatible':  result.compatible,
        'reason':      result.reason,
        'detail':      'transport rejected by weld station correctly' if passed
                       else f'unexpected result: compatible={result.compatible} reason={result.reason}',
    }


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all() -> list:
    return [
        scenario_missing_service_level_d(),
        scenario_human_in_forbidden_zone(),
        scenario_payload_out_of_range(),
        scenario_station_family_mismatch(),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description='Run ETD failure scenarios.')
    ap.add_argument('--json', dest='as_json', action='store_true')
    args = ap.parse_args()

    results = run_all()

    if args.as_json:
        print(json.dumps(results, indent=2))
    else:
        print('\nETD Failure Scenario Suite')
        print('─' * 55)
        for r in results:
            status = '\033[32mPASS\033[0m' if r['passed'] else '\033[31mFAIL\033[0m'
            print(f'  {r["scenario"]:<35} {status}')
            print(f'    {r["detail"]}')
        total = len(results)
        passed = sum(1 for r in results if r['passed'])
        print(f'\n{passed}/{total} failure scenarios verified.\n')

    sys.exit(0 if all(r['passed'] for r in results) else 1)


if __name__ == '__main__':
    main()
