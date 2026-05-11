# ETD Marketplace Architecture

The ETD marketplace layer has four components:

1. `skill_store_index.json` — list of packages, versions, risk level and target use.
2. `marketplace_policy.json` — install/review policy.
3. `skill_store.py` — list and validate packages.
4. Runtime validator — blocks packages that request forbidden capabilities or lack required services.

The marketplace is not allowed to bypass safety constraints. It is a governed distribution layer for validated application-layer skills.
