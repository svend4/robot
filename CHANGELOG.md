# Changelog

## 0.3.0 — Hyundai platform expansion, station profiles, test suite

### New skill packages
- `examples/etd.hyundai.wia_welding` — Hyundai WIA H-Motion cobot arc-welding skill
  (family `weld`, 7 primitives, seam-tracker confidence gate, arc ignition/extinguish lifecycle,
  per-step safety during `weld_traverse`, released as `release_out/etd.hyundai.wia_welding-0.1.0.zip`)
- `examples/etd.hyundai.mobed_transport` — Hyundai MobED AMR transport skill
  (family `transport`, 5 primitives, human-aware speed reduction, per-step forbidden-zone checks,
  released as `release_out/etd.hyundai.mobed_transport-0.1.0.zip`)

### Runtime contexts
- `runtime_context_wia.json` — cobot runtime (16 services incl. `welding.*`)
- `runtime_context_mobed.json` — AMR runtime (10 services incl. `navigation.*`)

### Station profiles
- `station_profiles/weld_station_a.json` — Hyundai WIA H-Motion welding cell, arc zone enforced
- `station_profiles/mobed_logistics_a.json` — Hyundai MobED AMR logistics cell, 100 kg limit
- `station_profiles/humanoid_hmgma_a.json` — Boston Dynamics Atlas HMGMA sequencing line

### Station profile integration
- `adapters/station_profile_loader.py` — `StationProfile` dataclass, `check_skill_compatible()`,
  `load_all_profiles()`; legacy `is_skill_allowed()` helper preserved
- CLI: `--station-profile FILE` added to `validate` and `install` commands;
  new `etd stations` subcommand lists all profiles
- CLI: fixed `--robot-class` default (`None`; was `'humanoid'` which overwrote context files)
- API: `GET /store/stations`, `GET /store/stations/{id}` endpoints
- API: `POST /store/install` accepts optional `station_id`; response includes
  `station_compatible`, `station_reason`, `station_missing_services`, `station_warnings`

### Adapters
- `adapters/orbit_event_bridge.py` — expanded from 2-line stub to full bridge:
  `to_enterprise_event()` with severity/sequence/correlation_id envelope;
  `OrbitEventBridge` dataclass with `ingest()`, `flush()`, `pending()`, `reset()`,
  severity filter, critical-event bypass, and `on_flush` callback;
  `replay_skill_log()` helper
- `adapters/generic_oem_adapter.py` — unchanged; safety gate preserved

### Test suite (new)
- `tests/test_validator.py` — 14 tests: schema validation, semantic checks, compatibility levels,
  runtime context loading, JSON roundtrip
- `tests/test_api.py` — 17 tests: all REST endpoints, filter parameters, 404 handling
- `tests/test_cli.py` — 16 tests: all CLI commands via Click `CliRunner`
- `tests/test_marketplace.py` — 13 tests: `SkillStore` list/find/validate/install
- `tests/test_station_profiles.py` — 30 tests: loader, compatibility checker, human-aware
  warnings, API endpoints, CLI `stations` command (total: **90 tests**)

### Acceptance test framework
- `sim/acceptance_runner.py` — `AcceptanceMiddleware` with per-primitive state injection
  (`inject_at` dict: `safety_state`, `perception_override`, `force_override`);
  supports both `tests[]` and `scenarios[]` YAML formats; `--skill`, `--verbose`, `--json` flags
- All 7 packages have upgraded `tests/acceptance_tests.yaml` with package-specific scenarios
  (34 scenarios total, all passing)
- `examples/etd.assembly.precision/policies/chs_adapter.py` — added per-primitive safety gate
- `examples/etd.inspect.vision/policies/chs_adapter.py` — added per-primitive safety gate
- `examples/etd.cobot.safeassist/policies/chs_adapter.py` — fixed `humanReadyTimeoutSec`
  job-context override

### Packaging
- `pyproject.toml` — PEP 517/518 packaging; `etd` CLI entry point via `project.scripts`;
  `*.egg-info/` added to `.gitignore`
- `scripts/release_package.py` — 4-tier runtime context auto-detection
  (base / atlas / wia / mobed) based on package name keywords
- `etd_demo_runner.py` — expanded to validate all 7 packages with correct runtime contexts;
  coloured summary table; `--json` and `--fail-fast` flags; exits 0 only if all reach level A/B
- `marketplace/skill_store_index.json` — expanded from 5 to 7 entries
- `.github/workflows/validate-examples.yml` — added pytest and acceptance-runner steps

## 0.1.0
- Initial ETD skill package prototype.
- Added validator, example packages, adapters, simulation, reports, and docs.
- Added Unitree skill-store positioning notes.

## v0.1 marketplace licensing update

Added:

- `docs/skill-marketplace-licensing.md`
- `docs/commercialization-and-protection.md`
- `marketplace/licensing_policy.json`
- `marketplace/sample_commercial_listing.json`
- `marketplace/sample_open_source_listing.json`

Updated:

- `marketplace/skill_store_index.json` with license, pricing, source-availability, activation, and protection metadata
- `marketplace/marketplace_policy.json` with license-policy and commercial-package safeguards
- `README.md` with marketplace and licensing summary

Rationale:

- clarify open-source vs commercial distribution models
- define paid-skill protection mechanisms
- separate consumer-style action sharing from industrial ETD skill packages


## 0.1.4 - Documentation and licensing expansion

- Added `docs/documentation-system.md`.
- Added `docs/licensing-and-monetization.md`.
- Added `docs/commercial-skill-protection.md`.
- Added `docs/skill-package-doc-template.md`.
- Added `marketplace/license_policy.json`.
- Expanded `marketplace/skill_store_index.json` with license, pricing, source availability, protection level, and entitlement metadata.
- Expanded `marketplace/marketplace_policy.json` with commercial install requirements and commercial blocking conditions.

## v0.1-docs-commercial-model

Added:
- `docs/documentation-system.md`
- `docs/skill-marketplace-commercial-and-licensing.md`
- `docs/marketplace-protection-model.md`

These documents clarify how ETD should be documented, how open-source and commercial skill packages can coexist, and how marketplace protection can be implemented through signing, licensing, sandboxing, and audit trails.



## 0.1.1-docs
- Added detailed documentation system guide.
- Added licensing and commercial model notes for ETD skill marketplaces.
- Added IP protection and package security notes.
- Added marketplace submission and review guide.

## v0.1 documentation-marketplace update

- Added `docs/documentation-expansion-guide.md`.
- Added `docs/marketplace-commercial-model.md`.
- Added `docs/licensing-ip-protection.md`.
- Added `docs/unitree-open-vs-commercial-notes.md`.
- Expanded README with marketplace/documentation notes.

## v0.1.x - Documentation, licensing, and marketplace governance

Added:
- `docs/documentation-blueprint.md`
- `docs/skill-economics-licensing.md`
- `docs/ip-protection-and-package-security.md`
- `docs/store-governance-review-model.md`
- licensing/pricing metadata in `marketplace/skill_store_index.json`
- commercial/open-source policy fields in `marketplace/marketplace_policy.json`
- `marketplace/skill_store.py` reference helper


## v0.1-doc-commercial-update

Added detailed documentation for:

- documentation structure and developer documentation plan;
- open-source vs commercial skill package models;
- package IP protection and security;
- Unitree skill-store business-model analysis;
- marketplace license profiles and protection profiles.


## 0.2.0-docs-marketplace
- Added detailed documentation expansion guide.
- Added licensing and commercialization model for ETD skill packages.
- Added marketplace commercial policy document.
- Expanded marketplace index with license, pricing, entitlement, and source-availability metadata.
- Added reference `marketplace/skill_store.py` and `sim/marketplace_demo.py`.
