"""ETD Acceptance Test Runner.

Reads tests/acceptance_tests.yaml for each skill package and runs each scenario
against the real chs_adapter.py, using an AcceptanceMiddleware that can inject
safety/perception state at specific primitives.

Usage:
    python sim/acceptance_runner.py                          # run all packages
    python sim/acceptance_runner.py --skill etd.pickplace.basic
    python sim/acceptance_runner.py --verbose
    python sim/acceptance_runner.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Acceptance middleware ──────────────────────────────────────────────────────

class AcceptanceMiddleware:
    """Middleware for acceptance testing — supports state injection at primitives."""

    def __init__(
        self,
        initial_safety: Optional[Dict[str, Any]] = None,
        inject_at: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self._safety: Dict[str, Any] = {
            'human_in_forbidden_zone': False,
            'human_ready_signal': True,
            'human_in_safety_radius': True,
            'human_distance_m': 2.0,
            'normal_force_n': 12.0,
            'confidence': 0.96,
            'aligned': True,
        }
        if initial_safety:
            self._safety.update(initial_safety)

        self._inject_at: Dict[str, Dict[str, Any]] = inject_at or {}
        self._camera_frame_count = 0
        self.events: List[Dict[str, Any]] = []
        self.primitives_entered: List[str] = []

    def publish(self, topic: str, msg: Any) -> None:
        if topic == 'telemetry.events':
            event = msg.get('event', '')
            self.events.append({'event': event, 'ts': time.time(),
                                **{k: v for k, v in msg.items() if k != 'event'}})
            if event == 'primitive.entered':
                prim = msg.get('primitive', '')
                self.primitives_entered.append(prim)
                if prim in self._inject_at:
                    patch = self._inject_at[prim]
                    if 'safety_state' in patch:
                        self._safety.update(patch['safety_state'])
                    if 'perception_override' in patch:
                        self._safety.update(patch['perception_override'])
                    if 'force_override' in patch:
                        self._safety.update(patch['force_override'])

    def read(self, topic: str) -> Any:
        if topic == 'state.safety_state':
            return dict(self._safety)
        if topic == 'force_control.contact_feedback':
            return {'normal_force_n': self._safety.get('normal_force_n', 12.0)}
        if topic == 'perception.part_alignment':
            return {
                'confidence': self._safety.get('confidence', 0.96),
                'offset_mm': 0.15,
                'aligned': self._safety.get('aligned', True),
            }
        if topic == 'perception.camera_frame':
            self._camera_frame_count += 1
            return {'frame_id': self._camera_frame_count, 'width': 1920, 'height': 1080}
        if topic == 'perception.scene_map':
            return {'map_ready': True, 'obstacles': []}
        if topic == 'state.balance_state':
            return {'stable': True, 'com_margin': 0.12, 'gait': 'stand'}
        if topic == 'perception.object_pose':
            return {'confidence': self._safety.get('confidence', 0.96),
                    'x': 3.0, 'y': 1.5, 'z': 0.8,
                    'object_class': 'automotive_part', 'mass_estimate_kg': 4.5}
        if topic == 'perception.seam_tracker':
            return {'confidence': self._safety.get('confidence', 0.96),
                    'offset_mm': 0.3, 'seam_found': True}
        if topic == 'vision.weld_inspection':
            return {'pass': True, 'defects': [], 'confidence': 0.97}
        if topic == 'perception.obstacle_detector':
            return {'obstacles': [], 'clear': True}
        if topic == 'navigation.path_planner':
            return {'path_ready': True, 'estimated_time_s': 30}
        if topic == 'manipulation.lift_control':
            return {'lift_ready': True, 'current_height_mm': 0}
        return None


# ── Test result ───────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: str
    description: str
    passed: bool
    status: str
    reason: Optional[str]
    failure_message: Optional[str]
    primitives_entered: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class SuiteResult:
    skill_id: str
    suite: str
    total: int
    passed: int
    failed: int
    results: List[TestResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


# ── Adapter loader ────────────────────────────────────────────────────────────

def _load_run(skill_id: str):
    pkg_path = ROOT / 'examples' / skill_id
    skill_json = json.loads((pkg_path / 'skill.json').read_text())
    entrypoint = skill_json.get('entrypoint', 'policies/chs_adapter.py:run')
    module_rel, func_name = entrypoint.split(':')
    mod_name = f'etd_acc_{skill_id.replace(".", "_")}'
    spec = importlib.util.spec_from_file_location(mod_name, pkg_path / module_rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return getattr(module, func_name)


# ── Test execution ────────────────────────────────────────────────────────────

def _run_test(run_fn, test: Dict[str, Any], skill_id: str) -> TestResult:
    test_id = test.get('id', test.get('name', 'unknown'))
    description = test.get('description', '')

    profile = test.get('profile', 'default')
    job_ctx = test.get('input', {}).get('job_context', {'chsProfile': profile, 'priority': 'normal'})
    if 'chsProfile' not in job_ctx:
        job_ctx['chsProfile'] = profile

    inject_spec = test.get('inject', {})
    inject_at: Dict[str, Dict[str, Any]] = {}
    if inject_spec:
        at_prim = inject_spec.get('at_primitive')
        if at_prim:
            inject_at[at_prim] = {k: v for k, v in inject_spec.items() if k != 'at_primitive'}

    # Initial safety overrides (applied before any primitive)
    initial_safety = None
    if inject_spec and 'at_primitive' not in inject_spec:
        # Legacy format: inject applies globally
        initial_safety = inject_spec.get('safety_state')

    mw = AcceptanceMiddleware(initial_safety=initial_safety, inject_at=inject_at)

    t0 = time.time()
    try:
        result = run_fn(job_ctx, middleware=mw)
    except Exception as exc:
        return TestResult(
            test_id=test_id, description=description, passed=False,
            status='error', reason=None,
            failure_message=f'Exception: {exc}',
            primitives_entered=mw.primitives_entered,
            duration_ms=(time.time() - t0) * 1000,
        )
    duration_ms = (time.time() - t0) * 1000

    expect = test.get('expect', test.get('expected', {}))
    actual_status = result.get('status', '')
    actual_reason = result.get('reason', '')

    failure_msg = None

    exp_status = expect.get('status')
    if exp_status and actual_status != exp_status:
        failure_msg = f'status: expected={exp_status!r}, got={actual_status!r}'

    if not failure_msg:
        exp_reason = expect.get('reason')
        if exp_reason and actual_reason != exp_reason:
            failure_msg = f'reason: expected={exp_reason!r}, got={actual_reason!r}'

    if not failure_msg:
        for key in expect.get('result_keys', []):
            if key not in result:
                failure_msg = f'result missing key: {key!r}'
                break

    return TestResult(
        test_id=test_id, description=description,
        passed=(failure_msg is None),
        status=actual_status, reason=actual_reason or None,
        failure_message=failure_msg,
        primitives_entered=mw.primitives_entered,
        duration_ms=duration_ms,
    )


# ── Suite runner ──────────────────────────────────────────────────────────────

def run_suite(skill_id: str) -> SuiteResult:
    pkg_path = ROOT / 'examples' / skill_id
    tests_yaml = pkg_path / 'tests' / 'acceptance_tests.yaml'
    if not tests_yaml.exists():
        return SuiteResult(skill_id=skill_id, suite='(no tests)', total=0, passed=0, failed=0)

    spec = yaml.safe_load(tests_yaml.read_text(encoding='utf-8'))
    suite_name = spec.get('suite', skill_id)
    tests = spec.get('tests', spec.get('scenarios', []))

    run_fn = _load_run(skill_id)
    results: List[TestResult] = []
    for test in tests:
        r = _run_test(run_fn, test, skill_id)
        results.append(r)

    passed = sum(1 for r in results if r.passed)
    return SuiteResult(
        skill_id=skill_id, suite=suite_name,
        total=len(results), passed=passed, failed=len(results) - passed,
        results=results,
    )


# ── Output formatting ─────────────────────────────────────────────────────────

def _print_suite(suite: SuiteResult, verbose: bool) -> None:
    icon = '✓' if suite.success else '✗'
    print(f'\n{icon} {suite.skill_id}  [{suite.suite}]  {suite.passed}/{suite.total} passed')
    print(f'  {"─"*60}')
    for r in suite.results:
        p_icon = '  ✓' if r.passed else '  ✗'
        print(f'{p_icon} {r.test_id:<42} {r.duration_ms:>6.0f} ms')
        if not r.passed:
            print(f'       FAIL: {r.failure_message}')
        elif verbose:
            print(f'       → status={r.status!r}'
                  + (f'  reason={r.reason!r}' if r.reason else ''))


def main() -> None:
    ap = argparse.ArgumentParser(description='ETD Acceptance Test Runner')
    ap.add_argument('--skill', default=None, help='Run only this skill ID')
    ap.add_argument('--verbose', '-v', action='store_true', help='Show passing test details')
    ap.add_argument('--json', dest='as_json', action='store_true', help='JSON output')
    args = ap.parse_args()

    if args.skill:
        skills = [args.skill]
    else:
        skills = sorted(d.name for d in (ROOT / 'examples').iterdir()
                        if d.is_dir() and (d / 'tests' / 'acceptance_tests.yaml').exists())

    suites: List[SuiteResult] = []
    for skill_id in skills:
        suite = run_suite(skill_id)
        suites.append(suite)

    if args.as_json:
        print(json.dumps([asdict(s) for s in suites], indent=2))
    else:
        for suite in suites:
            _print_suite(suite, verbose=args.verbose)
        total = sum(s.total for s in suites)
        passed = sum(s.passed for s in suites)
        failed = sum(s.failed for s in suites)
        print(f'\n{"═"*65}')
        print(f'  Acceptance Tests: {passed}/{total} passed', end='')
        if failed:
            print(f'  ({failed} FAILED)', end='')
        print()
        print('═' * 65)

    if any(s.failed > 0 for s in suites):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
