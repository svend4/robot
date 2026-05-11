"""Marketplace install-decision demo for all ETD skill store entries."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import load_runtime_context
from marketplace.skill_store import SkillStore, default_runtime_context

_ATLAS_CTX_PATH = ROOT / 'runtime_context_atlas.json'
_ATLAS_SKILLS = {'humanoid', 'atlas'}


def _pick_context(entry_family: str):
    if any(kw in entry_family for kw in _ATLAS_SKILLS):
        if _ATLAS_CTX_PATH.exists():
            return load_runtime_context(_ATLAS_CTX_PATH)
    return default_runtime_context()


def main() -> None:
    store = SkillStore(ROOT)
    results = []
    for entry in store.list_entries():
        ctx = _pick_context(entry.family)
        token = 'demo-entitlement-token' if entry.requiresEntitlement else None
        decision = store.validate_for_install(entry.skillId, ctx, entitlement_token=token)
        results.append(asdict(decision))

    print(json.dumps({'marketplace_demo': results}, indent=2))

    if not all(item['allowed'] for item in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
