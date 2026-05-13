# ETD Roadmap

## v0.5.0 — Current prototype (complete)

All items below were delivered in the prototype:

- [x] JSON Schema Draft 2020-12 validation (`etd_reference_validator.py`)
- [x] 4-level A–D compatibility scoring
- [x] Package signing (Ed25519 via `cryptography`)
- [x] Release pipeline (validate → sign → zip)
- [x] Skill marketplace (index, entitlement, policy, station compat)
- [x] REST API (`fastapi`, `/store/*`, `/validate`)
- [x] CLI (`validate`, `install`, `stations`, `info`, `serve`)
- [x] 8 reference skill packages (all level A)
- [x] 6 station profiles
- [x] ROS 2 action server/client bridge (dry-run + mocked ROS 2)
- [x] Simulator (scenario runner, failure scenarios, acceptance runner, visualizer)
- [x] 689 tests, all passing; branch coverage ≥ 96%

---

## v0.6.0 — Hardening and fleet readiness

**Goal**: make the runtime safe to deploy in a real pilot workcell.

- [x] **Audit logging.** Every `validate_for_install` written as JSON Lines to
  `logs/etd_audit.jsonl`. Fields: `skill_id`, `station_id`, `timestamp`,
  `operator_id`, `result`, `reason`, `validation_level`. `AuditLog` class in
  `marketplace/audit_log.py`; `audit-log` CLI command for inspection.
- [x] **Package revocation.** Marketplace supports a `revoked.json` blocklist.
  Revoked skill IDs cannot be installed or executed regardless of entitlement.
  `SkillStore._revoked` set loaded at init; `validate_for_install` returns
  `skill_revoked` before any validation for blocked IDs.
- [x] **Fleet rollout policy.** Staged rollout: `draft` → `canary` (1 station) →
  `pilot` (N stations) → `production`. State per skill@version in
  `marketplace/rollout_state.json`. `RolloutPolicy` enforces one-stage-at-a-time;
  `rollout set-stage` / `rollout status` CLI commands.
- [x] **Signature verification at install time.** `verify_package()` called
  silently by `validate_for_install` when `requiresSignature=True`. Missing or
  invalid signature returns `reason="signature_invalid"` before schema validation.
- [x] **Runtime context schema.** Formal JSON Schema for `runtime_context.json`
  so OEM integrators can validate their context files before use.
  `schemas/runtime_context.schema.json` (Draft 2020-12); `validate-context` CLI
  command; `validate_runtime_context()` in `etd_reference_validator.py`.
- [x] **Health check endpoint.** `GET /health` returning validator version,
  loaded packages, station profile count, and revoked skill count.
- [x] **CLI `revoke` command.** Adds a skill ID to the revocation list with
  a reason and timestamp. Writes JSON entry to `marketplace/revoked.json`;
  idempotent (duplicate is detected and skipped).

---

## v0.7.0 — OEM middleware bridge

**Goal**: connect to a real robot's middleware for at least one platform.

- [ ] **ROS 2 action type built.** Compile `ExecuteSkill.action` in a real
  ROS 2 workspace; wire `ETDSkillActionServer` to a running robot node.
- [x] **Hyundai WIA adapter wired to H-Motion.** `adapters/hyundai_wia_adapter.py`
  maps all ETD service topics to H-Motion ROS 2 topic names; `dry_run=True` mode
  with injectable mock state enables full sim/test without hardware; `dry_run=False`
  path stubs `_ros2_read` / `_ros2_publish` for real rclpy integration.
  `HyundaiMobEDAdapter` (H-Rise AMR, `/hrise/*`) and `HyundaiExoAdapter`
  (H-MEX exoskeleton, `/hmex/*`) complete the three-platform Hyundai family.
- [x] **Middleware contract formalized.** `etd_middleware_contract.py` defines
  abstract base class `ETDMiddleware` with typed `read` / `publish` signatures.
  `load_middleware_adapter()` validates required_topics at load time.
  `adapters/registry.py`: `get_adapter_for_skill()` auto-selects the right
  adapter by skill ID prefix; `ETDSkillActionServer` uses the registry so no
  per-skill wiring is needed. `AtlasAdapter` (Orbit / `/atlas/*` topics) and
  `NullMiddleware` complete the built-in set.
- [x] **Telemetry pipeline.** `adapters/telemetry_sink.py`: pluggable
  `TelemetrySink` hierarchy — `NullSink`, `ConsoleSink`, `FileSink`,
  `MQTTSink` (paho-mqtt; stubs to stdout when library absent), `MultiSink`
  (fan-out). `HyundaiWIAAdapter` forwards `telemetry.events` to any configured
  sink, decoupling robot telemetry from OEM middleware publish.
- [ ] **Acceptance tests on hardware.** At least one YAML scenario run against
  a physical cobot (not just `AcceptanceMiddleware`).

---

## v1.0.0 — Production-grade marketplace

**Goal**: publishable, multi-vendor skill store with governed review.

- [x] **Publisher portal.** Web UI for skill package submission, review status,
  and version management. `marketplace/publisher_portal.py`: `SubmissionRecord`
  (full state machine: submitted → in_review → approved | rejected |
  needs_revision), `PublisherPortal` (submit with auto-run of `ReviewPipeline`,
  auto-approve on pass, approve/reject/request_revision/resubmit, persist to
  `submissions.json`). `api/publisher.py`: FastAPI router at `/publisher/*`
  (submit, list, get, approve, reject, revision, resubmit, stats). CLI:
  `etd publisher submit|list|approve|reject|revision`.
- [x] **Automated review pipeline.** On submission: schema validation →
  capability audit → safety boundary check → compatibility matrix generation.
  Human review required for `riskLevel: high` packages.
  `marketplace/review_pipeline.py`: `ReviewPipeline.run()` → `ReviewResult`
  with `passed`, `human_review_required`, `blocking_findings`, `compat_matrix`.
  CLI: `etd review PACKAGE_PATH [--json]`.
- [x] **Signed entitlement tokens.** `marketplace/entitlement_token.py`:
  Ed25519-signed tokens binding `skill_id + station_id + expiry + operator_org`.
  Wire format: `base64url(payload_json).base64url(signature)`. `issue_token()` /
  `verify_token()` using existing NaCl infrastructure. `SkillStore` verifies
  tokens when `entitlement_pubkey_path` is configured; falls back to truthy
  check for backwards-compat. `token issue` / `token verify` CLI commands.
- [x] **Package sandboxing.** Skill adapters run in a restricted Python
  environment: no `subprocess`, no `os.system`, no network access, no file
  writes outside `telemetry/`. `marketplace/sandbox.py`: `SandboxChecker`
  (static AST analysis — forbidden imports, OS calls, builtins, write-outside-
  telemetry) + `SkillSandbox` context manager (runtime `sys.meta_path` blocker).
  Integrated as `sandbox_check` stage 1 in `ReviewPipeline`. CLI:
  `etd sandbox-check PACKAGE_PATH [--json]`.
- [x] **Version negotiation.** Marketplace serves the highest compatible
  version of a skill for a given `runtime: ">=0.x.y"` constraint.
  `marketplace/version_negotiator.py`: `parse_version`, `satisfies` (operators:
  `>=`, `>`, `<=`, `<`, `==`, `!=`, `~=` compatible-release, conjunctions),
  `best_version`, `sort_versions`. `StoreEntry.runtimeConstraint` field.
  `SkillStore.get_versions()` / `get_entry()` use negotiation.
  CLI: `etd versions SKILL_ID [--runtime VERSION]`.
- [x] **Multi-vendor index.** Marketplace can aggregate packages from multiple
  signed publisher feeds (similar to a Linux package repository model).
  `marketplace/vendor_feed.py`: `VendorFeed` (identity + Ed25519 pubkey),
  `FeedRecord` (loaded + verified data), `VendorFeedManager` (register, load,
  aggregate with dedup — verified feeds win, `get_versions`, `find_skill`,
  `list_skills`, `list_feeds`), `create_feed_payload` (sign entries with
  NaCl Ed25519), `verify_feed_signature`. CLI: `etd feed create`, `etd feed
  verify`, `etd feed import [--json]`.
- [x] **Dashboard.** Real-time view of active skills, station health, recent
  aborts, and telemetry event stream. `marketplace/dashboard.py`:
  `DashboardSnapshot` (ASCII render + JSON), `Dashboard.snapshot()` aggregates
  skill store, rollout state, station profiles, audit log; `Dashboard.watch()`
  live refresh loop. `StationHealth` tracks compatible skill count, last event
  timestamp, active/idle status (24 h window). CLI: `etd dashboard [--json]
  [--watch N] [--interval S] [--events N]`. All 7/7 v1.0.0 items complete.

---

## Long-term

- [x] **Humanoid-first marketplace.** As Atlas, Unitree, and Hyundai humanoids
  reach production, ETD becomes the neutral application-layer adapter that
  lets a skill written for one humanoid run (with compat checks) on another.
  `marketplace/cross_platform.py`: `HumanoidPlatform`, `PlatformCompatResult`,
  `HumanoidRegistry` (6 built-in platforms: Atlas, Unitree G1, Unitree H1,
  Hyundai H-MEX, Hyundai MobED, Hyundai WIA), `check_compat()` (family +
  primitive + capability-flag checks with topic namespace remappings),
  `compat_matrix()`, `render_matrix_ascii()`, `load_skill_info()`.
  CLI: `etd platform list|check|matrix [--json]`.
  64 tests in `tests/test_cross_platform.py`.
- [x] **Skill composition.** Higher-level skills that chain primitives from
  multiple sub-skills (e.g. fetch → inspect → assemble) with shared safety
  context.  `marketplace/composer.py`: `SkillStep`, `ComposedSkill`,
  `SafetyContext`, `StepResult`, `ComposedSkillResult`, `SkillComposer`
  (`validate()` + `run()`) with per-step failure policies (`abort` / `skip`
  / `retry`), `mock_executor` (dry-run), `load_composed_skill()`.
  Reference composed skill package at
  `examples/etd.composed.fetch_inspect_place/` (walk-fetch → vision QA →
  pick-and-place).  CLI: `etd compose validate|run [--json]`.
  57 tests in `tests/test_skill_composer.py`.
- [x] **On-robot skill store.** Embedded marketplace running on the robot's
  compute unit, with offline entitlement cache and mesh sync to central index.
  `marketplace/onrobot_store.py`: `CachedEntitlement`, `EntitlementCache`
  (JSON-backed, add/get/evict/list_skills, wildcard-station support),
  `CachedManifest`, `SkillManifestCache` (JSON-backed, put/get/remove),
  `MeshSyncRecord`, `MeshSync` (announce/receive_from_peer/sync_status),
  `OfflineInstallResult`, `OnRobotStore` (install_offline, is_available_offline,
  sync_from_central, get_offline_skills, evict_expired_entitlements).
  CLI: `etd onrobot cache list|add|evict` and `etd onrobot sync status`.
  66 tests in `tests/test_onrobot_store.py`.
- [x] **Fleet management.** Coordinate skill deployment across a fleet of
  robot nodes with per-node compat gating and deployment lifecycle tracking.
  `marketplace/fleet_manager.py`: `RobotNode`, `NodeDeployResult`,
  `FleetDeployment` (pending→in_progress→completed|failed|partial lifecycle,
  `summary()`), `FleetHealthSnapshot` (ASCII render + JSON, skill_coverage
  map), `FleetManager` (register/unregister/heartbeat, `deploy()` with
  cross-platform compat gating, `fleet_status()`, `list_deployments()`,
  persists to `fleet_registry.json` + `fleet_deployments.json`).
  CLI: `etd fleet nodes list|register|unregister`, `etd fleet deploy`,
  `etd fleet status`, `etd fleet deployments [--json]`.
  61 tests in `tests/test_fleet_manager.py`.
- [x] **Skill execution telemetry analytics.** Persistent skill execution
  recording with z-score anomaly detection and fleet-wide reporting.
  `marketplace/telemetry_analytics.py`: `ExecutionEvent`, `ExecutionRecord`
  (with `make()` factory), `SkillStats` (p50/p95/p99 latency, success rate,
  common failures, `summary()`), `TelemetryStore` (JSON-Lines append-only store,
  filtered query), `TelemetryAnalyzer` (`skill_stats`, `node_stats`,
  `recent_failures`, `anomalies` z-score detection, `report`).
  `api/telemetry.py`: FastAPI router at `/telemetry` (record, list, stats,
  report, anomalies endpoints). CLI: `etd telemetry record|stats|anomalies|report`.
  70 tests in `tests/test_telemetry_analytics.py`.
