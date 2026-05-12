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
  `HyundaiWIAAdapter` subclasses it and is tested end-to-end with the WIA skill.
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

- [ ] **Publisher portal.** Web UI for skill package submission, review status,
  and version management.
- [ ] **Automated review pipeline.** On submission: schema validation →
  capability audit → safety boundary check → compatibility matrix generation.
  Human review required for `riskLevel: high` packages.
- [ ] **Signed entitlement tokens.** Replace `entitlement_checked: true` flag
  with a cryptographically signed token that binds `skill_id + station_id +
  expiry + operator_org`.
- [ ] **Package sandboxing.** Skill adapters run in a restricted Python
  environment: no `subprocess`, no `os.system`, no network access, no file
  writes outside `telemetry/`.
- [ ] **Version negotiation.** Marketplace serves the highest compatible
  version of a skill for a given `runtime: ">=0.x.y"` constraint.
- [ ] **Multi-vendor index.** Marketplace can aggregate packages from multiple
  signed publisher feeds (similar to a Linux package repository model).
- [ ] **Dashboard.** Real-time view of active skills, station health, recent
  aborts, and telemetry event stream.

---

## Long-term

- **Humanoid-first marketplace.** As Atlas, Unitree, and Hyundai humanoids
  reach production, ETD becomes the neutral application-layer adapter that
  lets a skill written for one humanoid run (with compat checks) on another.
- **Skill composition.** Higher-level skills that chain primitives from
  multiple sub-skills (e.g. fetch → inspect → assemble) with shared safety
  context.
- **On-robot skill store.** Embedded marketplace running on the robot's
  compute unit, with offline entitlement cache and mesh sync to central index.
