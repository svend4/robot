from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.skill_store import SkillStore, default_runtime_context


def main() -> None:
    store = SkillStore(ROOT)
    context = default_runtime_context()

    results = []
    for entry in store.list_entries():
        # Free/open-source packages need no entitlement. Commercial/private packages do.
        token = "demo-entitlement-token" if entry.requiresEntitlement else None
        decision = store.validate_for_install(entry.skillId, context, entitlement_token=token)
        results.append(asdict(decision))

    print(json.dumps({"marketplace_demo": results}, indent=2))

    if not all(item["allowed"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
