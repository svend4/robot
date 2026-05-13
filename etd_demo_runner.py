#!/usr/bin/env python3
"""ETD demo runner — validate all example packages and print a summary table.

Exits 0 if every package reaches validation level A or B, else 1.

Usage:
    python etd_demo_runner.py [--json] [--fail-fast]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import ETDReferenceValidator, load_runtime_context

# Map package name keywords → runtime context file
_CTX_MAP = [
    (('atlas', 'humanoid'),         'runtime_context_atlas.json'),
    (('wia', 'welding'),            'runtime_context_wia.json'),
    (('mobed', 'transport', 'amr'), 'runtime_context_mobed.json'),
    (('vest', 'exoskeleton', 'exo'),    'runtime_context_exo.json'),
]
_DEFAULT_CTX = 'runtime_context.json'


def _pick_context(pkg_name: str) -> Path:
    for keywords, ctx_file in _CTX_MAP:
        if any(kw in pkg_name for kw in keywords):
            p = ROOT / ctx_file
            if p.exists():
                return p
    return ROOT / _DEFAULT_CTX


def _level_ok(level: str) -> bool:
    return level in ('A', 'B')


def run_all(fail_fast: bool = False) -> list[dict]:
    examples_dir = ROOT / 'examples'
    packages = sorted(p for p in examples_dir.iterdir()
                      if p.is_dir() and (p / 'manifest.yaml').exists())
    results = []
    for pkg in packages:
        ctx_path = _pick_context(pkg.name)
        ctx = load_runtime_context(ctx_path)
        report = ETDReferenceValidator(ctx).validate_package(pkg)
        entry = {
            'package':    pkg.name,
            'valid':      report.valid,
            'level':      report.compatibility['level'],
            'score':      report.compatibility['score'],
            'ctx':        ctx_path.name,
            'errors':     report.errors,
            'warnings':   report.warnings,
            'compat_errors': report.compatibility.get('errors', []),
        }
        results.append(entry)
        if fail_fast and not _level_ok(entry['level']):
            break
    return results


def _print_table(results: list[dict]) -> None:
    col = 38
    print(f'\n{"PACKAGE":<{col}} {"CTX":<30} {"LEVEL":>5}  {"SCORE":>5}  STATUS')
    print('─' * 90)
    for r in results:
        ok = _level_ok(r['level'])
        status = '\033[32mPASS\033[0m' if ok else '\033[31mFAIL\033[0m'
        print(f'{r["package"]:<{col}} {r["ctx"]:<30} {r["level"]:>5}  {r["score"]:>5.2f}  {status}')
        for e in r['compat_errors']:
            print(f'  \033[31m✗ {e}\033[0m')
        for e in r['errors']:
            print(f'  \033[31m✗ {e}\033[0m')
        for w in r['warnings']:
            print(f'  \033[33m! {w}\033[0m')
    passed = sum(1 for r in results if _level_ok(r['level']))
    total = len(results)
    print(f'\n{passed}/{total} package(s) passed (level A or B).\n')


def main() -> None:
    ap = argparse.ArgumentParser(description='Validate all ETD example packages.')
    ap.add_argument('--json', dest='as_json', action='store_true', help='Output raw JSON')
    ap.add_argument('--fail-fast', action='store_true', help='Stop at first failure')
    args = ap.parse_args()

    results = run_all(fail_fast=args.fail_fast)

    if args.as_json:
        print(json.dumps(results, indent=2))
    else:
        _print_table(results)

    all_ok = all(_level_ok(r['level']) for r in results)
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
