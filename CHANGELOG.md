# Changelog

## 0.80.0 — Skill execution telemetry analytics (1481 → 1551 tests)

Persistent per-skill execution recording, duration statistics, and z-score
anomaly detection with a full REST API layer.

### Code changes

- `marketplace/telemetry_analytics.py` (NEW):
  - `ExecutionEvent`: one primitive-level event (`primitive`, `status`,
    `duration_ms`, `payload`); round-trips to/from dict.
  - `ExecutionRecord`: complete skill run with start/end timestamps, status,
    events list; `make()` factory auto-generates UUID + timestamps.
  - `SkillStats`: p50/p95/p99 latency percentiles, success rate, mean/min/max
    duration, ranked common-failure reasons; `summary()` ASCII render.
  - `TelemetryStore`: JSON-Lines–backed append-only store; filtered `query()`
    (skill\_id, node\_id, status, since, limit); `skill_ids()`, `node_ids()`,
    `clear()`; parent dirs created on first write.
  - `TelemetryAnalyzer`: `skill_stats()` (returns `SkillStats` or None),
    `node_stats()` (per-node health dict), `recent_failures()`, `anomalies()`
    (z-score ≥ threshold, sorted by z desc, requires ≥ 2 non-zero durations),
    `report()` (fleet-wide summary across all skills and nodes).
- `api/telemetry.py` (NEW): FastAPI router at `/telemetry`:
  - `POST /telemetry/executions` → 201 — record one execution (auto-ID or
    explicit `execution_id`/`started_at`/`completed_at`).
  - `GET  /telemetry/executions?skill_id=&node_id=&status=&since=&limit=` — query.
  - `GET  /telemetry/stats/{skill_id}` — `SkillStats.to_dict()`; 404 if no data.
  - `GET  /telemetry/report` — full fleet report.
  - `GET  /telemetry/anomalies?skill_id=&z_threshold=` — outlier executions.
- `api/app.py`: mounts `_telemetry_router`; version bumped to `0.80.0`.
- `etd_cli.py`: new `telemetry` command group:
  - `etd telemetry record --skill S --node N [--status ok|fail] [--duration-ms D]`
  - `etd telemetry stats SKILL_ID [--json]`
  - `etd telemetry anomalies [--skill S] [--threshold T] [--json]`
  - `etd telemetry report [--json]`

### Tests (1481 → 1551, +70)

- `tests/test_telemetry_analytics.py` (+70, NEW):
  - `TestExecutionEvent`: dict keys, round-trip, defaults, missing optional.
  - `TestExecutionRecord`: make factory, succeeded property, to\_dict events,
    round-trip, from\_dict defaults, make with events.
  - `TestPercentile`: empty, single, median, p100, p0.
  - `TestTelemetryStore`: count, record+count, persistence, query no-filter,
    by skill/node/status, limit, newest-first order, skill\_ids, node\_ids,
    clear, clear wipes file, malformed lines skipped, creates parent dirs,
    query since.
  - `TestTelemetryAnalyzer`: stats None for unknown, counts, success rate,
    durations, common failures, percentiles, to\_dict, summary string, node
    stats empty/populated, recent failures, limit=0, anomalies insufficient
    data, zero stdev, detects outlier, sorted desc, skill filter, report
    structure, empty report.
  - `TestTelemetryApiRecord`: 201, has execution\_id, explicit IDs.
  - `TestTelemetryApiList`: 200, empty, after record, filter skill/status, limit.
  - `TestTelemetryApiStats`: 404 unknown, 200 after record, structure.
  - `TestTelemetryApiReport`: 200, structure, empty.
  - `TestTelemetryApiAnomalies`: 200, structure, detects outlier, has z\_score,
    filter by skill.

## 0.79.0 — REST API for cross-platform, fleet, and composer (1430 → 1481 tests)

Extends the FastAPI REST layer to cover all features added in v0.75–v0.78.

### Code changes

- `api/cross_platform.py` (NEW): FastAPI router at `/platform`:
  - `GET  /platform/list` — all registered platforms (array of `to_dict()`)
  - `GET  /platform/platform/{id}` — single platform; 404 if unknown
  - `POST /platform/check` `{skill_info, source, target}` — full compat check
    with `missing_primitives`, `topic_remappings`, `missing_capability_flags`
  - `POST /platform/matrix` `{skill_info?, families?}` — NxN matrix rows
- `api/fleet.py` (NEW): FastAPI router at `/fleet`:
  - `GET  /fleet/nodes` — list all nodes
  - `POST /fleet/nodes` → 201 — register/replace node
  - `GET  /fleet/nodes/{id}` — get node; 404 if unknown
  - `DELETE /fleet/nodes/{id}` — unregister; 404 if unknown
  - `PUT  /fleet/nodes/{id}/heartbeat` `{status, installed_skills?}` → updated node; 404 if unknown
  - `POST /fleet/deployments` → 201 — deploy skill; supports skill_info + source_platform for compat gating
  - `GET  /fleet/deployments?skill_id=&status=` — filtered list
  - `GET  /fleet/deployments/{id}` — single deployment; 404 if unknown
  - `GET  /fleet/status` — `FleetHealthSnapshot.to_dict()`
- `api/composer.py` (NEW): FastAPI router at `/compose`:
  - `POST /compose/validate` `{composed}` — issues list + `valid` bool
  - `POST /compose/run` `{composed}` — dry-run with mock executor
  - `GET  /compose/examples` — list composed skill packages in `examples/`
  - `GET  /compose/examples/{name}/validate` — validate a named example; 404
  - `GET  /compose/examples/{name}/run` — run a named example; 404
- `api/app.py`: mounts all three new routers; version bumped to `0.79.0`.

### Tests (1430 → 1481, +51)

- `tests/test_api_extensions.py` (+51, NEW):
  - `TestPlatformList`: 200, 6 platforms, atlas present, structure.
  - `TestPlatformGet`: known/404/unitree_g1 families.
  - `TestPlatformCheck`: compatible 200, result fields, incompatible (H1),
    topic remappings present, family mismatch.
  - `TestPlatformMatrix`: 200, 30 pairs, no self-pairs, with skill info, family
    filter → 6 pairs.
  - `TestFleetNodes`: list empty, register 201, list after register, get found/
    404, delete/delete-404, heartbeat updates status, heartbeat 404.
  - `TestFleetDeployments`: deploy 201, completed status, result structure,
    list 200, get found, get 404, list filter by skill_id.
  - `TestFleetStatus`: 200, structure keys.
  - `TestComposeValidate`: valid 200, valid result, invalid-no-steps, self-ref
    cycle, response has skill_id.
  - `TestComposeRun`: 200, success status, step results, multi-step (3 steps),
    result structure.
  - `TestComposeExamples`: list, structure (fetch_inspect_place/step_count=3),
    validate example, run example, validate 404, run 404.

## 0.78.0 — Fleet management (1369 → 1430 tests)

Fleet-level coordination layer above the per-robot OnRobotStore.

### Code changes

- `marketplace/fleet_manager.py` (NEW): fleet skill deployment coordination.
  - `RobotNode(node_id, station_id, platform_id, last_seen, status,
    installed_skills, metadata)` — robot descriptor; `to_dict()` /
    `from_dict()`.
  - `NodeDeployResult(node_id, station_id, success, reason, deployed_at)` —
    per-node deployment outcome; `to_dict()` / `from_dict()`.
  - `FleetDeployment(deployment_id, skill_id, version, target_node_ids,
    status, created_at, completed_at, node_results)`:
    - Status lifecycle: `pending → in_progress → completed | failed | partial`.
    - `nodes_succeeded` / `nodes_failed` properties; `summary()` (✓/✗ per
      node); `to_dict()` / `from_dict()`.
  - `FleetHealthSnapshot(generated_at, total_nodes, online/offline/unknown
    _nodes, total/active_deployments, skill_coverage)`: `to_dict()`,
    `render_ascii()` — box-drawing grid with skill coverage bars.
  - `FleetManager(data_dir, check_platform_compat=True)`:
    - Node registry: `register_node()` / `unregister_node()` / `get_node()` /
      `list_nodes()` / `heartbeat(node_id, status, installed_skills)`.
    - `deploy(skill_id, version, target_node_ids, entitlement_tokens,
      skill_info, source_platform)` — for each target node: (1) resolve node;
      (2) optional cross-platform compat gate via `HumanoidRegistry`; (3) mark
      `installed_skills`; (4) record `NodeDeployResult`. Finalises to
      `completed`, `failed`, or `partial`.
    - `get_deployment()` / `list_deployments(skill_id, status)`.
    - `fleet_status()` → `FleetHealthSnapshot`.
    - Persists registry to `fleet_registry.json` and deployments to
      `fleet_deployments.json`; both auto-loaded on init; data dir
      auto-created.
- `etd_cli.py`: `fleet` command group:
  - `fleet nodes list [--json]`
  - `fleet nodes register NODE_ID --station S --platform P`
  - `fleet nodes unregister NODE_ID`
  - `fleet deploy SKILL_ID [--version V] [--nodes N1,N2] [--json]`
    — exits 0 on completed/partial, 1 on failed/no-nodes.
  - `fleet status [--json]`
  - `fleet deployments [--skill S] [--status S] [--json]`
- `api/app.py`: version bumped to `0.78.0`.

### Tests (1369 → 1430, +61)

- `tests/test_fleet_manager.py` (+61, NEW):
  - `TestRobotNode`: defaults, to_dict roundtrip, from_dict defaults.
  - `TestNodeDeployResult`: to_dict roundtrip, from_dict defaults.
  - `TestFleetDeployment`: nodes_succeeded/failed, summary, to_dict roundtrip,
    to_dict counts, valid DEPLOY_STATUSES.
  - `TestFleetHealthSnapshot`: to_dict keys, render_ascii nodes/skills.
  - `TestFleetManagerRegistry`: no nodes, register, replace, unregister
    existing/nonexistent, get None, list, persist, autocreate dir.
  - `TestFleetManagerHeartbeat`: updates status/last_seen/skills, unknown
    node returns False.
  - `TestFleetManagerDeploy`: all-ok→completed, unknown-node→failed,
    partial, updates inventory, no-duplicate skill, completed_at set, result
    fields, persists, platform-compat gates incompatible (mobed), compat OK
    (atlas→G1).
  - `TestFleetManagerDeploymentQueries`: list-all, filter-skill, filter-status,
    get found/not-found, deployment_count.
  - `TestFleetManagerFleetStatus`: node counts, skill coverage, deployment
    count, to_dict, render_ascii.
  - CLI: fleet nodes list (empty/register+list/json/unregister/unregister-ghost),
    fleet deploy (success/json/no-nodes-exits-1), fleet status (ascii/json),
    fleet deployments (empty/json).

## 0.77.0 — On-robot embedded skill store (1303 → 1369 tests)

Implements the final long-term roadmap item: on-robot embedded marketplace
with offline entitlement cache and mesh sync.

### Code changes

- `marketplace/onrobot_store.py` (NEW): on-robot embedded skill store.
  - `CachedEntitlement(skill_id, station_id, operator_org, expiry, token_str,
    cached_at, verified_by_node)` — locally persisted token; `is_expired`
    property; `covers(skill_id, station_id)` with wildcard station support;
    `to_dict()` / `from_dict()`.
  - `EntitlementCache(cache_path, node_id)` — JSON-backed entitlement store:
    - `add(token_str, skill_id, station_id, operator_org, expiry, verify_key)`
      — optional NaCl re-verification; rejects expired tokens; replaces
      existing entry for same (skill_id, station_id); persists immediately.
    - `get(skill_id, station_id)` — returns first non-expired covering entry.
    - `evict_expired()` — prunes stale entries; returns count removed.
    - `list_skills()` — skill IDs with at least one valid token.
    - `entry_count` / `valid_count` properties.
  - `CachedManifest(skill_id, version, family, primitive_order, cached_at,
    source_node, extra)` — cached skill package metadata; `to_dict()` /
    `from_dict()`.
  - `SkillManifestCache(cache_path, node_id)` — JSON-backed manifest store:
    `put()` / `get()` / `remove()` / `list_skills()` / `manifest_count`.
    Records `source_node` on insert; persists on every mutation.
  - `MeshSyncRecord(peer_node_id, last_sync_at, synced_skill_ids,
    sync_count)` — per-peer sync state; `to_dict()` / `from_dict()`.
  - `MeshSync(node_id, manifest_cache)` — in-memory fleet peer-to-peer sync:
    `register_peer()`, `announce(skill_id)` broadcasts local manifests to all
    peers, `receive_from_peer(peer_id)` imports pending announcements into
    local cache and updates sync record, `sync_status()`, `peer_count`,
    `pending_announcement_count`.
  - `OfflineInstallResult(skill_id, station_id, success, reason, entitlement,
    manifest)` — outcome of `install_offline()`; `__str__` shows `[OK]`/`[FAIL]`.
  - `OnRobotStore(cache_dir, node_id)` — top-level façade:
    - `install_offline(skill_id, station_id)` — serves from cache; fails fast
      on missing entitlement or manifest.
    - `is_available_offline(skill_id, station_id)` — True only if both
      entitlement and manifest cached.
    - `sync_from_central(entries, entitlement_tokens)` — updates both caches
      from a central marketplace feed; skips entries with no `skillId`; rejects
      expired tokens; returns stats dict.
    - `get_offline_skills()` — sorted list of skills with both caches populated.
    - `evict_expired_entitlements()` — delegates to `EntitlementCache.evict_expired()`.
    - `summary()` / `to_dict()`.  Cache directory auto-created on init.
- `etd_cli.py`: `onrobot` command group:
  - `onrobot cache list [--cache-dir] [--json]` — shows `OnRobotStore.summary()`.
  - `onrobot cache add SKILL_ID --token T --expiry E [--station] [--org]
    [--cache-dir]` — exits 0 on success, 1 on expired/invalid.
  - `onrobot cache evict [--cache-dir]` — evicts expired entitlements.
  - `onrobot sync status [--cache-dir] [--json]` — shows mesh peer sync state.
- `api/app.py`: version bumped to `0.77.0`.

### Tests (1303 → 1369, +66)

- `tests/test_onrobot_store.py` (+66, NEW):
  - `TestCachedEntitlement`: expiry/not-expired, covers matching/wrong-skill/
    wrong-station/wildcard/expired, to_dict roundtrip, from_dict defaults.
  - `TestEntitlementCache`: empty, add+get, absent→None, expired rejected,
    add replaces existing, evict (injected expired entry), evict no-op,
    list_skills, list excludes expired, valid_count, persists across instances,
    node_id recorded, wildcard station get.
  - `TestCachedManifest`: to_dict roundtrip, from_dict defaults.
  - `TestSkillManifestCache`: empty, put+get, put replaces, get-unknown→None,
    remove existing/nonexistent, list_skills, persists, source_node set.
  - `TestMeshSyncRecord`: to_dict roundtrip, from_dict defaults.
  - `TestMeshSync`: no peers, register, announce known/unknown skill,
    receive imports manifest, receive updates sync record, auto-register peer,
    receive clears pending.
  - `TestOnRobotStore`: not available offline, available after populate, install
    success, no-entitlement fails, no-manifest fails, str result, sync manifests,
    sync tokens, sync skips expired, sync skips missing skillId, get_offline_skills,
    excludes manifest-only, evict, summary, to_dict, cache-dir auto-created.
  - `TestCLIOnRobotCacheList`: list text/JSON.
  - `TestCLIOnRobotCacheAdd`: valid token exits 0, expired exits 1.
  - `TestCLIOnRobotCacheEvict`: evict prints count.
  - `TestCLIOnRobotSyncStatus`: no peers text/JSON.

## 0.76.0 — Humanoid-first cross-platform marketplace (1239 → 1303 tests)

Implements the long-term Humanoid-first Marketplace roadmap item.

### Code changes

- `marketplace/cross_platform.py` (NEW): cross-platform compatibility layer.
  - `HumanoidPlatform(platform_id, name, robot_class, families,
    topic_namespace, supported_primitives, capability_flags)` — describes one
    robot platform; `supports_family()`, `supports_primitive()`, `to_dict()`.
  - Six built-in platforms:
    - `atlas` — Boston Dynamics Atlas; humanoid/manipulator/pickplace/inspect;
      `/atlas` namespace; 19 primitives; capabilities: bipedal, dexterous,
      vision, force-control, human-aware.
    - `unitree_g1` — Unitree G1; humanoid/manipulator/pickplace/inspect;
      `/unitree/g1`; 19 primitives; same capabilities minus human_aware_mode.
    - `unitree_h1` — Unitree H1 (no hands); humanoid/inspect; `/unitree/h1`;
      7 primitives; bipedal locomotion + vision only.
    - `hyundai_mex` — Hyundai H-MEX / VEX Exoskeleton; assist/cobot;
      `/hmex`; 11 primitives; wearable/force-assist/intent-sensing.
    - `hyundai_mobed` — Hyundai MobED AMR; transport; `/hrise`;
      5 primitives; wheeled/load-bearing/nav-stack.
    - `hyundai_wia` — Hyundai WIA H-Motion Cobot; weld/cobot/assembly;
      `/hwia`; 19 primitives; arc-welding/vision/force-control.
  - `PlatformCompatResult(skill_id, source_platform, target_platform,
    compatible, missing_primitives, topic_remappings,
    missing_capability_flags, warnings, adaptation_notes)`:
    `summary()` (✓/✗ ASCII), `to_dict()`.
  - `HumanoidRegistry`: built-in 6-platform registry; `register()` /
    `unregister()` for custom platforms; `get()` / `list_platforms()`.
    - `check_compat(skill_info, source, target)` — checks: same-platform
      short-circuit; family support on target; primitive coverage; capability
      flag diff; generates per-primitive topic remappings
      (`source_ns/prim → target_ns/prim`) when namespaces differ.
    - `compat_matrix(skill_info, families)` — NxN rows for all platform pairs
      (filtered by family overlap when `families` set).
    - `render_matrix_ascii(skill_info, families)` — compact grid with
      `✓`/`✗`/`≈`/`—`/`·` markers.
  - `load_skill_info(package_path)` — reads `skill.json` from a skill package
    directory; returns plain dict.
- `etd_cli.py`: `platform` command group:
  - `platform list [--json]` — table of all registered platforms.
  - `platform check PACKAGE_PATH --source ID --target ID [--json]` — exits 0
    on compatible, 1 on incompatible or missing package.
  - `platform matrix [--skill PKG] [--family FAM] [--json]` — full or
    filtered compat grid.
- `api/app.py`: version bumped to `0.76.0`.

### Tests (1239 → 1303, +64)

- `tests/test_cross_platform.py` (+64, NEW):
  - `TestHumanoidPlatform`: supports_family/primitive, to_dict sorted keys.
  - `TestBuiltinPlatforms`: 6 platforms, families, robot_class, namespaces,
    non-empty primitives.
  - `TestLoadSkillInfo`: Atlas/MobED, missing raises, string path.
  - `TestHumanoidRegistry`: default count, get/None, register adds/replaces,
    unregister removes/silent, list_platforms.
  - `TestCheckCompat`: same-platform, Atlas→G1 compat, Atlas→H1 incompat
    (missing grasp primitives), Atlas→MobED family mismatch, MobED→MobED,
    topic remapping format, unknown target → incompatible, unknown source
    warns, result fields populated, pickplace Atlas→G1, cobot WIA→WIA,
    missing capability flags, inspect Atlas→G1, no remappings on same platform.
  - `TestPlatformCompatResult`: summary COMPATIBLE/INCOMPATIBLE, to_dict keys,
    compatible true/false in dict.
  - `TestCompatMatrix`: 30 pairs without skill_info, 30 with skill_info, family
    humanoid filter (6 pairs), transport filter (0 pairs), row structure, no
    self-pairs.
  - `TestRenderMatrixAscii`: renders, contains platform IDs, contains
    check marks with skill, diagonal is dot.
  - `TestCLIPlatformList`: list text/JSON.
  - `TestCLIPlatformCheck`: compatible exits 0, incompatible exits 1, JSON,
    missing package exits 1.
  - `TestCLIPlatformMatrix`: ASCII, JSON 30 rows, with-skill JSON, family
    filter JSON 6 rows.

## 0.75.0 — Skill composition (1182 → 1239 tests)

Long-term roadmap item: composed multi-step skills with shared safety context.

### Code changes

- `marketplace/composer.py` (NEW): composed skill execution engine.
  - `SkillStep(skill_id, version_constraint, on_failure, retry_count, params)` —
    per-step descriptor; validates `on_failure ∈ {abort,skip,retry}` and
    `retry_count ≥ 0`; `from_dict()` / `to_dict()` using camelCase JSON keys.
  - `ComposedSkill(skill_id, version, name, description, steps)` — manifest
    dataclass; `from_dict()` / `to_dict()` for `composed_skill.json` I/O.
  - `SafetyContext(violations, aborted, abort_reason)` — shared mutable state
    threaded through every step; `record_violation()`, `abort()`, `.safe`
    property.
  - `StepResult(step_index, skill_id, status, attempts, error, duration_ms)` —
    per-step outcome; `.succeeded` property.
  - `ComposedSkillResult(skill_id, version, status, step_results,
    safety_context, total_duration_ms)` — overall outcome; `.summary()` (ASCII
    with ✓/✗/~/!/↺ markers) and `.to_dict()`.
  - `StepExecutor` type alias: `(step, safety_ctx, params) → (bool, str|None)`.
  - `mock_executor` — dry-run default; succeeds unless `SafetyContext` is
    aborted.
  - `SkillComposer(store, runtime_version)`:
    - `validate(composed)` → `List[str]` — checks: non-empty steps, valid
      `on_failure`, no self-reference cycle, store-based skill existence and
      version constraint satisfiability.
    - `run(composed, executor, safety_context)` → `ComposedSkillResult` —
      sequences steps; `abort` policy calls `safety_context.abort()` and marks
      remaining steps `aborted`; `skip` continues; `retry` exhausts
      `retryCount` attempts; executor exceptions caught and turned into failed
      `StepResult`.
  - `load_composed_skill(package_path)` — loads `composed_skill.json` from a
    composed skill package directory.
- `examples/etd.composed.fetch_inspect_place/composed_skill.json` (NEW):
  reference three-step composed skill: `etd.atlas.humanoid_walkfetch` (abort,
  retry×1) → `etd.inspect.vision` (skip) → `etd.pickplace.basic` (abort,
  retry×2).
- `etd_cli.py`: `compose` command group:
  - `compose validate PACKAGE_PATH [--json]` — exits 0 on valid; prints issues
    on error; exit 1 on invalid or missing package.
  - `compose run PACKAGE_PATH [--json]` — dry-run with `mock_executor`; exit
    0 on success, 1 on failure.
- `sim/scenario_runner.py`, `etd_demo_runner.py`, `validate_examples.py`,
  `sim/report_runner.py`: skip `examples/` subdirectories that lack
  `manifest.yaml` so composed-skill packages are not fed to the ETD validator.

### Tests (1182 → 1239, +57)

- `tests/test_skill_composer.py` (+57, NEW):
  - `TestSkillStep`: defaults, invalid `on_failure` raises, negative
    `retry_count` raises, `from_dict` full/defaults, `to_dict` roundtrip, all
    valid `on_failure` values.
  - `TestComposedSkill`: `from_dict` full/defaults, `to_dict` roundtrip.
  - `TestSafetyContext`: initial safe state, violation → unsafe, abort →
    unsafe+reason, multiple violations.
  - `TestStepResult`: `succeeded` true/false for all statuses.
  - `TestMockExecutor`: succeeds on safe ctx, fails on aborted ctx, fails on
    violated ctx.
  - `TestSkillComposerValidate`: valid skill, no-steps, self-reference, multiple
    steps, store-miss, version-unsatisfiable, version-satisfiable, no-constraint.
  - `TestSkillComposerRun`: all-succeed, default mock executor, abort stops
    sequence, skip continues, retry succeeds on 2nd attempt, retry exhausted →
    failed×3, executor exception caught, shared safety context, pre-aborted
    context skips all, duration fields set, result skill_id/version, overall
    failed on skip-step failure.
  - `TestComposedSkillResult`: summary contains skill_id/step ids, `to_dict`
    structure, succeeded/failed/skipped counts, summary shows ×N attempts,
    summary shows safety violations.
  - `TestLoadComposedSkill`: loads example package, step IDs, on_failure
    values, missing dir raises, string path accepted.
  - `TestCLIComposeValidate`: valid example exits 0, `--json` valid, missing
    package exits 1, self-reference in steps → issues in JSON.
  - `TestCLIComposeRun`: example exits 0 with SUCCESS, `--json` status=success
    with 3 step_results, missing package exits 1.

## 0.74.0 — Publisher portal (1137 → 1182 tests)

All v1.0.0 roadmap items now complete including the publisher portal.

### Code changes

- `marketplace/publisher_portal.py` (NEW): submission lifecycle management.
  - `SubmissionRecord(submission_id, skill_id, version, package_path, publisher,
    submitted_at, status, pipeline_passed, human_review_required, review_result,
    blocking_findings, decision_reason, decided_at, decided_by)` — full state
    machine: `submitted → in_review → approved | rejected | needs_revision`.
    `to_dict()` / `from_dict()` for JSON persistence.
  - `PublisherPortal(repo_root, submissions_path, auto_approve_on_pass=True)`:
    - `submit(package_path, publisher)` — runs `ReviewPipeline` immediately;
      auto-approves when all stages pass and `human_review_required=False`;
      persists to `marketplace/submissions.json`
    - `get_submission(id)`, `list_submissions(publisher, status, skill_id)`
    - `approve(id, decided_by, reason)` — from `in_review` or `needs_revision`
    - `reject(id, reason, decided_by)` — from `in_review` or `needs_revision`
    - `request_revision(id, reason, decided_by)` — from `in_review`
    - `resubmit(id)` — from `needs_revision`; re-runs pipeline, keeps same id
    - State transition enforcement: wrong-status raises `ValueError`; unknown id
      raises `KeyError`
- `api/publisher.py` (NEW): FastAPI router at `/publisher`:
  - `POST /publisher/submit` — 404 if path missing; auto-approve or in_review
  - `GET  /publisher/submissions` — filterable by `publisher`, `status`, `skill_id`
  - `GET  /publisher/submission/{id}` — 404 if unknown
  - `POST /publisher/submission/{id}/approve` — 409 if wrong status
  - `POST /publisher/submission/{id}/reject`
  - `POST /publisher/submission/{id}/revision`
  - `POST /publisher/submission/{id}/resubmit`
  - `GET  /publisher/stats` — total, by_status, auto_approved counts
- `api/app.py`: mounts `publisher` router; version bumped to `0.74.0`
- `etd_cli.py`: `publisher` command group:
  - `publisher submit PACKAGE_PATH [--publisher NAME] [--json]`
    exits 0=auto-approved, 2=in_review, 1=error
  - `publisher list [--publisher F] [--status F]`
  - `publisher approve SUBMISSION_ID [--reason] [--by]`
  - `publisher reject SUBMISSION_ID --reason REASON [--by]`
  - `publisher revision SUBMISSION_ID --reason REASON [--by]`

### Tests (1137 → 1182)

- `tests/test_publisher_portal.py` (+45, NEW):
  - `TestStatuses`, `TestSubmissionRecord`, `TestReadSkillMeta`
  - `TestPortalSubmit`: auto-approve real package; high-risk → in_review;
    forbidden-import → in_review; unique IDs; skill_id/version/publisher
    recorded; no-auto-approve flag; real pickplace package; persistence across
    portal instances
  - `TestPortalQuery`: get/unknown-None/list-all/filter-publisher/filter-status/
    newest-first
  - `TestPortalDecisions`: approve/reject/revision move to correct status;
    decided_by/reason set; wrong-status raises; unknown-id raises
  - `TestPortalResubmit`: resubmit after revision keeps ID; wrong-status raises
  - `TestPublisherAPI`: submit valid/404-path/list/get-404/stats/approve-404
  - `TestPublisherCLI`: submit exits 0 or 2; `--json`; nonexistent exits 1;
    list; approve unknown exits 1

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for Publisher portal — all roadmap items
  from v0.5.0 through v1.0.0 are now complete

---

## 0.73.0 — v1.0.0 COMPLETE: dashboard (1098 → 1137 tests)

All 7/7 v1.0.0 roadmap items are now implemented and tested.

### Code changes

- `marketplace/dashboard.py` (NEW): runtime dashboard that aggregates skill
  store, rollout state, station profiles, and audit log into a single view.
  - `StationHealth(station_id, allowed_families, compatible_skill_count,
    last_event_ts, last_result, status)` — per-station summary. Status is
    `'active'` when the latest audit event for the station is within 24 h.
  - `RolloutEntry(skill_id, version, stage, approved_stations, updated_at)`.
  - `RecentEvent(timestamp, skill_id, result, reason, station_id, validation_level)`.
  - `DashboardSnapshot`: `render_ascii(width=62)` — 5-section box drawing
    (SUMMARY | STATION HEALTH | ROLLOUT STATE | RECENT AUDIT EVENTS);
    `to_dict()` — full JSON-serialisable representation; OK/FAIL marks on events.
  - `Dashboard(repo_root, audit_log_path, station_profiles_dir, rollout_state_path)`:
    `snapshot(last_n_events=10)` — reads all data sources, builds snapshot;
    `watch(interval_s, refresh_count, clear_screen)` — refresh loop with
    Ctrl-C exit, parameterised stop count.
- `etd_cli.py`: `dashboard [--json] [--watch N] [--interval S] [--events N]`
  — single snapshot by default; `--watch -1` runs until Ctrl-C.

### Tests (1098 → 1137)

- `tests/test_dashboard.py` (+39, NEW):
  - `TestStationHealth`, `TestRolloutEntry`, `TestRecentEvent`: dataclass fields,
    defaults
  - `TestDashboardSnapshot`: ASCII render (header, SUMMARY, STATION HEALTH,
    ROLLOUT STATE, RECENT EVENTS, placeholders, OK/FAIL marks), `to_dict` keys,
    JSON-serialisable, station health field set, custom width
  - `TestDashboardDataLoading`: no data sources; store entries; rollout; station
    profiles; audit events; `last_n_events` limit; newest-first ordering
  - `TestDashboardSummary`: allowed/blocked counts; rollout_count in summary
  - `TestDashboardStationHealth`: compatible count by family; active (recent
    event); idle (no events); idle (event older than 24 h)
  - `TestDashboardWatch`: `refresh_count=2` renders twice; once no-clear
  - `TestDashboardRealData`: real repo snapshot (≥8 skills, ≥6 stations,
    ≥1 rollout entry); ASCII render ≥10 lines
  - `TestDashboardCLI`: ASCII output; `--json` structure; all sections present;
    `--events 3` limits recent events

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for Dashboard — all 7/7 v1.0.0 items
  complete. ETD marketplace is production-grade.

---

## 0.72.0 — v1.0.0: multi-vendor index (1047 → 1098 tests)

### Code changes

- `marketplace/vendor_feed.py` (NEW): multi-vendor skill index aggregation.
  - `VendorFeed(feed_id, name, public_key_hex)` — publisher identity record.
  - `FeedRecord(feed_id, feed_name, feed_version, entries, verified, error)` —
    loaded feed data with `entry_count` property.
  - `create_feed_payload(feed_id, name, entries, signing_key, feed_version)` →
    signed dict: canonical `json.dumps(entries, sort_keys=True)` signed with
    NaCl Ed25519, base64url-encoded signature.
  - `verify_feed_signature(payload, public_key_hex)` → `(bool, reason)`.
    Reasons: `signature_valid`, `missing_signature`, `signature_invalid`,
    `key_error`, `verification_error`, `nacl_not_available` (soft-pass).
  - `VendorFeedManager`: register/unregister feeds; `load_feed(feed_id, payload)`
    — verifies signature, parses `StoreEntry` objects; `load_feed_from_file(path)`;
    `aggregate()` — deduplicates by `(skillId, version)`, verified feeds win;
    `get_versions(skill_id)`, `find_skill(skill_id, runtime_version)`,
    `list_feeds()`, `list_skills()`, `feed_count`, `total_entries`.
- `etd_cli.py`: `feed` command group:
  - `feed create --id FEED_ID --name NAME [--index INDEX] [--key KEY] [--out OUT]`
    — create and sign a vendor feed from an existing skill store index
  - `feed verify FEED_PATH [--pubkey PUBKEY] [--json]` — verify signature,
    exits 0 on OK / 1 on failure
  - `feed import FEED_PATH [--pubkey PUBKEY] [--json] [--runtime VER]` —
    load, verify, and list entries; exits 0 if verified / 1 if not

### Tests (1047 → 1098)

- `tests/test_vendor_feed.py` (+51, NEW):
  - `TestVendorFeed`, `TestFeedRecord`: dataclass fields, `entry_count`,
    `error` default
  - `TestCreateFeedPayload`: required keys, feed_id preserved, entries count,
    signature string, custom feed_version, roundtrip verify
  - `TestVerifyFeedSignature`: valid sig, wrong key, missing sig, empty sig,
    tampered entries, tampered entry field, invalid pubkey hex
  - `TestVendorFeedManagerRegistration`: register, unregister, unregister clears
    record, load unregistered raises, load-from-file unregistered raises
  - `TestVendorFeedManagerLoading`: verified feed, invalid sig marks unverified,
    entries parsed as `StoreEntry`, load-from-file, feed name/version from payload
  - `TestVendorFeedManagerAggregation`: empty, single feed, two feeds, dedup
    same skill+version, different versions both present, verified wins dedup,
    `feed_count`, `total_entries`
  - `TestVendorFeedManagerQueries`: `get_versions` sorted desc, unknown skill,
    `find_skill` best version, unknown returns None, `list_feeds` keys,
    `list_skills` all entries, `list_skills` keys
  - `TestFeedCLI`: `feed create` creates file; `feed verify` valid exits 0,
    invalid exits 1, `--json` output, missing file; `feed import` valid entries,
    `--json`, invalid sig exits 1

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for multi-vendor index
  (6 of 7 v1.0.0 items complete — only Dashboard remains)

---

## 0.71.0 — v1.0.0: package sandboxing (981 → 1047 tests)

### Code changes

- `marketplace/sandbox.py` (NEW): two-layer sandbox protection.
  - `SandboxChecker` — static AST analysis of every `*.py` file in a package
    (excluding `__pycache__`). Reports:
    - `forbidden_import` — `subprocess`, `socket`, `ssl`, `urllib`, `requests`,
      `httpx`, `aiohttp`, `ftplib`, `smtplib`, `telnetlib`, `paramiko`,
      `multiprocessing`, `threading`, `ctypes`, `cffi`, `pickle`, `marshal`,
      `shelve`, `importlib`, `pty`, `signal`, and more
    - `forbidden_os_call` — `os.system`, `os.popen`, `os.fork`, `os.kill`,
      `os.execv*`, `os.spawn*`, `os.remove`, `os.makedirs`, `os.chmod`, etc.
    - `forbidden_builtin` — `eval`, `exec`, `compile`, `__import__`, `breakpoint`
    - `unrestricted_write` — `open()` with write/append/exclusive mode and a
      static path not under `telemetry/`
    - `syntax_error` — package Python file fails to parse
    Config-only packages (no `.py` files) automatically pass with a note.
  - `SkillSandbox` context manager — installs a `sys.meta_path` `_BlockingFinder`
    that raises `SandboxImportError` (subclass of `ImportError`) for any
    forbidden module import attempted while the sandbox is active. Accepts
    `extra_forbidden` frozenset for additional module roots. Finder is always
    removed on context exit (even if an exception is raised).
- `marketplace/review_pipeline.py`: `sandbox_check` added as **stage 1**
  (before schema_validation). Pipeline now runs 4 named stages:
  `sandbox_check → schema_validation → capability_audit → safety_boundary`.
  Packages with Python files containing forbidden imports/calls fail this stage
  and set `human_review_required = True`.
- `etd_cli.py`: `sandbox-check PACKAGE_PATH [--json]` command. Exits 0 when
  the package passes; exits 1 for violations or missing path.

### Tests (981 → 1047)

- `tests/test_sandbox.py` (+66, NEW):
  - `TestSandboxViolation`: str representation
  - `TestSandboxReport`: passed property, summary PASS/FAIL, `to_dict` shape
    and JSON-serialisability
  - `TestCheckerConfigOnly`: no `.py` files passes + config-only note; real
    example packages pass
  - `TestCheckerForbiddenImports`: `subprocess`, `socket`, `from subprocess`,
    `requests`, `pickle`, `ctypes`, `multiprocessing`, `importlib`, `threading`
    all fail; `os`, `json`, `pathlib` allowed; line number accurate
  - `TestCheckerForbiddenOSCalls`: `os.system`, `os.popen`, `os.fork`,
    `os.kill`, `os.execv`, `os.remove`, `os.makedirs` fail; `os.path.join`,
    `os.path.exists` allowed
  - `TestCheckerForbiddenBuiltins`: `eval`, `exec`, `compile`, `__import__`,
    `breakpoint` fail; `print` allowed
  - `TestCheckerOpenWrite`: write/append outside `telemetry/` fails; write
    inside `telemetry/` and read mode pass; no-mode passes
  - `TestCheckerMultipleFiles`: violations from multiple files collected;
    `python_files` list populated; `__pycache__` excluded; syntax error reported
  - `TestSkillSandbox`: blocks `subprocess`/`socket` (with sys.modules eviction);
    allows `json`/`pathlib`; finder removed after context exit (including on
    exception); `extra_forbidden` installs additional blocker; `SandboxImportError
    is ImportError`
  - `TestReviewPipelineSandboxStage`: config-only passes; forbidden-import fails
    and sets `human_review_required`; sandbox_check is first stage; real
    packages pass
  - `TestSandboxCheckCLI`: clean package exits 0; `--json` output; nonexistent
    path exits 1; forbidden-import package exits 1; output mentions "Sandbox"
- `tests/test_review_pipeline.py`: updated stage count assertion (3 → 4)

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for package sandboxing
  (5 of 7 v1.0.0 items complete)

---

## 0.70.0 — v1.0.0: version negotiation + automated review pipeline (886 → 981 tests)

### Code changes

- `marketplace/version_negotiator.py` (NEW): semver constraint resolution.
  `parse_version(v)` → `(major, minor, patch)` tuple; degrades gracefully on
  invalid input. `satisfies(version, constraint)` supports all operators:
  `>=`, `>`, `<=`, `<`, `==`, `!=`, `~=` (compatible-release: `~=1.2` →
  `>=1.2,<2.0`; `~=1.2.3` → `>=1.2.3,<1.3`), comma-separated conjunctions,
  and bare version (acts as `==`). `best_version(entries, runtime_version)` →
  highest-versioned entry whose `runtimeConstraint` is satisfied, or None.
  `sort_versions(entries, descending=True)` → sorted list.
- `marketplace/skill_store.py`:
  - `StoreEntry` gains `runtimeConstraint: str = ""` field
  - `SkillStore.get_versions(skill_id)` → entries sorted highest-first
  - `SkillStore.get_entry(skill_id, runtime_version)` uses `best_version()`;
    falls back to first entry when no constraint is set
  - `SkillStore.find_skill(skill_id, runtime_version)` uses `get_entry()`
- `marketplace/review_pipeline.py` (NEW): `ReviewPipeline.run(package_path)`
  executes 4 stages and returns a `ReviewResult`:
  1. `schema_validation` — `ETDReferenceValidator` with permissive `_ALL_SERVICES`
     context; blocks on any schema/semantic error
  2. `capability_audit` — verifies `command.skill_intent` is in write caps,
     no high-risk forbidden caps in write list, warns on undeclared forbidden
     and non-standard forbidden declarations
  3. `safety_boundary` — checks force window sign/order/magnitude, payload
     constraint vs profile, `arcZoneRadius_m >= 1.0m`
  4. compat matrix — cross-references station profiles against
     `requiresServices`; produces `robot_classes`, `compatible_stations`,
     `station_count`
  `human_review_required` when `riskLevel == high` or any stage fails.
  `StageResult.passed` defaults to `False` (safe by default).
- `etd_cli.py`:
  - `versions SKILL_ID [--runtime VERSION]` — list all index entries for a
    skill, annotated with constraint satisfaction for the given runtime
  - `review PACKAGE_PATH [--json]` — run full 4-stage review pipeline; exits
    1 when pipeline fails or package path doesn't exist

### Tests (886 → 981)

- `tests/test_version_negotiator.py` (+47, NEW):
  - `TestParseVersion`: 3/2/1-part, invalid, empty, leading whitespace
  - `TestSatisfiesSingle`: all 8 operators, empty/wildcard/bare version
  - `TestSatisfiesConjunction`: range satisfied/upper-fail/lower-fail, 3-part
  - `TestSatisfiesCompatRelease`: `~=` minor and patch variants
  - `TestBestVersion`: single no-constraint, picks highest compatible, newest
    when all compatible, none when none compatible, empty list, conjunction
    constraint, no runtimeConstraint attribute
  - `TestSortVersions`: descending (default) and ascending
  - `TestSkillStoreVersionNegotiation`: `get_versions`, `get_entry`,
    unknown skill, `find_skill` raw dict
  - `TestVersionsCLI`: known skill exit-0, unknown skill exit-1
- `tests/test_review_pipeline.py` (+48, NEW):
  - `TestStageResult`/`TestReviewResult`: dataclass defaults, `passed` property,
    `blocking_findings`, `summary` content, `to_dict` shape
  - `TestPipelineSchemaStage`: valid package passes; real `etd.pickplace.basic`
  - `TestPipelineCapabilityStage`: valid/missing-required/forbidden-cap/
    extra-forbidden-warns/multiple-forbidden
  - `TestPipelineSafetyStage`: valid/high-risk-warns/negative-lower/upper-lt-lower/
    >500N-warns/payload-exceeds/arcZone-<1m/no-profiles/multiple-profiles
  - `TestCompatMatrix`: all keys present, robot_classes/required/optional/
    runtime from manifest, no-compat-section fallback
  - `TestHumanReviewRequired`: clean medium-risk, high-risk, cap fail, safety fail
  - `TestPipelineRealPackages`: 3 packages run without exception, JSON serialisable
  - `TestLoadHelper`: JSON/YAML/`.yml` extension
  - `TestReviewCLI`: valid package exit-0, `--json` output, nonexistent path
    exit-nonzero, high-risk shows warning

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for version negotiation and automated
  review pipeline (4 of 7 v1.0.0 items complete)

---

## 0.69.0 — v1.0.0 start: signed entitlement tokens (850 → 886 tests)

### Code changes

- `marketplace/entitlement_token.py` (NEW): `EntitlementToken` dataclass with
  canonical JSON payload (`sort_keys=True`), `is_expired()`, `covers()`. Wire
  format: `base64url(payload_json).base64url(signature)` using NaCl Ed25519.
  `issue_token(skill_id, station_id, operator_org, signing_key, ttl_days)` →
  opaque string. `verify_token(token_str, verify_key, skill_id, station_id)` →
  `(valid, reason, EntitlementToken|None)` — reasons: `token_valid`,
  `token_expired`, `signature_invalid`, `malformed_token`,
  `token_skill_station_mismatch`, `decode_error`, `payload_parse_error`.
- `marketplace/skill_store.py`:
  - `SkillStore.__init__` accepts optional `entitlement_pubkey_path`; loads
    `VerifyKey` only when explicitly provided (no auto-detection, preserves
    backwards compat for existing `demo-entitlement` tokens)
  - Entitlement token verification moved **before** schema validation (early
    reject: bad token never triggers expensive validation)
- `etd_cli.py`: `token` command group with `issue` (signs with signing key) and
  `verify` (checks signature + expiry + skill/station coverage); both support
  `--json` flag

### Tests (850 → 886)

- `tests/test_entitlement_token.py` (+36, NEW):
  - `EntitlementToken`: canonical payload, sorted keys, `is_expired`, `covers`
    (exact/wildcard/wrong-skill/wrong-station/expired)
  - `issue_token`: roundtrip, ttl_days respected, deterministic payload decoding
  - `verify_token`: valid, wildcard station, wrong skill/station/key, malformed,
    tampered payload, expired, None token on decode error
  - `SkillStore` integration: valid signed token allows, invalid blocks, expired
    blocked with `token_expired`, no-pubkey falls back to truthy
  - CLI: `token issue` output, `--json`, custom station/org; `token verify`
    exit-0/exit-1/`--json`

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for signed entitlement tokens
  (1 of 7 v1.0.0 items complete)

---

## 0.68.0 — v0.7.0: Atlas adapter + registry + action server auto-wiring (803 → 850 tests)

### Code changes

- `adapters/atlas_adapter.py` (NEW): `AtlasAdapter(ETDMiddleware)` mapping 19
  ETD topics to BD Orbit fleet (`/orbit/*`) and Atlas ROS 2 (`/atlas/*`)
  namespaces. Mock state covers `state.safety_state`, `state.balance_state`,
  `perception.scene_map`, `perception.object_pose`. `set_balance()` and
  `set_object_pose()` helpers. `orbit_endpoint` param for live Orbit REST calls.
- `adapters/registry.py` (NEW): `ETDMiddleware` adapter registry.
  `register_adapter(prefix, cls)` for prefix-match or `exact=True` for exact
  match. `get_adapter_class(skill_id)` resolves by longest-prefix; falls back
  to `NullMiddleware`. `get_adapter_for_skill(skill_id, dry_run, sink)` resolves
  and instantiates with correct kwargs via `inspect.signature`. Built-in
  registrations for all 4 platform adapters.
- `integrations/ros2/.../skill_action_server.py`: added `_resolve_middleware()`
  using the registry; `execute_goal()` auto-resolves when `middleware=None`;
  `run_ros2()` auto-instantiates live-mode adapter for the ROS 2 callback.

### Tests (803 → 850)

- `tests/test_atlas_adapter_registry.py` (+47, NEW):
  - `AtlasAdapter` (20 unit + 4 integration): reads/publish/inject/set helpers,
    telemetry sink, orbit_endpoint, live-mode stubs; Atlas walk-fetch skill
    end-to-end + abort + FileSink
  - Registry (14 tests): per-platform class lookup, exact vs prefix match,
    fallback to NullMiddleware, custom registration, TypeError rejection,
    `list_registrations`, NullMiddleware behavior
  - `ETDSkillActionServer` wiring (5 tests): auto-selects WIA/Atlas/Null by
    skill ID; explicit middleware overrides auto-selection; goal completes

### Roadmap

- `docs/roadmap-v0.2.md`: expanded middleware-contract entry to note registry,
  AtlasAdapter, and skill_action_server auto-wiring

---

## 0.67.0 — v0.7.0: MobED + exoskeleton adapters + middleware developer guide (755 → 803 tests)

### Code changes

- `adapters/hyundai_mobed_adapter.py` (NEW): `HyundaiMobEDAdapter(ETDMiddleware)`
  mapping 17 ETD service topics to H-Rise AMR ROS 2 namespace (`/hrise/*`).
  `initial_pose` constructor arg, `set_pose()` convenience helper. Dry-run mock
  includes `state.robot_pose`, `state.safety_state`, `state.battery`.
- `adapters/hyundai_exo_adapter.py` (NEW): `HyundaiExoAdapter(ETDMiddleware)`
  mapping 18 ETD service topics to H-MEX exoskeleton ROS 2 namespace (`/hmex/*`).
  `simulate_fatigue=True` mode increments `fatigue_pct` +5 per read (max 100).
  `set_fatigue()` and `set_intent()` helpers for direct state injection.
  Mock covers `state.exo_joint_state`, `state.fatigue_monitor`,
  `perception.intent_detector`.

### Documentation

- `docs/middleware-developer-guide.md` (NEW): Complete OEM adapter authoring
  guide — ETDMiddleware subclassing, topic mapping, telemetry sink wiring,
  dry-run/inject test pattern, safety boundary contract, 7-item checklist.
  Includes minimal adapter code example and full reference to all three Hyundai
  adapters.

### Tests (755 → 803)

- `tests/test_hyundai_adapters.py` (+48, NEW):
  - `HyundaiMobEDAdapter` (18 unit + 4 integration): safety/pose reads, publish
    recording, inject/set_pose, topic mapping, telemetry sink, live-mode stubs;
    end-to-end transport skill run + abort + FileSink
  - `HyundaiExoAdapter` (22 unit + 4 integration): safety/joint/fatigue/intent
    reads, simulate_fatigue progression + cap at 100, set_fatigue/set_intent,
    topic mapping, telemetry sink; end-to-end exo skill run + abort + FileSink

### Roadmap

- `docs/roadmap-v0.2.md`: expanded Hyundai WIA adapter entry to note MobED and
  exoskeleton adapters completing the three-platform family

---

## 0.66.0 — v0.7.0 start: middleware contract + Hyundai WIA adapter + telemetry pipeline (709 → 755 tests)

### Code changes

- `etd_middleware_contract.py` (NEW): `ETDMiddleware` abstract base class with
  typed `read(topic) → dict` and `publish(topic, message) → None` signatures.
  `required_topics` class variable declared by each adapter. `validate()` checks
  all required topics are reachable at load time. `load_middleware_adapter()` type-
  checks and validates; returns adapter unchanged for chaining.
- `adapters/hyundai_wia_adapter.py` (NEW): `HyundaiWIAAdapter(ETDMiddleware)`
  wiring all ETD service topics to H-Motion ROS 2 topic names
  (`/hmotion/perception/seam_tracker`, `/hmotion/welding/torch_control`, …).
  `dry_run=True` (default): reads from injectable mock-state table, publishes
  recorded to `adapter.published`. `dry_run=False`: stubs `_ros2_read` /
  `_ros2_publish` for real rclpy integration. `inject_state()` helper for tests.
  `telemetry_sink` parameter forwards `telemetry.events` to any `TelemetrySink`.
- `adapters/telemetry_sink.py` (NEW): pluggable telemetry output hierarchy:
  `NullSink` (tests), `ConsoleSink` (stdout), `FileSink` (JSON Lines),
  `MQTTSink` (paho-mqtt; stubs to stdout when absent), `MultiSink` (fan-out,
  swallows per-sink errors). `TelemetrySink` ABC with `emit()` / `close()`.

### Tests (709 → 755)

- `tests/test_middleware_contract.py` (+46, NEW):
  - `ETDMiddleware` contract: ABC enforcement, validate() pass/fail, required_topics
  - `load_middleware_adapter`: TypeError for non-subclass, RuntimeError for missing
    topics, calls validate()
  - `HyundaiWIAAdapter` (25 tests): dry_run reads/publish/inject/topic_for,
    telemetry sink forwarding, live-mode ROS 2 stubs
  - Sinks (15 tests): NullSink, ConsoleSink, FileSink append/parent-creation,
    MultiSink fan-out / fault isolation / close, empty MultiSink
  - Integration (4 tests): WIA weld skill + HyundaiWIAAdapter end-to-end;
    abort on injected human-in-zone; FileSink receives skill events

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for middleware contract formalized, Hyundai
  WIA adapter wired to H-Motion, and telemetry pipeline (3 of 5 v0.7.0 items)

---

## 0.65.0 — v0.6.0 complete: fleet rollout policy + runtime context schema (701 → 709 tests)

### Code changes

- `marketplace/rollout_policy.py` (NEW): `RolloutPolicy` class persisting staged
  rollout state to `marketplace/rollout_state.json`. Stages: `draft` → `canary`
  (exactly 1 station) → `pilot` (≥1 station) → `production`. Enforces
  one-stage-at-a-time advancement; `is_approved_for_station()` gates deployment.
- `schemas/runtime_context.schema.json` (NEW): JSON Schema Draft 2020-12 for
  `runtime_context.json`. Validates `runtime_version` (semver pattern), `robot_class`
  (enum: humanoid, mobile_manipulator, fixed_manipulator, dual_arm, amr,
  exoskeleton, cobot), `available_services` (dot-notation array), `platform_profile`.
- `etd_reference_validator.py`: added `validate_runtime_context(path)` function
  returning `(valid: bool, errors: list[str])`; uses `_CONTEXT_SCHEMA_PATH`.
- `etd_cli.py`:
  - `validate-context` command: validates a `runtime_context.json` file against
    the schema; exits 0/1; supports `--json` flag for machine-readable output
  - `rollout` command group with two subcommands:
    - `rollout set-stage SKILL_ID STAGE --version --station --operator`
    - `rollout status [SKILL_ID]`

### Tests (701 → 709)

- `tests/test_cli.py` (+8):
  - `validate-context` valid file (exit 0), invalid file (exit 1), missing file
    (exit 2), `--json` output parseable
  - `rollout set-stage` canary succeeds, stage-skip raises error (exit 1),
    `rollout status` on empty state, `rollout status` after set-stage shows entry

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for fleet rollout policy and runtime context
  schema — **all 7 v0.6.0 items now complete**

---

## 0.64.0 — v0.6.0: audit logging + signature verification at install time (696 → 701 tests)

### Code changes

- `marketplace/audit_log.py` (NEW): `AuditLog` class writing JSON Lines to
  `logs/etd_audit.jsonl`. Fields: `event_type`, `skill_id`, `timestamp`,
  `result`, `reason`, `validation_level`, `station_id`, `operator_id`.
  `record()` is a no-op when `log_path=None` (safe in tests).
  `read_entries()` parses the log for CLI display.
- `marketplace/skill_store.py`:
  - `SkillStore.__init__` creates `AuditLog(repo_root / "logs" / "etd_audit.jsonl")`
  - `validate_for_install` now accepts `station_id` and `operator_id` kwargs
  - Every exit path (revoked, not_found, signature_invalid, validation_failed,
    entitlement_required, allowed) writes one audit entry via `_audit()`
  - `requiresSignature=True` → calls `verify_package()` silently (stdout
    suppressed via `contextlib.redirect_stdout`); missing/invalid sig returns
    `reason="signature_invalid"` before schema validation
- `etd_cli.py`: added `audit-log` command (`--n`, `--skill`, `--result`,
  `--json` flags); reads `logs/etd_audit.jsonl` and formats entries as table
- `examples/etd.*/package.sig`: re-signed all 8 packages with current key
  (previous sig on etd.pickplace.basic was invalid)

### Tests (696 → 701)

- `tests/test_marketplace.py` (+7): audit entry written on allowed install,
  audit entry written on revoked install, unsigned package blocked with
  `signature_invalid`
- `tests/test_cli.py` (+5): audit-log no-file message, audit-log shows entries
  with filter; revoke tests already in 0.63.0
- `tests/test_signing.py` (fixed 2): `test_verify_missing_sig_file_returns_false`
  and `test_verify_main_exits_one_on_unsigned` now remove package.sig from copy
  before asserting failure (all packages now have valid sigs)
- `tests/test_cli.py` (fixed 1): `test_verify_unsigned_package_fails` similarly
  removes package.sig from tmp copy

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for audit logging and signature
  verification at install time (5 of 7 v0.6.0 items now complete)

---

## 0.63.0 — v0.6.0 feature: package revocation blocklist + health endpoint + CLI revoke

### Code changes

- `marketplace/skill_store.py`:
  - Added `revocation_path` attribute pointing to `marketplace/revoked.json`
  - Added `_load_revoked()` → `set[str]` of revoked skill IDs (loaded at `__init__`)
  - Added `is_revoked(skill_id)` public predicate
  - `validate_for_install()` now checks revocation before any validation; revoked
    skills return `allowed=False, reason="skill_revoked"` immediately
- `etd_cli.py`:
  - Added `revoke` command: takes `SKILL_ID`, `--reason`, `--revoked-by`, `--out`;
    writes JSON entry to `marketplace/revoked.json`; idempotent (duplicate skipped)
- `api/app.py`:
  - `GET /health` now returns `loaded_skills`, `loaded_stations`, `revoked_skills`,
    and `validator_version` in addition to `status` and `version`

### Tests (689 → 696)

- `tests/test_marketplace.py` (+4): revoked skill blocked (`skill_revoked`),
  non-revoked not blocked, no-revoked-file → empty set, `_load_revoked` extracts ids
- `tests/test_cli.py` (+3): revoke writes new file, revoke appends to existing,
  revoke is idempotent on duplicate

### Roadmap

- `docs/roadmap-v0.2.md`: ticked [x] for package revocation, health check endpoint,
  CLI revoke command (all three v0.6.0 items now complete)

---

## 0.62.0 — New: generic cobot skills reference doc (4 packages, derived from package files)

- `docs/cobot-skills-reference.md`: NEW — 260-line reference document derived directly
  from the actual package files in `examples/`
  - `etd.pickplace.basic`: 5 primitives, 2 CHS profiles (small_box, fragile_item),
    8 required services, station compat (assembly_a, logistics_a, cobot_a)
  - `etd.assembly.precision`: 6 primitives, 2 CHS profiles (peg_in_hole,
    connector_insert), contact_probe gate, micro_adjust gate, 10 required services
    (incl. perception.part_alignment and force_control.contact_feedback),
    station compat (assembly_a)
  - `etd.inspect.vision`: 5 primitives, 2 CHS profiles (barcode_qa, defect_scan),
    classify_result gate, report_quality → workflow.job_context publishing,
    station compat (assembly_a, logistics_a, cobot_a)
  - `etd.cobot.safeassist`: 5 primitives, 2 CHS profiles (safe_handover, tool_pass),
    detect_human_ready gate, compliant hold force windows, release_on_confirmation
    gate, station compat (assembly_a, cobot_a)
  - Common section: safety model, middleware contract, skill intent protocol,
    fallback behaviour, compatibility level A for all 4
- `docs/INDEX.md`: added cobot-skills-reference.md entry in Architecture section

---

## 0.61.0 — Publisher guide: real CLI commands, 10-step workflow (171 → 260 lines)

- `docs/publisher-developer-guide.md`: 171 lines → 260 lines
  - Added prerequisites table (etd_cli.py, etd_reference_validator.py,
    scripts/sign_package.py, sim/acceptance_runner.py, sim/failure_scenarios.py)
  - Added 10-step workflow with exact CLI commands for: validate, station-profile
    check, acceptance tests, failure scenarios, keygen, publish/sign, verify,
    install eligibility, store list/info, REST API serve
  - Added station profiles table (7 profiles with coverage descriptions)
  - Added failure scenario table (4 scenarios with expected results)
  - Added REST API endpoints table (/store/list, /store/info, /store/stations,
    /validate, /store/install)
  - Added package author checklist (10 items with how-to-verify commands)
  - Expanded publication stages to Q0–Q7 (Draft through Production-certified)
  - Retained publisher obligations, required metadata JSON, listing template,
    pricing disclosure requirements
- `docs/INDEX.md`: updated publisher-developer-guide.md description

---

## 0.60.0 — Full competitive landscape doc (34 lines → 200 lines)

- `docs/competitive-landscape-unitree.md`: 34 lines → 200 lines
  - Added 9 competitor sections: Unitree, Boston Dynamics/Hyundai, Hyundai Robotics LAB,
    Agility Robotics (Amazon/Digit), Figure/OpenAI (BMW), 1X Technologies, Apptronik
    (Mercedes-Benz/Apollo), Tesla Optimus, ROS 2 ecosystem
  - Each section: platform specs, key partnerships, software model, ETD differentiation
  - Closing summary table (7 competitors vs ETD across 5 dimensions)
  - Strategic conclusion: ETD has no direct competitor as a neutral multi-OEM safety-enforced
    skill distribution standard
- `docs/INDEX.md`: updated description for competitive-landscape-unitree.md

---

## 0.59.0 — Expand Unitree marketplace analysis with UniPwn security case and licensing model

- `docs/unitree-skill-marketplace-analysis.md`: 21 lines → 120 lines
  - Added Unitree G1-D end-to-end platform context (data acquisition, training,
    simulation, one-click deployment)
  - Added confirmed vs unconfirmed facts about Unitree monetization (TechRadar,
    3DNews, robohorizon.com public reporting)
  - Added UniPwn security case study (worm-class vulnerability in Go2, B2, G1, H1
    — concrete argument for package signing, capability sandboxing, revocation,
    and audit logging in any robot skill store)
  - Added safety-metadata principle: a commercial package may protect its IP
    but cannot hide its safety declarations (capabilities, fallback, constraints,
    publisher identity, telemetry events)
  - Added hybrid licensing model table (open-source reference, free proprietary,
    commercial per-site, enterprise-certified, private OEM)
  - Added ETD licensing formula: Core open-source, Reference Skills free/open,
    Industrial Skills commercial/enterprise, Safety Metadata always readable,
    Proprietary Payload may be protected
- `docs/INDEX.md`: updated `unitree-skill-marketplace-analysis.md` description

---

## 0.58.0 — Enrich integration notes with specs from source material

- `docs/hyundai-integration-notes.md`: added Hyundai robot ecosystem section —
  H-Motion AMR (1.5 t), Parking Robot (3.4 t, 1.2 m/s), MobED Alliance (March 2026),
  X-ble Shoulder (first KS-certified wearable in South Korea, March 2026),
  X-ble MEX (medical rehab exo), ACR/DAL-e/Safety Inspection service robots,
  Edge Brain (Hyundai Robotics LAB + DEEPX, January 2026), full Orbit → ETD → Edge
  Brain → OEM stack diagram
- `docs/atlas-integration-notes.md`: added Atlas platform specs table (56 DoF,
  2.3 m reach, 50 kg peak payload, autonomous battery swap, barcode scanning, Orbit
  MES/WMS fleet deployment), Hyundai acquisition context (80 % since 2021, 30 000
  units/year US factory), 4-layer stack diagram, full 9-primitive sequence, gate
  conditions, CHS profiles table, required services, integration boundary

---

## 0.57.0 — INDEX.md descriptions updated to match expanded docs

- Updated `docs/INDEX.md` roadmap, productization, funding, due-diligence,
  and marketplace-architecture entries to reflect their expanded content.

---

## 0.56.0 — Five stub docs expanded to full content

- `technical-due-diligence-checklist.md`: 9 verifiable sections (safety boundary,
  signing, schema, station compat, failure scenarios, coverage, API, dependencies,
  code quality)
- `marketplace-architecture.md`: component diagram, install flow, license tiers,
  safety enforcement at three checkpoints
- `roadmap-v0.2.md`: v0.5.0 done, v0.6.0 hardening, v0.7.0 OEM bridge,
  v1.0.0 production marketplace, long-term vision
- `productization-notes.md`: positioning, target segments, differentiators,
  4-phase go-to-market, risks/mitigations
- `funding-pitch-outline.md`: full pitch structure — problem, solution, traction,
  market, business model, ask, why now

---

## 0.55.0 — Four stub docs expanded to full technical reference

- `architecture.md`: layered stack diagram, all components, ETD mapping system,
  execution flow, station compatibility, safety invariants
- `atlas-integration-notes.md`: all 9 primitives with gate conditions, CHS
  profiles table, handover timeout, integration boundary
- `package-format.md`: every package file with schema examples, naming
  conventions, validation levels A–D
- `use-cases-automotive.md`: one section per skill with automotive context,
  profiles, gate conditions; platform/station mapping table

---

## 0.54.0 — Hyundai integration notes + Atlas expansion + INDEX corrections

- Added `docs/hyundai-integration-notes.md`: all three Hyundai platforms
  (WIA welding, MobED AMR, VEX exoskeleton) — primitives, ETD layer roles,
  integration boundaries, safety model, middleware contract
- Updated `docs/INDEX.md`: new hyundai doc linked, test counts corrected
  (160→689, acceptance 39→98)
- Updated `README.md`: hyundai-integration-notes referenced in key docs list

---

## 0.53.0 — ROS2 client 93%→98%: feedback callback + sys.path.insert branch (689 tests)

### Coverage additions
- `tests/test_ros2_bridge.py` (41 → 43 tests):
  - **`_local_execute` `sys.path.insert` branch (line 52)**: temporarily strip bridge dir from `sys.path` via monkeypatch → condition is True → line 52 executes → bridge dir re-inserted
  - **`_ros2_execute` feedback callback body (lines 93-94)**: capture `_fb_callback` from `send_goal_async`; first `spin_until_future_complete` call invokes it with a fake feedback message → `feedback_received.append` + `logger.info` both covered

### Coverage deltas
| File | Before | After |
|---|---|---|
| `skill_action_client.py` | 93% | 98% |

### Test totals by module (689 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 52 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 225 |
| `test_acceptance.py` | 98 |
| `test_ros2_bridge.py` | 43 |
| `test_signing.py` | 62 |

---

## 0.52.0 — visualizer plt.show() no-save path + README count corrections (687 tests)

### Coverage additions
- `tests/test_sim_modules.py` (224 → 225 tests):
  - **`_plot_gantt` `plt.show()` branch (line 259)**: call `_plot_gantt([trace])` without `save_path`; `matplotlib.use` and `plt.show` patched directly on already-imported real modules → `else: plt.show()` covered; visualizer.py 98% → 99%

### README corrections
- `test_acceptance.py`: corrected count 100 → 98 (parametrize expansion ≠ function count)
- `test_sim_modules.py`: corrected count 227 → 225 (same reason)

### Coverage deltas
| File | Before | After |
|---|---|---|
| `sim/visualizer.py` | 98% | 99% |

### Test totals by module (687 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 52 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 225 |
| `test_acceptance.py` | 98 |
| `test_ros2_bridge.py` | 41 |
| `test_signing.py` | 62 |

---

## 0.51.0 — ROS2 bridge full mock: server callback capture + client timeout/reject/happy-path (686 tests)

### Coverage additions
- `tests/test_ros2_bridge.py` (35 → 41 tests):
  - **Server `_execute_callback` body + `rclpy.spin`/`shutdown` (lines 136-156)**: inject both `rclpy` and `etd_ros2_bridge.action` fakes; `_FakeActionServer` captures the callback; `rclpy.spin` raises `KeyboardInterrupt` → `finally: rclpy.shutdown()` executed; callback invoked manually with fake goal handle → lines 136-148 covered
  - **Client timeout path (lines 84-86)**: full rclpy mock with `wait_for_server` returning False → `rclpy.shutdown()` called + `TimeoutError` raised
  - **Client goal-rejected path (lines 100-102)**: `goal_handle.accepted=False` → returns `{'status': 'rejected', 'reason': 'goal_rejected_by_server'}`
  - **Client happy path (lines 103-109)**: `goal_handle.accepted=True`, chained `get_result_async()` mock with JSON result → `json.loads(...)` produces result dict, `rclpy.shutdown()` called

### Coverage deltas
| File | Before | After |
|---|---|---|
| `skill_action_server.py` | 74% | 98% |
| `skill_action_client.py` | 55% | 93% |

### Test totals by module (686 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 52 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 227 |
| `test_acceptance.py` | 100 |
| `test_ros2_bridge.py` | 41 |
| `test_signing.py` | 62 |

---

## 0.50.0 — assembly.precision no-middleware defaults + seat_verify failure (680 tests)

### Coverage additions
- `tests/test_acceptance.py` (99 → 100 tests):
  - **assembly.precision `_read_perception` else-branch (line 92)**: `run(middleware=None)` → `hasattr(None, 'read')` False → returns hardcoded `{'confidence': 0.95, 'offset_mm': 0.2, 'aligned': True}`
  - **assembly.precision `_publish` no-op (line 96->exit)**: same call → `hasattr(None, 'publish')` False
  - **assembly.precision `insertion_push` direct-publish skip (lines 174->194)**: `hasattr(None, 'publish')` False → `command.skill_intent` not published
  - **`seat_verify` insufficient-seating-force abort**: `normal_force_n` defaults to 0.0 (not in default dict) → `0.0 < seat_force_n*0.8=12.0` → abort with `insufficient_seating_force`

### Coverage deltas
| File | Before | After |
|---|---|---|
| `examples/etd.assembly.precision/policies/chs_adapter.py` | 93% | 97% |

### Test totals by module (680 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 52 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 227 |
| `test_acceptance.py` | 100 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 62 |

---

## 0.49.0 — CLI _check_station_entry None early-return + serve uvicorn, verify_signature no-sig error (679 tests)

### Coverage additions
- `tests/test_cli.py` (50 → 52 tests):
  - **`_check_station_entry(None)` early return (line 110)**: monkeypatch `find_skill` to return None → after `decision.allowed=True`, `entry=None` → `if not entry: return` fired → no station output
  - **`serve` command body (lines 282-285)**: inject fake uvicorn via `sys.modules` → `import uvicorn` resolves to mock → `uvicorn.run('api.app:app', ...)` called → lines 282-285 covered
- `tests/test_signing.py` (61 → 62 tests):
  - **`verify_package` no-sig-file path (lines 42-43)**: call `verify_package` on empty tmp dir (no `package.sig`) → `if not sig_path.exists():` True → error printed to stdout → False returned

### Coverage deltas
| File | Before | After |
|---|---|---|
| `etd_cli.py` | 96% | 98% |
| `scripts/verify_signature.py` | 92% | 97% |

### Test totals by module (679 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 52 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 227 |
| `test_acceptance.py` | 99 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 62 |

---

## 0.48.0 — cobot/mobed/inspect no-middleware defaults + mobed mid-segment abort (676 tests)

### Coverage additions
- `tests/test_acceptance.py` (95 → 99 tests):
  - **cobot `_read_human_state` else-branch (line 87)**: `run(middleware=None)` → `hasattr(None, 'read')` False → hardcoded human-present defaults returned
  - **cobot `_publish` no-op (line 92->exit)**: same call → `hasattr(None, 'publish')` False
  - **cobot `social_approach` direct-publish skip (line 148->190)**: `hasattr(None, 'publish')` False → `command.skill_intent` not published
  - **cobot `handover_transfer` direct-publish skip (line 182->184)**: same → `command.skill_intent` not published; `time.sleep(0.3)` (mocked) still runs
  - **mobed `_read` else-return (line 76)**: `run(middleware=None)` → `hasattr(None, 'read')` False → returns `{}`
  - **mobed `_publish` no-op (line 69->exit)**: same call → no-op
  - **mobed `navigate_to_destination` early return (line 160)**: counter middleware safe for first 7 safety reads (navigate_to_pickup primitive+4 steps, dock_and_lift, navigate_to_destination primitive) → read 8 (inside segment) returns `human_in_forbidden_zone=True` → `_navigate_segment` returns error dict → `return err` at line 160
  - **inspect `_publish` no-op (line 104->exit)**: `run(middleware=None)` → no-op
  - **inspect `scan_target` direct-publish skip (line 149->183)**: `hasattr(None, 'publish')` False
  - **inspect `report_quality` direct-publish skip (line 180->183)**: same

### Coverage deltas
| File | Before | After |
|---|---|---|
| `examples/etd.cobot.safeassist/policies/chs_adapter.py` | 92% | 97% |
| `examples/etd.hyundai.mobed_transport/policies/chs_adapter.py` | 93% | 97% |
| `examples/etd.inspect.vision/policies/chs_adapter.py` | 94% | 97% |

### Test totals by module (676 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 50 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 227 |
| `test_acceptance.py` | 99 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 61 |

---

## 0.47.0 — adapter no-middleware defaults, vest-exo lumbar + read-only, atlas handover loop, wia mid-traverse abort, validate_examples failing-package (672 tests)

### Coverage additions
- `tests/test_acceptance.py` (87 → 95 tests):
  - **vest_exoskeleton `_safety_state/_joint_state/_intent/_fatigue` else-branches (lines 98,104,110,116)**:
    `run(middleware=None)` → `hasattr(None, 'read')` False → hardcoded defaults returned
  - **vest_exoskeleton `_publish` no-op (line 120->exit)**: same middleware=None call → `hasattr(None, 'publish')` False
  - **vest_exoskeleton `engage_assist` lumbar branch (line 202)**: middleware reads `mode='lumbar'` →
    `elif mode == 'lumbar':` True → `assist.lumbar_mode_entered` published
  - **vest_exoskeleton `engage_assist` no-publish skip (line 204->212)**: read-only middleware
    (has `read`, no `publish`) → `hasattr(mw, 'publish')` False → torque publish skipped, `assist_cycles += 1` still runs
  - **atlas `_read_state` defaults dict (lines 123-136)**: `run(middleware=None)` → returns
    hardcoded robot-state defaults (pose, balance, safety, scene, object)
  - **atlas `_emit_intent/_publish` no-op (lines 152->exit, 157->exit)**: same call → no `publish` attr → both guards False
  - **atlas handover while-loop sleep (line 297)**: `human_handover` profile + counter middleware
    → first poll returns `human_ready_signal=False` → `time.sleep(0.05)` hit → second poll True → accepted
  - **wia `_read` empty-return (line 87)**: `run(middleware=None)` with `tack_weld` → `hasattr(None, 'read')` False → `{}`
  - **wia `_publish` no-op (line 80->exit)**: same call → `hasattr(None, 'publish')` False
  - **wia mid-traverse safety abort (lines 163-168)**: counter middleware safe for first 4 safety
    reads → read 5 (inside traverse loop step) returns `human_in_forbidden_zone=True` →
    `welding.arc_stopped` + `skill.aborted` published → returns `aborted/weld_traverse`
- `tests/test_sim_modules.py` (226 → 227 tests):
  - **`validate_examples.main()` with failing validator (lines 53-54, 56, 58)**: monkeypatch
    `ETDReferenceValidator` to return `valid=False, errors=['schema_check_failed']` → `'  ! schema_check_failed'`
    printed for each package → `failed` list populated → `SystemExit` raised with joined names

### Coverage deltas
| File | Before | After |
|---|---|---|
| `examples/etd.hyundai.vest_exoskeleton/policies/chs_adapter.py` | 89% | 98% |
| `examples/etd.hyundai.wia_welding/policies/chs_adapter.py` | 91% | 98% |
| `examples/etd.atlas.humanoid_walkfetch/policies/chs_adapter.py` | 91% | 95% |
| `validate_examples.py` | 80% | 94% |

### Test totals by module (672 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 50 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 227 |
| `test_acceptance.py` | 95 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 61 |

---

## 0.46.0 — _plot_gantt matplotlib path + --save branch, publish no-skip-sign, station entry missing-services + warning (664 tests)

### Coverage additions
- `tests/test_sim_modules.py` (224 → 226 tests):
  - **`_plot_gantt` matplotlib happy path (lines 222–259)**: matplotlib IS installed → Agg backend
    → `_plot_gantt([trace], save_path=str(tmp_path/'gantt.png'))` → PNG file created
  - **`visualizer.main()` `--save` flag (line 303)**: `'if args.plot or args.save:'` True →
    `_plot_gantt(traces, save_path=args.save)` called; PNG exists and `'Chart saved'` printed
- `tests/test_cli.py` (47 → 50 tests):
  - **`publish` `if skip_sign:` False branch (line 161->163)**: invoke without `--skip-sign` →
    condition False → `--skip-sign` NOT appended to subprocess cmd → release_package.py runs
    without it (signing skipped due to missing key, but exits 0)
  - **`_check_station_entry` `if result.missing_services:` True (line 123)**: monkeypatch
    `find_skill` with entry `requiredServices=['svc.not.at.station']`; mobed_logistics_a has
    services that exclude it → `missing_services` non-empty → `'Missing services'` printed
  - **`_check_station_entry` `for w in result.warnings:` body (line 125)**: monkeypatch
    `find_skill` with `requiresHumanAware=True`; logistics_cell_a has `requires_human_aware=False`
    → warning `'skill_requires_human_aware_...'` added → loop body executed and printed

### Test totals by module (664 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 50 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 226 |
| `test_acceptance.py` | 87 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 61 |

---

## 0.45.0 — API decision-None/policy-missing 404s, acceptance failed-suite exit, CLI warnings + install-None branches (659 tests)

### Coverage additions
- `tests/test_api.py` (33 → 35 tests):
  - **`POST /store/install` `decision is None` → 404**: mock `validate_for_install()` returns None
    → defensive `if decision is None:` guard fires → 404 `'Skill not found'`
  - **`GET /store/policy` file missing → 404**: monkeypatch `api.app.ROOT` to `tmp_path` (no
    `marketplace/marketplace_policy.json`) → `if not policy_path.exists():` → 404
- `tests/test_acceptance.py` (86 → 87 tests):
  - **`main()` failed suites → print count + `SystemExit(1)`**: fake `run_suite` returns
    `failed=1` → `if failed:` True → prints `'(1 FAILED)'` → `if any(s.failed > 0):` True →
    `raise SystemExit(1)`
- `tests/test_cli.py` (45 → 47 tests):
  - **`_print_report` `if report.warnings:` True branch**: monkeypatch
    `etd_reference_validator._JSONSCHEMA_AVAILABLE = False` → validator adds jsonschema warning
    → `'Warnings:'` and `'jsonschema not installed'` appear in output
  - **`install` `if decision is None:` guard**: monkeypatch `SkillStore.validate_for_install`
    to return None → `'Skill not found'` echoed to stderr → `sys.exit(1)`

### Test totals by module (659 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 35 |
| `test_cli.py` | 47 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 224 |
| `test_acceptance.py` | 87 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 61 |

---

## 0.44.0 — replay no-data key, acceptance main() no-skill scan, whitespace pub-key, signing else-branch, manifest-parse exception (654 tests)

### Coverage additions
- `tests/test_orbit_bridge.py` (38 → 39 tests):
  - **`replay_skill_log` event without 'data' key**: `e.get('data')` returns None →
    `to_enterprise_event(data=None)` → `data or {}` → envelope `'data': {}`
- `tests/test_acceptance.py` (85 → 86 tests):
  - **`acceptance_runner.main()` no-`--skill` arg else-branch**: directory scan of
    `examples/` → all 8 packages discovered and passed to `run_suite`; verified via
    monkeypatched `run_suite` tracking calls
- `tests/test_signing.py` (58 → 61 tests):
  - **`verify_package` whitespace-only pub-key file**: `pub_key_path.exists()` True but
    content is `'   \n\t\n   '` → `strip()` → `''` → `if not verify_hex:` → False
  - **`release_package.main()` signing else-branch**: key file exists + `--skip-sign` not
    set → `else:` block at step 2 → `sign_package(pkg, key_path)` called → `package.sig`
    written; verified by `str(sk_path)` as absolute `--key` arg (`ROOT / abs` = `abs`)
  - **`release_package.main()` manifest-parse `except Exception: pass`**: mock validator
    returns `valid=True`, manifest.yaml contains invalid YAML → `yaml.safe_load` raises
    `yaml.YAMLError` → caught → `version` stays `'0.1.0'` → zip filename contains `0.1.0`

### Test totals by module (654 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 33 |
| `test_cli.py` | 45 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 39 |
| `test_sim_modules.py` | 224 |
| `test_acceptance.py` | 86 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 61 |

---

## 0.43.0 — ascii_timeline empty-result/no-summary-keys/zero-duration, run_traced open-primitive cleanup (649 tests)

### Coverage additions
- `tests/test_sim_modules.py` (220 → 224 tests):
  - **`ascii_timeline` `if trace.result:` False branch**: `trace.result = {}` (empty dict) →
    falsy → inner block skipped → no "Result:" line in output
  - **`ascii_timeline` `if summary_keys:` False branch**: result is truthy but contains no
    known summary keys (`pass_qc`, `payload_kg`, `confidence`, `handover_accepted`) →
    `summary_keys = []` → falsy → "Result:" line omitted
  - **`ascii_timeline` zero-duration `or 1.0` fallback**: `end == start` →
    `total_duration = 0.0` → `total = 0.0 or 1.0 = 1.0` → no ZeroDivisionError in bar rendering
  - **`run_traced` open-primitive cleanup**: monkeypatched `_load_adapter_run` returns a
    function that publishes `primitive.entered` but no `primitive.exited` → after `run_fn()`
    returns, `if mw._current_primitive:` True → `mw._current_primitive.end = trace.end`

### Test totals by module (649 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 33 |
| `test_cli.py` | 45 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 38 |
| `test_sim_modules.py` | 224 |
| `test_acceptance.py` | 85 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 58 |

---

## 0.42.0 — test_id name/unknown fallback, _load_run default entrypoint, pick_context path-not-exists (646 tests)

### Coverage additions
- `tests/test_acceptance.py` (82 → 85 tests):
  - **`test_id` 'name' fallback**: `test.get('id', test.get('name', 'unknown'))` — 'name'
    key used when 'id' is absent → `r.test_id == 'my_named_test'`
  - **`test_id` 'unknown' fallback**: neither 'id' nor 'name' key present →
    `r.test_id == 'unknown'`
  - **`_load_run` default entrypoint**: `skill.json` without 'entrypoint' key →
    `skill_json.get('entrypoint', 'policies/chs_adapter.py:run')` default branch →
    loads `policies/chs_adapter.py:run`; returned function is callable
- `tests/test_sim_modules.py` (219 → 220 tests):
  - **`marketplace_demo._pick_context` `path.exists()` False branch**: keyword matches
    ('humanoid') but context file patched to nonexistent path → `path.exists()` → False
    → loop falls through → `default_runtime_context()` returned

### Test totals by module (646 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 33 |
| `test_cli.py` | 45 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 38 |
| `test_sim_modules.py` | 220 |
| `test_acceptance.py` | 85 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 58 |

---

## 0.41.0 — timestamp zero preserved, failure-scenario detail else-branches (642 tests)

### Coverage additions
- `tests/test_orbit_bridge.py` (37 → 38 tests):
  - **`timestamp_ms=0` is not None → value preserved**: `to_enterprise_event` uses
    `timestamp_ms is not None` guard; passing 0 (falsy but not None) must NOT be overwritten
    by `int(time.time() * 1000)` — verifies the correct `is not None` pattern
- `tests/test_sim_modules.py` (216 → 219 tests):
  - **`scenario_missing_service_level_d` detail else-branch**: monkeypatched validator returns
    level='A' → `passed=False` → `detail = 'expected level D, got A'`
  - **`scenario_payload_out_of_range` detail else-branch**: monkeypatched `check_skill_compatible`
    always returns `compatible=True` → `passed=False` → `detail = 'unexpected compat: ...'`
  - **`scenario_station_family_mismatch` detail else-branch**: same monkeypatch →
    `passed=False` → `detail = 'unexpected result: ...'`

### Test totals by module (642 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 33 |
| `test_cli.py` | 45 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 38 |
| `test_sim_modules.py` | 219 |
| `test_acceptance.py` | 82 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 58 |

---

## 0.40.0 — non-dict manifest meta fallback, inject-no-safety-state, all-required-services-present, CLI missing-services text (638 tests)

### Coverage additions
- `tests/test_validator.py` (58 → 59 tests):
  - **`isinstance(manifest, dict)` False branch → `meta = {}`**: patched `_load` to return a
    non-dict object with `.get()` for `manifest.yaml` → `isinstance` guard at line 181 takes
    else branch → `meta = {}` → `semantic['name_matches_skill_id'] = False`
- `tests/test_acceptance.py` (81 → 82 tests):
  - **`inject` dict without `at_primitive` AND without `safety_state`**: `inject_spec` truthy,
    `'at_primitive' not in inject_spec` → line 186 branch taken; `inject_spec.get('safety_state')`
    returns None → `initial_safety=None` → middleware uses defaults → skill completes
- `tests/test_station_profiles.py` (38 → 39 tests):
  - **`available_services` non-empty, all required services present → `missing_services=[]` → compatible**:
    exercises the inner `if missing_services:` False path when station has services
    but none are missing; confirms compatible=True without early return
- `tests/test_cli.py` (44 → 45 tests):
  - **`_check_station` text output: `if result.missing_services:` prints "Missing services"**:
    custom package with `requiredServices` containing a service absent from station's
    `available_services` → text output shows `Missing services: some.missing.service`

### Test totals by module (638 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 59 |
| `test_api.py` | 33 |
| `test_cli.py` | 45 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 39 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 216 |
| `test_acceptance.py` | 82 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 58 |

---

## 0.39.0 — release validation failure, station human-aware warning, non-dict schema fallback (634 tests)

### Coverage additions
- `tests/test_signing.py` (57 → 58 tests):
  - **`release_package.main()` validation failure → exit-1**: empty package dir fails validation
    → `if not rep.valid:` branch → prints `Validation FAILED:` + raises `SystemExit(1)`
- `tests/test_cli.py` (43 → 44 tests):
  - **`validate` with station that does not enforce human-aware warns in text output**:
    skill has `humanAware: true`, station has `requires_human_aware: false` →
    `_check_station` emits `skill_requires_human_aware_but_station_does_not_enforce_it` warning
- `tests/test_validator.py` (57 → 58 tests):
  - **`_JSONSCHEMA_AVAILABLE=False` + non-dict document → `False` schema result**:
    `execution_contract.json` replaced with JSON array `[]` → `isinstance(doc, dict)` is `False`
    → `schema_results['execution_contract'] = False`

### Test totals by module (634 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 58 |
| `test_api.py` | 33 |
| `test_cli.py` | 44 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 38 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 216 |
| `test_acceptance.py` | 81 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 58 |

---

## 0.38.0 — inject empty patch, legacy expected key, missing telemetry key, marketplace exit-1, API find_skill None (631 tests)

### Coverage additions
- `tests/test_acceptance.py` (79 → 81 tests):
  - **`inject` with `at_primitive` but no nested keys**: `inject_at[at_prim] = {}`
    (empty dict comprehension) — middleware receives an empty patch at the primitive,
    state unchanged, skill completes normally
  - **Legacy `expected` key fallback**: `expect = test.get('expect', test.get('expected', {}))`
    exercises the second `.get('expected', {})` branch when `expect` key is absent
- `tests/test_validator.py` (56 → 57 tests):
  - **Missing `telemetry` key in manifest → `or {}` fallback**: `(manifest.get('telemetry') or {}).get('events', [])` — removes `telemetry` key entirely → `None or {}` → no crash; with events.json also cleared, `telemetry_has_lifecycle_event=False`
- `tests/test_sim_modules.py` (215 → 216 tests):
  - **`marketplace_demo.main()` exit-1 path**: monkeypatched `validate_for_install` returns
    `allowed=False` → `if not all(item['allowed'] ...)` → `raise SystemExit(1)`
- `tests/test_api.py` (32 → 33 tests):
  - **`/store/install` `station_id` + `find_skill` returns None**: patches `_store.find_skill`
    to return `None` → `if entry:` False → station_compatible NOT added to response

### Test totals by module (631 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 57 |
| `test_api.py` | 33 |
| `test_cli.py` | 43 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 38 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 216 |
| `test_acceptance.py` | 81 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 57 |

---

## 0.37.0 — inspect barcode_qa path, legacy YAML key, API station compatible, WIA profile fallback (626 tests)

### Coverage additions
- `tests/test_acceptance.py` (75 → 79 tests):
  - **`inspect.vision` barcode_qa profile**: `scan_mode='barcode'` → `_classify_barcode`
    called (not `_classify_defects`); confidence 0.97 ≥ 0.88 → `pass_qc=True`;
    `defects_found=[]` (no defect model in barcode path)
  - **`run_suite` legacy `scenarios` key**: `spec.get('tests', spec.get('scenarios', []))`
    fallback — YAML with `scenarios:` key (not `tests:`) loads correctly; suite runs
    1 test, passes
  - **WIA welding unknown `chsProfile` falls back to `standard_seam`**:
    `_PROFILE_DEFAULTS.get(name, _PROFILE_DEFAULTS['standard_seam'])` default →
    amperage=160, seam_length=150 confirmed in result
- `tests/test_api.py` (31 → 32 tests):
  - **`/store/install` `station_id` compatible path**: `etd.assembly.precision` +
    `assembly_station_a` (allows `assembly` family) → `station_compatible=True`,
    `station_reason='station_compatible'`, `station_missing_services=[]`

### Test totals by module (626 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 56 |
| `test_api.py` | 32 |
| `test_cli.py` | 43 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 38 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 215 |
| `test_acceptance.py` | 79 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 57 |

---

## 0.36.0 — adapter branch coverage: exo gain/mode, cobot speed, assembly threshold, infra fallbacks (622 tests)

### Coverage additions
- `tests/test_acceptance.py` (71 → 75 tests):
  - **Exo `adapt_gain` below fatigue threshold**: `fatigue_pct=50 < threshold=70` →
    `if fatigue_pct >= ctx.fatigue_threshold_pct` is False → `final_gain` stays 1.0,
    `assist.mode_switched` NOT published
  - **Exo `engage_assist` mode='reach'**: falls through both `if mode == 'overhead':`
    and `elif mode == 'lumbar':` → neither overhead nor lumbar event published, but
    `assist.torque_applied` IS published; skill completes
  - **Cobot `social_approach` missing `human_in_safety_radius` key**: `human.get(...)`
    returns None → falsy → `speed_factor = 0.8` (not 0.4); confirmed via
    `command.skill_intent` capture; skill completes
  - **Assembly `vision_align` confidence exactly at threshold**: `confidence=0.90` with
    `alignment_confidence_min=0.90` → strict `<` check → `0.90 < 0.90` is False →
    not aborted → skill completes
- `tests/test_station_profiles.py` (37 → 38 tests):
  - **Empty `required_services` with non-empty `available_services`**:
    `missing_services = []` → `if missing_services:` is False → no incompatibility
    from services → `compatible=True`
- `tests/test_marketplace.py` (36 → 37 tests):
  - **`_compat_level` non-dict `compatibility` with no `.level` attr**:
    `getattr(compatibility, "level", "D")` returns default `"D"` (the `else` branch
    of `isinstance(compatibility, dict)` with an object lacking the attribute)
- `tests/test_api.py` (30 → 31 tests):
  - **`/store/install` `available_services` override branch**: non-empty list →
    `if req.available_services:` True → `ctx.available_services` replaced; contrast
    with empty list (branch skipped, default full services retained)

### Test totals by module (622 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 56 |
| `test_api.py` | 31 |
| `test_cli.py` | 43 |
| `test_marketplace.py` | 37 |
| `test_station_profiles.py` | 38 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 215 |
| `test_acceptance.py` | 75 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 57 |

---

## 0.35.0 — validator compat fallback, CLI dual flags, acceptance runner expect branches (615 tests)

### Coverage additions
- `tests/test_validator.py` (55 → 56 tests):
  - **Missing `compatibility` key → `or {}` fallback** (line 228): removed the
    entire `compatibility` section from manifest → `compat = {}` →
    `compat.get('robotClass', []) = []` → `robot_class_mismatch` confirmed
- `tests/test_cli.py` (42 → 43 tests):
  - **`_load_ctx` both `--robot-class` AND `--service` simultaneously**: exercises
    both `if robot_class is not None:` and `if services:` branches in a single
    call; one service provided → many missing → compat errors → exit 1
- `tests/test_acceptance.py` (69 → 71 tests):
  - **Missing `status` key in `expect` dict**: `exp_status = None` →
    `if exp_status and ...` short-circuits → status check skipped →
    `passed = True` regardless of actual status
  - **`status` matches, no `reason` key**: `exp_reason = None` → reason check
    also skipped → `passed = True` even with an arbitrary actual reason

### Test totals by module (615 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 56 |
| `test_api.py` | 30 |
| `test_cli.py` | 43 |
| `test_marketplace.py` | 36 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 215 |
| `test_acceptance.py` | 71 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 57 |

---

## 0.34.0 — cross-module branch coverage: validator fallbacks, marketplace, API, signing, ROS 2 (611 tests)

### Coverage additions
- `tests/test_validator.py` (52 → 55 tests):
  - **Missing `metadata` key** → `(manifest.get('metadata') or {})` returns `{}`; `meta = {}`
    and `name_matches_skill_id` fails — exercises the `or {}` fallback on line 181
  - **Missing `profiles` key in `chs_profiles.json`** → `profiles.get('profiles')` returns None →
    `or []` → `profile_names = []`; `default_chs_profile_exists` fails — exercises line 186
  - **Missing `constraints` key** → `(manifest.get('constraints') or {}).get('payloadKgMax')` →
    None → `payload_within_constraints = True`; no spurious error — exercises line 215
- `tests/test_marketplace.py` (35 → 36 tests):
  - **`licensing_policy.json` missing** → `SkillStore.__init__` `else {}` fallback at line 64;
    verified `store.licensing_policy == {}`
- `tests/test_api.py` (28 → 30 tests):
  - **All three `/store/skills` filters combined** (`family`, `license_model`, `free_only`) in
    one request; returns exactly `etd.pickplace.basic` — exercises the chained filter chain
  - **`sign_package` raises → HTTP 500** — monkeypatched `scripts.sign_package.sign_package`
    with `side_effect=RuntimeError`; verified 500 response with error detail
- `tests/test_signing.py` (56 → 57 tests):
  - **Generic package name → `else` branch in `release_package.py:61`** — `etd.pickplace.basic`
    matches no OEM keyword; `ctx_path = ROOT / 'runtime_context.json'` taken without
    `--runtime-context` flag; `valid=True, Signing SKIPPED` confirmed in output
- `tests/test_ros2_bridge.py` (34 → 35 tests):
  - **`main()` without `--dry-run`** → calls `server.run_ros2()` → `RuntimeError('rclpy not
    available')` raised — exercises the `else` branch at line 168

### Test totals by module (611 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 55 |
| `test_api.py` | 30 |
| `test_cli.py` | 42 |
| `test_marketplace.py` | 36 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 215 |
| `test_acceptance.py` | 69 |
| `test_ros2_bridge.py` | 35 |
| `test_signing.py` | 57 |

---

## 0.33.0 — sim/cli branch coverage: fail_fast break, non-dir skip, missing requiredServices (603 tests)

### Coverage additions
- `tests/test_sim_modules.py` (211 → 215 tests):
  - **`etd_demo_runner.run_all(fail_fast=True)` break**: monkeypatched
    `ETDReferenceValidator` to return level D for every package; called
    `run_all(fail_fast=True)` and asserted only 1 result (early exit via `break`)
  - **`scenario_runner.run_all_scenarios()` non-dir skip**: created `tmp_path/examples/`
    with one real package + one `README.txt` file; monkeypatched `ROOT`;
    asserted only 1 result (the file was skipped via `if not pkg.is_dir(): continue`)
  - **`report_runner.main()` non-dir skip**: same approach — 1 package + README.txt;
    asserted `validation_summary` has exactly 1 entry
- `tests/test_cli.py` (41 → 42 tests):
  - **`_check_station` missing `requiredServices` → `else []`**: created minimal
    `manifest.yaml` + `skill.json` with no `requiredServices` key; verified station
    check ran (not skipped) and produced COMPATIBLE/INCOMPATIBLE output, proving the
    `else []` fallback branch was taken without error

### Test totals by module (603 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 52 |
| `test_api.py` | 28 |
| `test_cli.py` | 42 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 215 |
| `test_acceptance.py` | 69 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |

---

## 0.32.0 — sim/cli branch coverage: _pick_context fallback, report_runner release_out, failure exception, chained filter (599 tests)

### Coverage additions
- `tests/test_sim_modules.py` (205 → 211 tests):
  - **`scenario_runner._pick_context`**: `p.exists()` False branch — keyword matches but
    context file is absent, so function falls through to `runtime_context.json` default
    (monkeypatched `_CTX_MAP` to use a non-existent file name)
  - **`etd_demo_runner._pick_context`**: same `p.exists()` False / default fallback branch
  - **`failure_scenarios.scenario_human_in_forbidden_zone`**: `except Exception as exc` branch —
    fake `chs_adapter.py` in `tmp_path` whose `run()` raises `RuntimeError`; monkeypatched
    `ROOT`; verified `passed=False`, `status='error'`, `reason` contains the error message
  - **`report_runner.main()`** — `release_out` exists: created `tmp_path/release_out/` with
    one `.zip` file; monkeypatched `ROOT`; verified zip name appears in `release_summary` output
  - **`report_runner.main()`** — OEM context files missing: only `runtime_context.json` present;
    all four `else base_ctx` fallbacks exercised; output still contains 8-entry `validation_summary`
- `tests/test_cli.py` (40 → 41 tests):
  - **`list_skills` chained `--family` + `--free` filter**: `--family inspect --free` returns
    empty (inspect skill is subscription); `--family transport --free` returns mobed_transport
    (both criteria satisfied) — exercises the sequential filter chain at lines 185–188 of `etd_cli.py`

### Test totals by module (599 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 52 |
| `test_api.py` | 28 |
| `test_cli.py` | 41 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 211 |
| `test_acceptance.py` | 69 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |

---

## 0.31.0 — adapter branch coverage: assembly/inspect/atlas + extended _AdapterMW (593 tests)

### Coverage additions
- `tests/test_acceptance.py` (60 → 69 tests):
  - Extended `_AdapterMW` with `part_alignment`, `balance_state`, `scene_map`,
    `object_pose` per-topic overrides (in addition to existing joint_state/intent/fatigue/seam_tracker)
  - **Assembly precision** (`etd.assembly.precision`):
    - `vision_align` aborts when `alignment_confidence_below_threshold` (confidence 0.5 < 0.90)
    - `vision_align` aborts when `alignment_offset_too_large` (offset 5.0mm > precision_mm×3=1.5mm)
    - `seat_verify` aborts when `insufficient_seating_force` (force 5.0N < seat_force×0.8=12.0N)
  - **Inspect vision** (`etd.inspect.vision`):
    - `classify_result` aborts when `low_classification_confidence` — monkeypatched
      `random.uniform` to minimum so `0.93−0.04=0.89 < 0.92`
    - `_classify_defects` with `random.random()=0.0 < 0.08` injects a defect → `pass_qc=False`
      in completed result (exercises the defects branch in `QCResult`)
  - **Atlas humanoid** (`etd.atlas.humanoid_walkfetch`):
    - Balance gate at every primitive: `stable=False` → `balance_loss_detected` at first primitive
    - `localize_target`: `map_ready=False` in scene map → `localization_failure`
    - `approach_object`: `object_pose.confidence=0.5 < 0.85` → `grasp_confidence_low`
    - `deposit_or_handover` with `human_handover` profile: `humanReadyTimeoutSec=-1`
      (monkeypatched via `_PROFILE_DEFAULTS`) → `handover_timeout` abort

### Test totals by module (593 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 52 |
| `test_api.py` | 28 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 205 |
| `test_acceptance.py` | 69 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |
| **Total** | **593** |

---

## 0.30.0 — OEM adapter safety-critical branch coverage: exo/cobot/wia/mobed (584 tests)

### Coverage additions
- `tests/test_acceptance.py` (50 → 60 tests) — new `_AdapterMW` helper subclassing
  `AcceptanceMiddleware` with per-topic overrides and a safety-read countdown:
  - **Vest exoskeleton** (`etd.hyundai.vest_exoskeleton`):
    - `operator_panic_release=True` → aborts with `reason='operator_panic_release'` (vs. `human_in_forbidden_zone`)
    - `calibrated=False` in joint state → aborts with `reason='calibration_failed'`
    - Intent confidence 0.5 below profile minimum 0.82 → `intent_confidence_below_threshold`
    - `fatigue_pct=90 >= threshold 70` → `adapt_gain` branch lowers `final_gain` to 0.8
  - **Cobot safeassist** (`etd.cobot.safeassist`):
    - `humanReadyTimeoutSec=-1` (deadline already past) → `human_ready_timeout` abort
    - Forbidden zone injected on 4th safety read (inside `wait_human_ready` while-loop) → inner abort
  - **WIA welding** (`etd.hyundai.wia_welding`):
    - Seam tracker confidence 0.5 < minimum 0.90 → `seam_track_confidence_low` abort at `torch_align`
    - `tack_weld` profile (travel_speed=0, post_inspection=False) → `welding.seam_progress`
      and `inspection.result` events absent from telemetry
    - Arc active at `ignite_arc`, then human abort at `weld_traverse` → `welding.arc_stopped`
      emitted before `skill.aborted` (covers `if arc_active:` branch, lines 119-120)
  - **MobED transport** (`etd.hyundai.mobed_transport`):
    - Human forbidden zone on 2nd safety read (inside `_navigate_segment` loop) →
      abort returned from helper function with `at_primitive='navigate_to_pickup'`

### Test totals by module (584 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 52 |
| `test_api.py` | 28 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 205 |
| `test_acceptance.py` | 60 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |
| **Total** | **584** |

---

## 0.29.0 — acceptance runner legacy inject, chsProfile injection, pickplace adapter branches (574 tests)

### Coverage additions
- `tests/test_acceptance.py` (46 → 50 tests):
  - `_run_test()` legacy inject format: `inject` dict without `at_primitive` key applies
    `safety_state` globally as `initial_safety` — pickplace aborts on first primitive
  - `_run_test()` `chsProfile` auto-injection: `input.job_context` without `chsProfile`
    gets the `profile` field inserted before calling the adapter
  - `etd.pickplace.basic` adapter `fragility='high'` branch: forces `speed_factor=0.5`,
    `body_mode='micro_stable'`, `arm_mode='slow_arc'`, `wrist_mode='minimal_force'`
  - `etd.pickplace.basic` adapter unknown `chsProfile` fallback: unknown profile name
    resolves to `small_box` defaults (`payloadKg=1.5`)

### Test totals by module (574 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 52 |
| `test_api.py` | 28 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 205 |
| `test_acceptance.py` | 50 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |
| **Total** | **574** |

---

## 0.28.0 — validator _JSONSCHEMA_AVAILABLE=False and engine-exception branches (570 tests)

### Coverage additions
- `tests/test_validator.py` (47 → 52 tests):
  - `_jsonschema_validate()` returns `[]` when `_JSONSCHEMA_AVAILABLE` is monkeypatched False
  - `validate_package()` adds `'jsonschema not installed'` warning when unavailable
  - `validate_package()` uses `isinstance(doc, dict)` fallback for schema results when unavailable
  - `_jsonschema_validate()` `except Exception` handler: passing `schema=None` forces
    `AttributeError` in `Draft202012Validator`, caught and returned as `'schema engine error'`
  - `_load()` `.yml` extension branch via `tmp_path / 'config.yml'`

### Test totals by module (570 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 52 |
| `test_api.py` | 28 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 205 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |
| **Total** | **570** |

---

## 0.27.0 — __main__ blocks and API station+nonexistent-skill branch (565 tests)

### Coverage additions
- `tests/test_sim_modules.py` (204 → 205 tests):
  - `sim/event_replay.py` `__main__` block via `runpy.run_path` — verifies JSON output
    with `skill_id`, `envelopes`, `first='skill.started'`, `last='skill.completed'`
- `tests/test_marketplace.py` (33 → 35 tests):
  - `marketplace/skill_store.py` `__main__` block via `runpy.run_path` — verifies 8
    install decision JSON objects printed, each with `skillId` and `allowed` fields
- `tests/test_api.py` (27 → 28 tests):
  - `POST /store/install` with valid `station_id` + unknown `skill_id` — exercises the
    `if entry:` branch inside the station check loop; confirms `station_compatible` absent
    from response when skill entry is not found

### Test totals by module (565 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 47 |
| `test_api.py` | 28 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 35 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 205 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |
| **Total** | **565** |

---

## 0.26.0 — generate/sign/verify script main() functions (561 tests)

### Coverage additions
- `tests/test_signing.py` (47 → 56 tests):
  - `generate_keypair.main()` — creates key files, prints paths, uses default `keys/` dir
  - `sign_package.main()` — creates `package.sig`, prints "Signed:" message
  - `verify_signature.main()` — exits 0 on valid signature, exits 1 on unsigned package,
    exits 0 with explicit `--pub-key` flag, prints "OK" on success

### Test totals by module (561 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 47 |
| `test_api.py` | 27 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 33 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 204 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 56 |
| **Total** | **561** |

---

## 0.25.0 — visualizer.main(), ascii_timeline edges, _plot_gantt ImportError (552 tests)

### Coverage additions
- `tests/test_sim_modules.py` (194 → 204 tests):
  - `visualizer.main()` with no args — all 8 skills, ASCII timeline output verified
  - `visualizer.main(--skill ...)` — single skill mode, other skills absent from output
  - `visualizer.main(--skill ... --profile ...)` — custom profile in output
  - `visualizer.main()` error branch — nonexistent skill prints `ERROR:` and continues
  - `ascii_timeline()` with empty `trace.primitives` — no crash, header still present
  - `ascii_timeline()` with result dict missing all summary keys — no `Result:` line
  - `ascii_timeline()` with empty result dict — no `Result:` line
  - `ascii_timeline()` with primitive `status='running'` — `'…'` icon in output
  - `ascii_timeline()` with unknown primitive status — `'?'` fallback icon in output
  - `_plot_gantt()` `ImportError` branch — matplotlib mocked absent, prints install hint

### Test totals by module (552 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 47 |
| `test_api.py` | 27 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 33 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 204 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 47 |
| **Total** | **552** |

---

## 0.24.0 — ROS2 main() dry-run, validation_failed reason, package __init__ exports (542 tests)

### Coverage additions
- `tests/test_ros2_bridge.py` (30 → 34 tests):
  - `ETDSkillActionServer.main(--dry-run)` — prints "Dry run" message and JSON result
  - `ETDSkillActionClient.main(--dry-run)` — exits 0, prints ETD Client output
- `tests/test_marketplace.py` (30 → 33 tests):
  - `validate_for_install()` with level D → `reason='validation_failed'` explicitly asserted
  - `adapters/__init__` exports: `to_enterprise_event`, `check_skill_compatible`,
    `load_station_profile`, `OrbitEventBridge` all importable
  - `sim/__init__` exports: `replay`, `nominal_lifecycle`, `FakeMiddleware`,
    `run_all_scenarios` all importable
- `tests/test_cli.py` (38 → 40 tests):
  - `install` with nonexistent skill + `--station-profile` → `_check_station_entry(None)`
    returns early, no COMPATIBLE/INCOMPATIBLE output
  - `install` nonexistent skill → exits 1 with `skill_not_found` or BLOCKED in output

### Test totals by module (542 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 47 |
| `test_api.py` | 27 |
| `test_cli.py` | 40 |
| `test_marketplace.py` | 33 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 194 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 34 |
| `test_signing.py` | 47 |
| **Total** | **542** |

---

## 0.23.0 — stations CLI, install blocked+station skip, FakeMiddleware edges, sim demos (533 tests)

### Coverage additions
- `tests/test_cli.py` (33 → 38 tests):
  - `stations` table output — station IDs and count present
  - `stations --json` — list of ≥6 profiles with expected IDs
  - `install --station-profile` when entitlement blocked → station check skipped (no COMPATIBLE)
  - `install --station-profile` when station incompatible → INCOMPATIBLE shown
  - `validate --station-profile` on empty package → "Station check skipped" or non-zero exit
- `tests/test_sim_modules.py` (196 → 194 — corrected count; net new tests):
  - `FakeMiddleware.get_status()` with unknown ID → None
  - `FakeMiddleware.latency_ms` forwarded in accepted response
  - `FakeMiddleware.complete()` with default args → `result='success'`, `result_data={}`
  - `sim/run_sim_demo.main()` → exits 0
  - `sim/run_assembly_demo.main()` → exits 0
- `tests/test_ros2_bridge.py` count corrected to 30 (was 27 in prior changelog)

### Test totals by module (533 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 47 |
| `test_api.py` | 27 |
| `test_cli.py` | 38 |
| `test_marketplace.py` | 30 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 194 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 30 |
| `test_signing.py` | 47 |
| **Total** | **533** |

---

## 0.22.0 — validator main(), marketplace_demo main(), report_runner main(), orbit severities (523 tests)

### Coverage additions
- `tests/test_validator.py` (43 → 47 tests):
  - `etd_reference_validator.main()` pretty mode — prints `ETD validation: PASS`, exits 0
  - `etd_reference_validator.main(--output json)` — valid JSON with `valid=True`
  - `etd_reference_validator.main()` with missing runtime context → falls back to empty
    `RuntimeContext`, still prints `ETD validation:` output
  - `etd_reference_validator.main()` on a broken package → exits non-zero, prints `FAIL`
- `tests/test_sim_modules.py` (183 → 196 tests):
  - `sim/marketplace_demo.main()` — returns normally when all installs allowed; JSON output
    has `marketplace_demo` key with 8 decisions; all `allowed=True`
  - `sim/report_runner.main()` — exits 0 on success; JSON summary has `overall_pass=True`
    and 8-entry `validation_summary`; writes `reports/report_summary.json` and `.md`
- `tests/test_orbit_bridge.py` (30 → 37 tests):
  - Severity mappings for `primitive.exited` (debug), `telemetry.heartbeat` (debug),
    `telemetry.metrics` (info), `safety.warning` (warn)
  - `primitive.exited` and `telemetry.heartbeat` filtered at `min_severity='info'`
  - `telemetry.metrics` passes at `min_severity='info'`

### Test totals by module (523 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 47 |
| `test_api.py` | 27 |
| `test_cli.py` | 33 |
| `test_marketplace.py` | 31 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 37 |
| `test_sim_modules.py` | 196 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 27 |
| `test_signing.py` | 47 |
| **Total** | **523** |

---

## 0.21.0 — AcceptanceMiddleware, _run_test edges, acceptance main(), release_package main() (506 tests)

### Coverage additions
- `tests/test_acceptance.py` (8 → 46 tests):
  - `AcceptanceMiddleware.read()` — all 17 topics: safety_state, force_contact_feedback,
    part_alignment, camera_frame (counter increments), scene_map, balance_state,
    object_pose, seam_tracker, weld_inspection, obstacle_detector, path_planner,
    lift_control, intent_detector, exo_joint_state, fatigue_monitor, imu_pose, unknown → None
  - `AcceptanceMiddleware.publish()` — non-telemetry no-op; primitive.entered records;
    inject_at with `safety_state`, `perception_override`, `force_override` all apply correctly
  - `AcceptanceMiddleware` — `initial_safety` overrides defaults at construction
  - `_run_test()` — status mismatch, reason mismatch, result_keys check (missing key),
    result_keys check (key present → pass), exception path → status='error'
  - `run_suite()` — no acceptance_tests.yaml → empty SuiteResult, success=True
  - `_print_suite()` — verbose shows status=, failure shows FAIL message and ✗ icon
  - `main(--skill)` — single skill output; `main(--json)` — valid JSON with suite data;
    `main(--verbose)` — shows status= in verbose output
- `tests/test_signing.py` (41 → 47 tests):
  - `release_package.main(--skip-sign)` — valid=True, Signing SKIPPED, zip created
  - `release_package.main(--key missing)` — key not found message, zip still created
  - Auto-detected context for atlas, wia, mobed, exo packages via keyword dispatch
  - JSON summary in output has skillId, signed=False, validationLevel, artifact fields

### Test totals by module (506 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 43 |
| `test_api.py` | 27 |
| `test_cli.py` | 33 |
| `test_marketplace.py` | 31 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 183 |
| `test_acceptance.py` | 46 |
| `test_ros2_bridge.py` | 27 |
| `test_signing.py` | 47 |
| **Total** | **506** |

---

## 0.20.0 — failure_scenarios main(), demo_runner main(), validate_examples main() (461 tests)

### Coverage additions
- `tests/test_sim_modules.py` (179 → 183 tests):
  - `sim/failure_scenarios.main()` pretty-print mode — output contains all 4 scenario
    names and `4/4` summary line
  - `sim/failure_scenarios.main(--json)` — valid JSON list of 4 results, all `passed=True`
  - Detailed result dict fields for each scenario: `detail` string content,
    `block_reason` payload limit, `reason` contains `not_allowed`
  - `etd_demo_runner.main()` pretty-print — output contains package names and `8/8`
  - `etd_demo_runner.main(--json)` — valid JSON list of 8 entries with `package` key
  - `etd_demo_runner.main(--fail-fast)` — exits 0 when all packages pass
  - `sim/scenario_runner.main()` — exits 0, output contains `etd.` skill IDs
  - `validate_examples.main()` — no SystemExit, output contains `valid=True`

### Test totals by module (461 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 43 |
| `test_api.py` | 27 |
| `test_cli.py` | 33 |
| `test_marketplace.py` | 31 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 183 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 27 |
| `test_signing.py` | 41 |
| **Total** | **461** |

---

## 0.19.0 — Generator fallback, scenario_runner dispatch, replay edges, level-B install (448 tests)

### Coverage additions
- `tests/test_sim_modules.py` (156 → 179 tests):
  - `scenario_runner._pick_context()` — all 8 keyword branches (atlas, humanoid, wia,
    mobed, amr, vest, exo, default fallback to runtime_context.json) tested directly
  - `RobotStateGenerator._table()` fallback — unknown skill family returns `_PICKPLACE`
    table; `at('approach')` on unknown-family skill returns correct arm state
  - `replay()` dict event without `skill_id` key → `setdefault` fills in the provided
    default; mixed string+dict event list with own skill_id overriding the default;
    dict event with `data` forwarded; dict event with `timestamp_ms` forwarded
  - `nominal_lifecycle()` with empty primitives → `[skill.started, skill.completed]`
  - `aborted_lifecycle()` with empty primitives → `[skill.started, skill.aborted]`
- `tests/test_marketplace.py` (28 → 31 tests):
  - `validate_for_install()` at level B (missing optional services) → `allowed=True`,
    `reason='install_allowed'`, `validationLevel='B'`
  - `validate_listing()` at level B → `installAllowed=True`
- `tests/test_signing.py` (38 → 41 tests):
  - `_package_digest()` when a signed file is missing → does not raise; digest still
    32 bytes; differs from full-package digest
  - `sign_package()` + `verify_package()` round-trip on a package with a deleted file
    → signature still validates correctly for remaining files

### Test totals by module (448 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 43 |
| `test_api.py` | 27 |
| `test_cli.py` | 33 |
| `test_marketplace.py` | 31 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 179 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 27 |
| `test_signing.py` | 41 |

---

## 0.18.0 — FakeMiddleware edge cases, ROS2 bridge no-middleware paths (428 tests)

### Coverage additions
- `tests/test_sim_modules.py` (148 → 156 tests):
  - `FakeMiddleware.complete()` with nonexistent id → False
  - `FakeMiddleware.cancel()` on already-cancelled execution → False (idempotent guard)
  - `FakeMiddleware(fail_rate=1.0).send_request()` → `simulated_fault` rejection
  - `FakeMiddleware(fail_rate=0.0)` always accepts (zero guard)
  - `send_request` with explicit `station_id` in request (overrides instance station)
  - `send_request` with unknown station in request payload
- `tests/test_ros2_bridge.py` (19 → 27 tests):
  - `execute_goal(middleware=None)` — `_FeedbackMiddleware.inner=None` path: publish does
    nothing, read returns None; skill still completes (read returns None gracefully)
  - `execute_goal(middleware=None, feedback_fn=some_fn)` — callbacks still fire for
    `telemetry.events` even when inner middleware absent
  - `execute_goal(feedback_fn=None, middleware=None)` — both None, completes cleanly
  - All-8 packages parametrized via `server.execute_goal(goal, middleware=_MW)` —
    verifies every skill reaches `status=completed` with a full `_NominalMiddleware`

### Test totals by module (428 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 43 |
| `test_api.py` | 27 |
| `test_cli.py` | 33 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 156 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 27 |
| `test_signing.py` | 38 |

---

## 0.17.0 — Validator semantic failures, CLI branches, full suite (411 tests)

### Coverage additions
- `tests/test_validator.py` (29 → 43 tests):
  - Missing required files: `capabilities.json` deleted → error + `required_files_present=False`
  - `tests/acceptance_tests.yaml` deleted → `required_files_present=False`
  - Semantic check failures: `name_matches_skill_id`, `version_matches_skill_version`,
    `profile_uniqueness` (duplicate profile), `default_chs_profile_exists`,
    `telemetry_has_lifecycle_event` (no lifecycle events in either manifest or events.json),
    `primitive_order_nonempty` (empty list), `force_windows_valid` (max < min),
    `payload_within_constraints` (999 kg >> 8 kg limit),
    `capability_safe` (forbidden cap in write list),
    `capability_safe` (missing `command.skill_intent`)
  - `_load_schema()` returning None via monkeypatched `_SCHEMA_MAP` → warning printed
  - Compat score degrades with multiple simultaneous errors (runtime_too_old +
    robot_class_mismatch + all services missing)
- `tests/test_cli.py` (26 → 33 tests):
  - `_load_ctx()` falls back to `default_runtime_context()` when context file missing
  - `--robot-class exoskeleton` override → wrong class → FAIL (level D)
  - `_print_report()` pretty-print shows `✗` errors when required file deleted
  - `_print_report()` shows "All checks passed" when report is valid
  - `validate` + `--station-profile` + `--json` → two JSON blocks, `station_check` present
  - `validate` + incompatible `--station-profile` + `--json` → "compatible" in output
  - `install` + `--station-profile` when allowed → `_check_station_entry` called, COMPATIBLE shown
  - `list --family transport` → single MobED entry in table

### Test totals by module (411 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 43 |
| `test_api.py` | 27 |
| `test_cli.py` | 33 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 148 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 38 |

---

## 0.16.0 — Demo runner, marketplace_demo, report_runner, and API coverage (389 tests)

### Coverage additions
- `tests/test_sim_modules.py` (111 → 148 tests):
  - `etd_demo_runner._pick_context()` — all 10 keyword branches (atlas, humanoid,
    wia, welding, mobed, transport, amr, vest, exoskeleton, exo) plus default fallback
  - `etd_demo_runner._level_ok()` — True for A/B, False for C/D
  - `etd_demo_runner.run_all()` — all 8 packages return level A; result dict keys;
    `fail_fast=True` still completes when all pass
  - `etd_demo_runner._print_table()` — PASS line, FAIL line with compat_errors/
    errors/warnings, summary `X/Y` line
  - `marketplace_demo._pick_context()` — humanoid, atlas, welding, transport, assist,
    default fallback to `default_runtime_context()`
  - `report_runner._pick_context()` — atlas, humanoid, wia_welding, wia_weld, mobed,
    transport, vest, exoskeleton, base fallback (reuses `_load_contexts` from validate_examples)
- `tests/test_api.py` (21 → 27 tests):
  - `POST /validate` with an absolute package path (exercises the `not is_absolute()` branch)
  - `POST /validate` for `etd.hyundai.wia_welding` with WIA runtime context → level A
  - `GET /store/skills?family=does_not_exist` → count 0, empty list
  - `GET /store/skills?family=welding` → single WIA welding entry
  - `GET /store/skills?family=assist` → single vest exoskeleton entry
  - `POST /store/install` for MobED with `station_id=mobed_logistics_a` → station_compatible,
    station_warnings, station_missing_services all present

### Test totals by module (389 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 29 |
| `test_api.py` | 27 |
| `test_cli.py` | 26 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 148 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 38 |

---

## 0.15.0 — Visualizer, TracingMiddleware, and station profile edge cases (346 tests)

### Coverage additions
- `tests/test_sim_modules.py` (80 → 111 tests):
  - `PrimitiveTrace.duration` — normal and negative-clamped cases
  - `SkillTrace.total_duration` — normal and negative-clamped cases
  - `_bar()` — full, empty, half, overflow, underflow
  - `ascii_timeline()` — skill_id present, primitive name, ✓/✗ status icons,
    result summary keys, multiple traces
  - `TracingMiddleware.publish()` — non-telemetry ignored, telemetry recorded,
    `primitive.entered` creates PrimitiveTrace, `primitive.exited` sets end+status,
    `skill.aborted`/`skill.failed` closes current primitive with correct status
  - `TracingMiddleware.read()` — all 16 topic branches including Atlas, WIA, MobED,
    exoskeleton, and unknown-topic → None
  - `run_traced()` — full round-trip for `etd.pickplace.basic` and
    `etd.hyundai.wia_welding`; verifies status, primitives, total_duration, result dict
- `tests/test_station_profiles.py` (33 → 37 tests):
  - `StationProfile.from_dict()` with optional `notes` and `platform` fields
  - `StationProfile.from_dict()` without optional fields → None defaults
  - `StationProfile.to_dict()` includes `platform` and `notes`
  - `check_skill_compatible()` when `profile.available_services` is empty →
    service check skipped, `compatible=True` even with unmet required services

### Test totals by module (346 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 29 |
| `test_api.py` | 21 |
| `test_cli.py` | 26 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 37 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 111 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 38 |

---

## 0.14.0 — _run_test branches, _print_suite, and verify_signature coverage (301 tests)

### Coverage additions
- `tests/test_sim_modules.py` (67 → 80 tests):
  - `_run_test()` failure branches: status mismatch, reason mismatch, missing
    result_key, result_key present (all four paths in the expect-checking logic)
  - `run_suite()` with no `acceptance_tests.yaml` → empty SuiteResult, `suite='(no tests)'`
  - `_print_suite()`: all-passing (shows ✓, no FAIL), with failure (shows ✗, FAIL message),
    verbose mode (shows `status=` and `reason=` for passing tests)
- `tests/test_signing.py` (37 → 38 tests):
  - `test_verify_sig_doc_missing_verify_key_returns_false` — `verify_key` stripped
    from sig doc and no matching key file → `if not verify_hex:` branch returns False

### Test totals by module (301 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 29 |
| `test_api.py` | 21 |
| `test_cli.py` | 26 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 80 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 38 |

---

## 0.13.0 — Acceptance runner, orbit bridge, and validate_examples coverage (292 tests)

### Coverage additions
- `tests/test_orbit_bridge.py` (28 → 30 tests):
  - `test_bridge_safety_warning_bypasses_filter` — `safety.warning` is in
    `_CRITICAL_EVENTS`; passes `min_severity='error'` filter regardless
  - `test_bridge_ingest_with_explicit_timestamp` — `timestamp_ms` forwarded through ingest
- `tests/test_sim_modules.py` (52 → 67 tests):
  - `AcceptanceMiddleware.publish()`: records telemetry events, ignores non-telemetry,
    tracks `primitives_entered`, applies `inject_at` state patch, `initial_safety` override
  - `SuiteResult.success` property: True when `failed==0`, False otherwise
  - `_run_test()` exception path: adapter raising `RuntimeError` → `status='error'`,
    `passed=False`, `failure_message` contains `'Exception'`
  - `validate_examples._load_contexts()`: returns all 5 context keys
  - `validate_examples._pick_context()`: all 5 branches (atlas, wia, mobed, exo, base)

### Test totals by module (292 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 29 |
| `test_api.py` | 21 |
| `test_cli.py` | 26 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 30 |
| `test_sim_modules.py` | 67 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 37 |

---

## 0.12.0 — API sign endpoint and CLI command coverage (276 tests)

### Coverage additions
- `tests/test_api.py` (18 → 21 tests):
  - `POST /store/sign` endpoint (previously untested):
    - `test_sign_package_not_found` → 404 when package path absent
    - `test_sign_key_not_found` → 400 when key file absent
    - `test_sign_valid_package` → 200 with `signed=True`; package.sig written
- `tests/test_cli.py` (20 → 26 tests):
  - `keygen` command: `test_keygen_creates_key_files` — both hex key files created
  - `verify` command:
    - `test_verify_signed_package_succeeds` — sign then verify → exit 0
    - `test_verify_unsigned_package_fails` — unsigned package → exit 1
  - `publish` command: `test_publish_skip_sign` — `--skip-sign` → zip artifact created
  - `validate --json` failure: `test_validate_json_output_failure` — missing services
    → exit 1, JSON output with `valid=false`, `level=D`

### Test totals by module (276 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 29 |
| `test_api.py` | 21 |
| `test_cli.py` | 26 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 52 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 37 |

---

## 0.11.0 — Validator edge case coverage (268 tests)

### Coverage additions in `tests/test_validator.py` (17 → 29 tests)
- `load_runtime_context()` for remaining contexts: `test_load_wia_runtime_context`,
  `test_load_mobed_runtime_context`, `test_load_exo_runtime_context`
- Compatibility level B: `test_compat_level_b_optional_services_missing` — all
  required services present but optional services absent → level B, valid=True
- Compatibility errors:
  - `test_compat_runtime_too_old` — `runtime_version='0.0.1'` below `>=0.1.0`
  - `test_compat_robot_class_mismatch` — unsupported robot_class → level D
- Parse error path: `test_parse_error_returns_invalid_report` — malformed YAML
  → `valid=False`, `'parse error'` in errors (lines 144-150)
- Helper functions `_version_tuple` and `_min_runtime`:
  - `test_version_tuple_normal`, `test_version_tuple_malformed_returns_zero` (exception branch)
  - `test_min_runtime_none_returns_none`, `test_min_runtime_empty_returns_none`,
    `test_min_runtime_with_spec`

### Test totals by module (268 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 29 |
| `test_api.py` | 18 |
| `test_cli.py` | 20 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 52 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 37 |

---

## 0.10.0 — Sim, client, and release pipeline coverage (256 tests)

### Coverage additions
- `tests/test_sim_modules.py` (42 → 52 tests):
  - `RobotStateGenerator` humanoid family: `test_generator_humanoid_family`,
    `test_generator_humanoid_reach_and_grasp`
  - Noise mode: `test_generator_noise_mode_returns_valid_structure`
  - `scenario_runner.print_results()`: `test_print_results_no_compat_errors`,
    `test_print_results_with_compat_errors`, `test_print_results_mixed_pass_fail`
    (including compat_errors display branch and pass/fail ratio line)
- `tests/test_ros2_bridge.py` (15 → 19 tests):
  - `ETDSkillActionClient.send_goal(dry_run=True)`: `test_client_dry_run_completes`,
    `test_client_dry_run_feedback_printed`
  - `ETDSkillActionClient._ros2_execute()` ImportError: `test_client_ros2_raises_without_rclpy`
  - `ETDSkillActionServer.run_ros2()` ImportError: `test_server_run_ros2_raises_without_rclpy`
- `tests/test_signing.py` (34 → 37 tests):
  - `release_package._zip_dir()`: `test_zip_dir_creates_zip_file`,
    `test_zip_dir_contains_expected_files`, `test_zip_dir_excludes_pycache`

### Test totals by module (256 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 17 |
| `test_api.py` | 18 |
| `test_cli.py` | 20 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 52 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 19 |
| `test_signing.py` | 37 |

---

## 0.9.0 — SkillStore coverage completions (243 tests)

### Coverage additions in `tests/test_marketplace.py` (17 → 28 tests)
- `StoreEntry.from_dict()` compatibility shims:
  - `test_store_entry_compat_requires_activation` — `requiresActivation` → `requiresEntitlement`
  - `test_store_entry_compat_source_available_false/true` — `sourceAvailable` → `sourceAvailability`
  - `test_store_entry_explicit_fields_take_precedence_over_compat`
- `get_entry()` missing-skill path: `test_get_entry_not_found`
- `validate_listing()` edge cases:
  - `test_validate_listing_skill_not_found` — unknown skill → `installAllowed: False`
  - `test_validate_listing_commercial_uses_demo_token` — auto-injects demo token for entitlement-gated skills
  - `test_validate_listing_free_skill_install_allowed` — all fields present
- `_compat_level()` non-dict branch: `test_compat_level_non_dict_compatibility`, `test_compat_level_missing_attribute_returns_d`
- `InstallDecision` fields: `test_install_decision_level_a_for_free_skill`

### Test totals by module (243 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 17 |
| `test_api.py` | 18 |
| `test_cli.py` | 20 |
| `test_marketplace.py` | 28 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 42 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 15 |
| `test_signing.py` | 34 |

---

## 0.8.0 — keypair generator tests (232 tests)

### Coverage additions
- `tests/test_signing.py` extended with 7 `generate_keypair` tests:
  - `test_generate_creates_key_files`: both hex files written to `out_dir`
  - `test_generate_private_key_is_32_bytes_hex`: 32-byte Ed25519 private key
  - `test_generate_public_key_is_32_bytes_hex`: 32-byte Ed25519 public key
  - `test_generate_private_key_permissions`: private key file is `chmod 600`
  - `test_generate_keypair_is_usable_for_signing`: generated key signs + verifies a real package
  - `test_generate_creates_output_dir_if_absent`: nested directory auto-created
  - `test_generate_keys_are_different`: two calls produce distinct keypairs

### Test totals by module (232 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 17 |
| `test_api.py` | 18 |
| `test_cli.py` | 20 |
| `test_marketplace.py` | 17 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 42 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 15 |
| `test_signing.py` | 34 |

---

## 0.7.0 — Signing pipeline tests and OEM adapter coverage (225 tests)

### New test module
- `tests/test_signing.py` (27 tests) — full coverage of the Ed25519 signing pipeline:
  - `sign_package()`: sig file creation, required JSON fields, algorithm/digest
    labels, 64-byte signature, 32-byte public key, signed_files list
  - `verify_package()`: embedded key, explicit public key, missing sig file,
    tampered file detection, wrong public key rejection
  - Sign→verify round-trip parametrized over all 8 skill packages
  - `_package_digest()` determinism and cross-package uniqueness
  - `generic_oem_adapter.to_oem_request()`: nominal request, default station,
    forbidden-command rejection for `servo_torque`, `collision_disable`,
    `emergency_stop_override`, empty payload allowed

### Test totals by module (225 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 17 |
| `test_api.py` | 18 |
| `test_cli.py` | 20 |
| `test_marketplace.py` | 17 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 42 |
| `test_acceptance.py` | 8 |
| `test_ros2_bridge.py` | 15 |
| `test_signing.py` | 27 |

---

## 0.6.0 — Test suite expansion to 198 tests

### New test modules
- `tests/test_acceptance.py` — integrates `sim/acceptance_runner.py` into pytest:
  8 parametrized cases, one per skill package; covers all 39 YAML acceptance
  scenarios; `random.seed(42)` for deterministic `etd.inspect.vision` confidence
- `tests/test_ros2_bridge.py` — 15 tests for `ETDSkillActionServer` without
  a ROS 2 installation: adapter loading, all 8 packages via `execute_goal()` with
  `_NominalMiddleware`, server-busy guard, feedback callback correctness

### Test coverage gaps closed
- `test_validator.py`: added level-A tests for `etd.hyundai.wia_welding`,
  `etd.hyundai.mobed_transport`, `etd.hyundai.vest_exoskeleton`
- `test_marketplace.py`: renamed `test_store_lists_seven_skills` →
  `test_store_lists_eight_skills`; added `test_install_vest_exo_*`,
  `test_install_wia_welding_with_token_allowed`,
  `test_install_mobed_transport_with_token_allowed`
- `test_station_profiles.py`: added `test_load_exo_station_profile`,
  `test_compatible_assist_at_exo_station`, `test_api_get_exo_station`;
  `test_api_list_stations` now asserts `exo_assembly_a` is present
- `test_api.py`: strengthened `test_health` to assert `version == '0.5.0'`;
  added `test_get_vest_exoskeleton_skill`
- `test_cli.py`: added `test_validate_hyundai_packages` (all 4 Hyundai packages
  with correct runtime contexts), `test_info_vest_exoskeleton`,
  `test_install_vest_exo_requires_entitlement`,
  `test_install_vest_exo_with_token`

### Version bumps
- `pyproject.toml`: version `0.1.0` → `0.5.0`
- `api/app.py`: API version `0.2.0` → `0.5.0` (FastAPI metadata + `/health`)
- `sim/visualizer.py`: docstring updated "4 example skills" → "8 skill packages"

### Test totals by module (198 total)
| Module | Tests |
|---|---|
| `test_validator.py` | 17 |
| `test_api.py` | 18 |
| `test_cli.py` | 20 |
| `test_marketplace.py` | 17 |
| `test_station_profiles.py` | 33 |
| `test_orbit_bridge.py` | 28 |
| `test_sim_modules.py` | 42 |
| `test_acceptance.py` | 8 (wraps 39 YAML scenarios) |
| `test_ros2_bridge.py` | 15 |

---

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
