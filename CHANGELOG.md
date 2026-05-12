# Changelog

## 0.5.0 — Sim/adapters integration polish

### Visualizer
- `sim/visualizer.py` — all 8 skill packages now covered in `_SKILL_PROFILES`
  (added `etd.atlas.humanoid_walkfetch` / `sequencing_carry` and
  `etd.hyundai.vest_exoskeleton` / `overhead_assembly`)
- `TracingMiddleware.read()` — added exo topic handlers:
  `state.exo_joint_state`, `perception.intent_detector`, `state.fatigue_monitor`,
  `perception.imu_pose`; all return safe nominal values
- Seeded `random.seed(42)` in `run_traced()` so `etd.inspect.vision` classify_result
  is deterministic — no more intermittent aborts in the visualizer

### Package exports
- `adapters/__init__.py` — now exports `OrbitEventBridge`, `to_enterprise_event`,
  `replay_skill_log`, `StationProfile`, `StationCompatibilityResult`,
  `check_skill_compatible`, `load_all_profiles`, `load_station_profile`,
  `is_skill_allowed`
- `sim/__init__.py` — now exports `replay`, `replay_execution`, `nominal_lifecycle`,
  `aborted_lifecycle`, `RobotStateGenerator`, `mock_state`, `FakeMiddleware`,
  `run_all_scenarios`, `run_all_failure_scenarios`

### Sample data & middleware
- `sim/sample_event_sequence.json` — replaced 4-event stub with a 32-event
  multi-robot execution log: nominal pickplace (robot-01 / assembly_station_a),
  aborted wia_welding at torch_align (cobot-02 / weld_station_a, human_in_forbidden_zone),
  nominal mobed_transport (mobed-03 / logistics_cell_a)
- `sim/fake_middleware_endpoint.py` — added `exo_assembly_a` to `_KNOWN_STATIONS`

---

## 0.4.0 — Exoskeleton skill package + sim module expansion

### New skill package — etd.hyundai.vest_exoskeleton (8th package)
- `examples/etd.hyundai.vest_exoskeleton/` — Hyundai VEX/H-MEX wearable assist;
  family `assist`, 6 primitives: calibrate_fit → detect_intent → engage_assist →
  monitor_fatigue → adapt_gain → disengage_assist
- CHS profiles: `overhead_assembly` (120 N, 70 % fatigue gate),
  `heavy_carry` (150 N, 60 %), `lumbar_support` (80 N, 80 %)
- Intent confidence gate at `detect_intent` (aborts below profile threshold);
  torque-zero on `operator_panic_release`; adaptive gain when fatigue exceeds threshold
- 5 acceptance test scenarios (nominal, low confidence abort, panic release, human zone, fatigue)
- Schema extensions: `assist` added to family enum; `exoskeleton`/`wearable` added to
  robotClass enum; `ASSIST` added to taskType enum (3 schema files modified)
- `runtime_context_exo.json` — 11-service exoskeleton runtime
  (`state.exo_joint_state`, `perception.intent_detector`, `force_control.torque_assist`, …)
- `station_profiles/exo_assembly_a.json` — Hyundai VEX/H-MEX assembly station,
  30 kg limit, families: assist/cobot/assembly
- `sim/acceptance_runner.py` — added read handlers for `perception.intent_detector`,
  `state.exo_joint_state`, `state.fatigue_monitor`, `perception.imu_pose`
- `marketplace/skill_store_index.json` — expanded from 7 to 8 entries
  (vest_exoskeleton: commercial subscription, requiresEntitlement)
- `release_out/etd.hyundai.vest_exoskeleton-0.1.0.zip` — signed release artifact

### Sim module expansion (5 stubs → full implementations)
- `sim/event_replay.py` — full replay engine replacing 4-line stub:
  `replay()` with severity filter (debug/info/warn/error/critical);
  `replay_execution()` for raw dict logs; `nominal_lifecycle()` and
  `aborted_lifecycle()` lifecycle constructors
- `sim/mock_robot_state_generator.py` — `RobotStateGenerator` dataclass with
  per-family state tables (pickplace / weld / transport / humanoid);
  `at()`, `walk()`, `step()`, `reset()`, `primitives()` methods;
  `_PICKPLACE/_WELD/_TRANSPORT/_HUMANOID` as `ClassVar` to avoid dataclass mutable-default error;
  legacy `mock_state()` helper preserved
- `sim/fake_middleware_endpoint.py` — `FakeMiddleware` dataclass: full execution lifecycle
  (`send_request`, `complete`, `get_result`, `cancel`, `active_count`);
  forbidden-command gate (`servo_torque`, `collision_disable`, `emergency_stop_override`);
  `_KNOWN_STATIONS` set; unique execution IDs; legacy module-level `send_request()` preserved
- `sim/failure_scenarios.py` — four deterministic failure scenarios:
  `scenario_missing_service_level_d()`, `scenario_human_in_forbidden_zone()`,
  `scenario_payload_out_of_range()`, `scenario_station_family_mismatch()`;
  `run_all()` runner
- `sim/scenario_runner.py` — rewritten from single-context to 5-tier dispatch
  (base / atlas / wia / mobed / exo); runs all 8 packages with correct runtime context;
  returns structured results with `package`, `valid`, `level`, `score`, `ctx` fields
- `tests/test_sim_modules.py` — 42 new tests covering all five modules (160 total)

### Demo and reporting
- `etd_demo_runner.py` — extended `_CTX_MAP` to include exo context dispatch
- `scripts/release_package.py` — extended auto-detection to include exo keywords
  (`vest`, `exoskeleton`, `exo`)

---

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
