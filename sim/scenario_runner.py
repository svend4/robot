"""Scenario runner — validate all ETD example packages with correct runtime contexts.

Unlike etd_demo_runner.py (which is the CLI entry point), this module is
importable and used by other sim scripts.  Returns structured results rather
than printing a table.

Usage::

    from sim.scenario_runner import run_all_scenarios, print_results

    results = run_all_scenarios()
    print_results(results)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import ETDReferenceValidator, load_runtime_context

_CTX_MAP = [
    (('atlas', 'humanoid'),          'runtime_context_atlas.json'),
    (('wia', 'welding'),             'runtime_context_wia.json'),
    (('mobed', 'transport', 'amr'),  'runtime_context_mobed.json'),
]


def _pick_context(pkg_name: str) -> Path:
    for keywords, ctx_file in _CTX_MAP:
        if any(kw in pkg_name for kw in keywords):
            p = ROOT / ctx_file
            if p.exists():
                return p
    return ROOT / 'runtime_context.json'


def run_all_scenarios() -> List[Dict]:
    results = []
    for pkg in sorted((ROOT / 'examples').iterdir()):
        if not pkg.is_dir():
            continue
        ctx_path = _pick_context(pkg.name)
        ctx = load_runtime_context(ctx_path)
        rep = ETDReferenceValidator(ctx).validate_package(pkg)
        results.append({
            'package':  pkg.name,
            'valid':    rep.valid,
            'level':    rep.compatibility['level'],
            'score':    rep.compatibility['score'],
            'ctx':      ctx_path.name,
            'errors':   rep.errors,
            'warnings': rep.warnings,
            'compat_errors': rep.compatibility.get('errors', []),
        })
    return results


def print_results(results: List[Dict]) -> None:
    print(f'\n{"PACKAGE":<38} {"CTX":<30} LEVEL  VALID')
    print('─' * 82)
    for r in results:
        mark = 'PASS' if r['valid'] else 'FAIL'
        print(f'{r["package"]:<38} {r["ctx"]:<30} {r["level"]}      {mark}')
        for e in r.get('compat_errors', []):
            print(f'  ! {e}')
    passed = sum(1 for r in results if r['valid'])
    print(f'\n{passed}/{len(results)} package(s) valid.\n')


def main() -> None:
    results = run_all_scenarios()
    print_results(results)
    sys.exit(0 if all(r['valid'] for r in results) else 1)


if __name__ == '__main__':
    main()
