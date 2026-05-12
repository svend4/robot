"""Pytest wrapper around sim/acceptance_runner.py — runs all 39 YAML scenarios."""
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.acceptance_runner import run_suite

_ALL_SKILLS = [
    'etd.pickplace.basic',
    'etd.assembly.precision',
    'etd.inspect.vision',
    'etd.cobot.safeassist',
    'etd.atlas.humanoid_walkfetch',
    'etd.hyundai.wia_welding',
    'etd.hyundai.mobed_transport',
    'etd.hyundai.vest_exoskeleton',
]


@pytest.mark.parametrize('skill_id', _ALL_SKILLS)
def test_acceptance_suite(skill_id):
    random.seed(42)  # deterministic classify_result confidence for inspect.vision
    suite = run_suite(skill_id)
    failures = [r for r in suite.results if not r.passed]
    assert len(failures) == 0, (
        f'{skill_id}: {len(failures)} scenario(s) failed:\n' +
        '\n'.join(
            f'  {r.test_id}: status={r.status!r}, reason={r.reason!r}'
            + (f', msg={r.failure_message!r}' if r.failure_message else '')
            for r in failures
        )
    )
