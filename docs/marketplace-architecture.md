# ETD Marketplace Architecture

The ETD marketplace is a governed distribution layer for validated,
application-layer skill packages. It enforces entitlement, safety, and
station compatibility before any package can be installed or executed.

---

## Component overview

```
┌──────────────────────────────────────────────────────┐
│                  ETD Marketplace                     │
│                                                      │
│  ┌─────────────────────┐  ┌────────────────────┐    │
│  │  skill_store_index  │  │  marketplace_policy │    │
│  │  (index of 8 pkgs,  │  │  (install rules,    │    │
│  │   versions, license)│  │   entitlement gate) │    │
│  └────────┬────────────┘  └──────────┬─────────┘    │
│           │                          │               │
│  ┌────────▼──────────────────────────▼─────────┐    │
│  │            SkillStore                        │    │
│  │  find_skill()  get_entry()                   │    │
│  │  validate_for_install()                      │    │
│  └────────────────────┬────────────────────────┘    │
│                        │                             │
│  ┌─────────────────────▼──────────────────────┐     │
│  │          ETD Reference Validator            │     │
│  │  JSON Schema · safety check · compat score  │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

---

## Components

### `skill_store_index.json`

Master index of all packages in the marketplace. Each entry records:

```json
{
  "skillId": "etd.hyundai.wia_welding",
  "version": "0.1.0",
  "license": "commercial",
  "entitlementRequired": true,
  "riskLevel": "medium",
  "family": "weld",
  "targetPlatform": "hyundai_wia_h_motion",
  "path": "examples/etd.hyundai.wia_welding"
}
```

Fields: `skillId`, `version`, `license`, `entitlementRequired`,
`riskLevel` (low/medium/high), `family`, `targetPlatform`, `path`.

### `marketplace_policy.json`

Policy rules governing which packages may be installed and under what
conditions:

```json
{
  "allowedLicenses": ["open_source", "commercial", "enterprise_private"],
  "requireEntitlementCheck": true,
  "requireSignatureVerification": false,
  "minCompatibilityLevel": "B",
  "blockedFamilies": [],
  "requireStationMatch": true
}
```

`minCompatibilityLevel` prevents C/D packages from being installed even
if they pass schema validation. `requireStationMatch` gates installs on
station profile compatibility.

### `SkillStore` (`marketplace/skill_store.py`)

The programmatic interface to the marketplace:

| Method | Returns | Description |
|---|---|---|
| `find_skill(skill_id)` | `dict \| None` | Raw index entry; None if not found |
| `get_entry(skill_id)` | `StoreEntry \| None` | Typed dataclass; None if not found |
| `validate_for_install(skill_id, station_profile)` | `InstallDecision` | Full gated install check |
| `list_skills(family, free_only)` | `list[dict]` | Filtered skill listing |

`InstallDecision` dataclass:
- `allowed: bool` — whether install is permitted
- `reason: str` — human-readable explanation
- `entry: StoreEntry | None` — the matched store entry

### ETD Reference Validator

Called by `validate_for_install` to run the full validation pipeline:
1. Load all 5 required package files
2. Validate each against its JSON Schema
3. Check `capabilities.json` against the global forbidden list
4. Score compatibility against the station profile and runtime context
5. Return `ValidationReport` with `valid`, `errors`, `compatibility`

The validator is the final safety gate — no package with a schema error
or forbidden capability write can pass.

---

## Install flow

```
CLI / API: install(skill_id, station_profile)
    │
    ▼
SkillStore.validate_for_install(skill_id, station_profile)
    │
    ├─ find_skill(skill_id) → None?  → denied: "skill not found"
    │
    ├─ entitlementRequired?
    │   └─ entitlement_checked = False?  → denied: "entitlement required"
    │
    ├─ ETDReferenceValidator.validate_package(path)
    │   ├─ schema errors?  → denied: "validation failed"
    │   └─ compatibility level C/D?  → denied: "compatibility too low"
    │
    ├─ station_profile provided?
    │   └─ _check_station_compat(skill, station)
    │       └─ required service missing?  → incompatible (logged, not denied)
    │
    └─ allowed = True  → InstallDecision(allowed=True, reason="ok", entry=…)
```

---

## License tiers

| License | Source | Entitlement | Examples |
|---|---|---|---|
| `open_source` | Full source | Not required | `etd.pickplace.basic` |
| `commercial` | Partial / binary | Required | `etd.assembly.precision`, all Hyundai |
| `enterprise_private` | Private, not distributed | Required | `etd.cobot.safeassist` |

Entitlement is checked at install time only. The runtime does not re-verify
entitlement on each execution — it trusts the install-time gate.

---

## Safety enforcement in the marketplace

The marketplace enforces the safety boundary at three points:

1. **Schema validation**: `manifest.yaml` must declare all five
   `packageCanNotOverride` entries. Missing any one of them causes
   `valid = False`.

2. **Capabilities check**: `capabilities.json` `write` list is scanned
   against a global forbidden set. Any match blocks the install.

3. **Station compatibility**: if a station profile is provided, the
   validator confirms that all `requiresServices` declared in the manifest
   are available at that station.

The marketplace layer itself cannot bypass these checks — there is no
admin override path in the current design.
