# ETD Robotics Skill Runtime — Prototype v0.70.0

A proof-of-concept **application-layer skill package framework** for industrial robots and humanoids. ETD sits between enterprise/workflow systems and OEM robot middleware — it validates, routes, and manages skill packages without touching certified safety-critical control.

> Inspired by ETD / Kryukov movement-theory principles.

---

## What is ETD?

ETD defines a **skill package format** that any robot manufacturer can adopt. A skill package declares:
- what it needs (services, sensors, station compatibility)
- what it can and cannot do (capability whitelist/blacklist)
- safety constraints it respects (no override of emergency stop, torque limits, etc.)
- execution contract (primitives, force windows, timeouts)
- telemetry events it emits

The validator checks every package before installation. The marketplace manages licensing, entitlement, and signing.

---

## Project structure

```
├── examples/                               # 8 reference skill packages (all level A) + 1 composed
│   ├── etd.pickplace.basic/                # pick-and-place (MIT, free)
│   ├── etd.assembly.precision/             # precision force-controlled insertion
│   ├── etd.inspect.vision/                 # vision QA / defect scan
│   ├── etd.cobot.safeassist/               # human-collaborative handover
│   ├── etd.atlas.humanoid_walkfetch/       # Boston Dynamics Atlas walk-and-fetch
│   ├── etd.hyundai.wia_welding/            # Hyundai WIA H-Motion arc-welding
│   ├── etd.hyundai.mobed_transport/        # Hyundai MobED AMR logistics
│   ├── etd.hyundai.vest_exoskeleton/       # Hyundai VEX/H-MEX wearable assist
│   └── etd.composed.fetch_inspect_place/   # composed: walk-fetch → vision QA → pick-and-place
├── marketplace/                        # skill store: index, policy, license, revocation, rollout, audit
├── adapters/                           # orbit event bridge, station profile loader, OEM adapters
├── sim/                                # simulation, demo runners, visualizer
├── schemas/                            # JSON Schema Draft 2020-12 for all package files
├── station_profiles/                   # 6 station compatibility profiles
├── scripts/                            # release packaging, signing, keypair generation
├── api/                                # FastAPI REST skill store
├── tests/                              # 1798 pytest tests
├── docs/                               # architecture, roadmap, licensing, commercialization
├── integrations/ros2/                  # ROS 2 action server/client bridge (stub)
├── etd_reference_validator.py          # core validator
├── etd_cli.py                          # CLI: validate, install, stations, info, revoke, audit-log, validate-context, rollout, token, versions, review, sandbox-check, feed, dashboard, publisher
├── etd_demo_runner.py                  # validates all 8 packages with correct contexts
├── runtime_context.json                # base runtime context
├── runtime_context_atlas.json          # Boston Dynamics Atlas context
├── runtime_context_wia.json            # Hyundai WIA cobot context
├── runtime_context_mobed.json          # Hyundai MobED AMR context
└── runtime_context_exo.json            # Hyundai VEX exoskeleton context
```

---

## Quick start

```bash
pip install -r requirements.txt

# Validate all 8 packages (all show valid=True, level=A)
python etd_demo_runner.py

# CLI
python etd_cli.py validate examples/etd.pickplace.basic
python etd_cli.py stations
python etd_cli.py install etd.hyundai.wia_welding \
    --station-profile station_profiles/weld_station_a.json
python etd_cli.py revoke etd.bad.skill --reason "critical CVE"
python etd_cli.py audit-log
python etd_cli.py validate-context runtime_context.json
python etd_cli.py rollout set-stage etd.pickplace.basic canary --station workcell-01
python etd_cli.py rollout status
python etd_cli.py token issue etd.hyundai.wia_welding --station workcell-01 --org "Hyundai MFG"
python etd_cli.py token verify <TOKEN> etd.hyundai.wia_welding --station workcell-01
python etd_cli.py versions etd.pickplace.basic
python etd_cli.py versions etd.pickplace.basic --runtime 0.5.0
python etd_cli.py review examples/etd.hyundai.wia_welding
python etd_cli.py review examples/etd.hyundai.wia_welding --json
python etd_cli.py sandbox-check examples/etd.hyundai.wia_welding
python etd_cli.py sandbox-check examples/etd.hyundai.wia_welding --json
python etd_cli.py feed create --id my-feed --name "My Feed" --out my-feed.feed.json
python etd_cli.py feed verify my-feed.feed.json
python etd_cli.py feed import my-feed.feed.json --json
python etd_cli.py dashboard
python etd_cli.py dashboard --json
python etd_cli.py dashboard --watch 5 --interval 3
python etd_cli.py publisher submit examples/etd.pickplace.basic
python etd_cli.py publisher submit examples/etd.hyundai.wia_welding --json
python etd_cli.py publisher list
python etd_cli.py publisher approve <SUBMISSION_ID>
python etd_cli.py publisher reject <SUBMISSION_ID> --reason "safety issue"
python etd_cli.py compose validate examples/etd.composed.fetch_inspect_place
python etd_cli.py compose validate examples/etd.composed.fetch_inspect_place --json
python etd_cli.py compose run examples/etd.composed.fetch_inspect_place
python etd_cli.py compose run examples/etd.composed.fetch_inspect_place --json
python etd_cli.py platform list
python etd_cli.py platform list --json
python etd_cli.py platform check examples/etd.atlas.humanoid_walkfetch --source atlas --target unitree_g1
python etd_cli.py platform check examples/etd.atlas.humanoid_walkfetch --source atlas --target unitree_h1
python etd_cli.py platform matrix
python etd_cli.py platform matrix --skill examples/etd.atlas.humanoid_walkfetch --json
python etd_cli.py platform matrix --family humanoid
python etd_cli.py onrobot cache list
python etd_cli.py onrobot cache list --json
python etd_cli.py onrobot cache add etd.pickplace.basic --token <TOKEN> --expiry 2027-01-01T00:00:00Z
python etd_cli.py onrobot cache evict
python etd_cli.py onrobot sync status
python etd_cli.py onrobot sync status --json
python etd_cli.py fleet nodes register robot-01 --station workcell-01 --platform atlas
python etd_cli.py fleet nodes list
python etd_cli.py fleet nodes list --json
python etd_cli.py fleet deploy etd.pickplace.basic --nodes robot-01 --version 0.1.0
python etd_cli.py fleet deploy etd.pickplace.basic --json
python etd_cli.py fleet status
python etd_cli.py fleet status --json
python etd_cli.py fleet deployments
python etd_cli.py fleet deployments --skill etd.pickplace.basic --json

# Dependency resolver
python etd_cli.py deps register etd.composed.pipeline --requires etd.pickplace.basic:>=0.1.0 --requires etd.inspect.vision
python etd_cli.py deps order etd.composed.pipeline
python etd_cli.py deps tree etd.composed.pipeline
python etd_cli.py deps check etd.composed.pipeline --available etd.pickplace.basic,etd.inspect.vision
python etd_cli.py deps cycles

# Execution scheduler
python etd_cli.py schedule add etd.pickplace.basic --node robot-01 --interval 30
python etd_cli.py schedule add etd.inspect.vision --node robot-01 --type once --run-at 2026-06-01T08:00:00+00:00
python etd_cli.py schedule list --status active
python etd_cli.py schedule due
python etd_cli.py schedule run <job-id> --success --duration-ms 1200
python etd_cli.py schedule pause <job-id>

# Execution quota & rate limiting
python etd_cli.py quota set etd.pickplace.basic --max-per-hour 60 --max-per-day 500
python etd_cli.py quota set etd.pickplace.basic --node robot-01 --max-per-hour 10
python etd_cli.py quota list
python etd_cli.py quota check etd.pickplace.basic --node robot-01
python etd_cli.py quota usage --skill etd.pickplace.basic

# A/B testing
python etd_cli.py ab create --name "speed trial" --variant etd.pick:0.1.0:0.5:control --variant etd.pick:0.2.0:0.5:treatment
python etd_cli.py ab list --status active
python etd_cli.py ab route <experiment-id>
python etd_cli.py ab results <experiment-id> --json
python etd_cli.py ab recommend <experiment-id>
python etd_cli.py ab conclude <experiment-id> --winner treatment

# Telemetry analytics
python etd_cli.py telemetry record --skill etd.pickplace.basic --node robot-01 --status success --duration-ms 1200
python etd_cli.py telemetry stats etd.pickplace.basic
python etd_cli.py telemetry stats etd.pickplace.basic --json
python etd_cli.py telemetry anomalies --skill etd.pickplace.basic --threshold 2.5
python etd_cli.py telemetry report --json

# REST API
uvicorn api.app:app --reload
# GET  http://localhost:8000/store/skills
# POST http://localhost:8000/store/install  {"skillId": "etd.pickplace.basic"}
# GET  http://localhost:8000/store/stations
# GET  http://localhost:8000/platform/list
# POST http://localhost:8000/platform/check  {"skill_info": {...}, "source": "atlas", "target": "unitree_g1"}
# POST http://localhost:8000/platform/matrix  {"families": ["humanoid"]}
# GET  http://localhost:8000/fleet/nodes
# POST http://localhost:8000/fleet/nodes  {"node_id": "r01", "station_id": "ws-01", "platform_id": "atlas"}
# POST http://localhost:8000/fleet/deployments  {"skill_id": "etd.pickplace.basic", "version": "0.1.0", "target_node_ids": ["r01"]}
# GET  http://localhost:8000/fleet/status
# POST http://localhost:8000/compose/validate  {"composed": {"skillId": "...", "steps": [...]}}
# POST http://localhost:8000/compose/run       {"composed": {"skillId": "...", "steps": [...]}}
# GET  http://localhost:8000/compose/examples
# POST http://localhost:8000/deps/skills  {"skill_id": "etd.pipeline", "deps": [{"skill_id": "etd.pick"}]}
# GET  http://localhost:8000/deps/order/etd.pipeline
# POST http://localhost:8000/deps/check  {"skill_id": "etd.pipeline", "available": ["etd.pick"]}
# GET  http://localhost:8000/deps/cycles
# POST http://localhost:8000/scheduler/jobs  {"skill_id": "etd.pick", "node_id": "r01", "interval_minutes": 30}
# GET  http://localhost:8000/scheduler/due
# POST http://localhost:8000/scheduler/jobs/{id}/run  {"success": true, "duration_ms": 1200}
# POST http://localhost:8000/quota/policies  {"skill_id": "etd.pickplace.basic", "max_per_hour": 60}
# POST http://localhost:8000/quota/check     {"skill_id": "etd.pickplace.basic", "node_id": "r01"}
# GET  http://localhost:8000/quota/usage?skill_id=etd.pickplace.basic
# POST http://localhost:8000/ab/experiments  {"name": "speed trial", "variants": [...]}
# GET  http://localhost:8000/ab/experiments?status=active
# GET  http://localhost:8000/ab/experiments/{id}/route
# GET  http://localhost:8000/ab/experiments/{id}/results
# GET  http://localhost:8000/ab/experiments/{id}/recommend
# POST http://localhost:8000/ab/experiments/{id}/conclude  {"winner_label": "treatment"}
# POST http://localhost:8000/telemetry/executions  {"skill_id": "etd.pickplace.basic", "node_id": "r01", "status": "success", "total_duration_ms": 1200}
# GET  http://localhost:8000/telemetry/stats/etd.pickplace.basic
# GET  http://localhost:8000/telemetry/report
# GET  http://localhost:8000/telemetry/anomalies?z_threshold=2.5

# Acceptance tests (39 scenarios, all 8 packages)
python sim/acceptance_runner.py
python sim/acceptance_runner.py --skill etd.hyundai.vest_exoskeleton --verbose

# Visualizer — ASCII timeline for all 8 skills
python sim/visualizer.py

# Sim modules
python sim/scenario_runner.py
python sim/failure_scenarios.py
python sim/marketplace_demo.py

# Report
python sim/report_runner.py

# Release a package (validate → sign → zip)
python scripts/release_package.py examples/etd.hyundai.wia_welding
```

---

## Skill packages

| Package | Family | Primitives | Platform | License |
|---|---|---|---|---|
| `etd.pickplace.basic` | manipulator | 5 | generic | MIT / free |
| `etd.assembly.precision` | assembly | 6 | generic | commercial, per-site |
| `etd.inspect.vision` | inspection | 5 | generic | commercial, subscription |
| `etd.cobot.safeassist` | cobot | 6 | generic | enterprise private |
| `etd.atlas.humanoid_walkfetch` | humanoid | 9 | Boston Dynamics Atlas | commercial, per-site |
| `etd.hyundai.wia_welding` | weld | 7 | Hyundai WIA H-Motion | commercial, per-site |
| `etd.hyundai.mobed_transport` | transport | 5 | Hyundai MobED AMR | commercial, per-site |
| `etd.hyundai.vest_exoskeleton` | assist | 6 | Hyundai VEX/H-MEX | commercial, subscription |

---

## Each skill package contains

| File | Purpose |
|---|---|
| `manifest.yaml` | Version, compatibility, safety, telemetry |
| `skill.json` | Skill ID, entrypoint, primitives, profiles |
| `chs_profiles.json` | Task-context parameter profiles |
| `capabilities.json` | Read/write capability whitelist |
| `execution_contract.json` | Body/arm/wrist mode, force/speed profile |
| `telemetry/events.json` | Event definitions |
| `tests/acceptance_tests.yaml` | Acceptance test spec |
| `policies/chs_adapter.py` | Entrypoint adapter |

---

## Station profiles

Six station profiles are included in `station_profiles/`:

| Profile | Platform | Max payload | Families |
|---|---|---|---|
| `assembly_station_a` | generic cobot | 20 kg | manipulator, assembly |
| `cobot_zone_a` | generic cobot | 15 kg | cobot, assembly |
| `weld_station_a` | Hyundai WIA H-Motion | 25 kg | weld, cobot |
| `mobed_logistics_a` | Hyundai MobED AMR | 100 kg | transport |
| `humanoid_hmgma_a` | Boston Dynamics Atlas | 20 kg | humanoid, manipulator |
| `exo_assembly_a` | Hyundai VEX/H-MEX | 30 kg | assist, cobot, assembly |

Use `--station-profile` in the CLI or `station_id` in the API to gate installation by station compatibility.

---

## Safety model

Every package **must** declare that it cannot override:
- emergency stop
- collision core
- locomotion balance core
- certified torque limits
- human protective stop

A package that requests any forbidden capability is blocked at validation.

---

## Marketplace model

| License | Source | Entitlement | Example |
|---|---|---|---|
| `open_source` | full source | no | `etd.pickplace.basic` |
| `commercial` | partial/binary | yes | `etd.assembly.precision`, `etd.hyundai.wia_welding` |
| `commercial` | binary only | yes | `etd.inspect.vision` |
| `enterprise_private` | private | yes | `etd.cobot.safeassist` |

---

## Test suite

```
tests/
├── test_validator.py         # 59 — _JSONSCHEMA_AVAILABLE=False branches (incl. non-dict doc → False), engine exception, .yml load, missing telemetry key, non-dict manifest → empty meta
├── test_api.py               # 35 — REST endpoints incl. station+nonexistent-skill branch, absolute path, available_services override, station_id compatible=True, find_skill None skips compat, decision-is-None → 404, policy-missing → 404
├── test_cli.py               # 68 — stations command, install not-found, _check_station_entry(None), chained --family+--free filter, missing requiredServices → else [], --robot-class+--service together, human-aware station warning, missing services text output, warnings branch, install decision-None, publish no-skip-sign branch, station entry missing-services + human-aware warning, check_station_entry None→early-return, serve command uvicorn.run, revoke new-file/append/idempotent, audit-log no-file/entries, validate-context valid/invalid/missing/json, rollout set-stage canary/skip-error/status-empty/status-entries
├── test_middleware_contract.py # 46 — ETDMiddleware ABC, load_middleware_adapter, HyundaiWIAAdapter dry_run reads/publish/inject/topic_for/telemetry sink, live-mode ROS2 stubs, NullSink/ConsoleSink/FileSink/MultiSink/MQTTSink, integration: WIA skill + adapter + FileSink
├── test_hyundai_adapters.py   # 48 — HyundaiMobEDAdapter (18 tests + 4 integration), HyundaiExoAdapter (22 tests + 4 integration); simulate_fatigue progression, set_pose/set_fatigue/set_intent helpers, full skill runs with FileSink
├── test_atlas_adapter_registry.py # 47 — AtlasAdapter unit+integration, adapter registry prefix/exact/fallback/register, get_adapter_for_skill dry_run+sink, skill_action_server auto-wiring
└── test_entitlement_token.py      # 36 — EntitlementToken payload/covers/expiry, issue_token roundtrip, verify_token valid/wrong-key/tampered/expired, SkillStore integration with signed token, CLI token issue/verify
├── test_version_negotiator.py     # 47 — parse_version, satisfies (>=/>/<=/</==/!=/~= compat-release/conjunctions), best_version, sort_versions, SkillStore.get_versions/get_entry, CLI versions command
├── test_review_pipeline.py        # 48 — StageResult/ReviewResult, pipeline sandbox/schema/capability/safety/compat stages, human_review_required flag, real packages, CLI review command
├── test_sandbox.py                # 66 — SandboxViolation/SandboxReport, SandboxChecker (config-only, forbidden imports/OS calls/builtins/open-write), multi-file, pycache exclusion, syntax errors; SkillSandbox runtime blocker; ReviewPipeline sandbox stage; CLI sandbox-check
├── test_vendor_feed.py            # 51 — VendorFeed/FeedRecord dataclasses, create_feed_payload roundtrip, verify_feed_signature (valid/wrong-key/missing/tampered/invalid-hex), VendorFeedManager register/unregister/load/load-from-file/aggregate/dedup/verified-wins/get_versions/find_skill/list_skills/list_feeds; CLI feed create/verify/import
├── test_dashboard.py              # 39 — StationHealth/RolloutEntry/RecentEvent, DashboardSnapshot (ASCII render/sections/placeholders/OK-FAIL marks/to_dict), Dashboard data loading (store/rollout/stations/audit), summary counters, station active/idle (24 h window), watch refresh count, real repo data, CLI dashboard/--json/--events
└── test_publisher_portal.py       # 45 — STATUSES, SubmissionRecord (to_dict/from_dict), _read_skill_meta, PublisherPortal submit (auto-approve/high-risk/forbidden-import/unique-ids/persists), query (get/list/filters), decisions (approve/reject/revision/wrong-status-raises), resubmit, API (submit/404/list/stats/approve), CLI publisher submit/list/approve
├── test_marketplace.py       # 48 — skill_store __main__ block, validation_failed reason, __init__ exports, missing licensing_policy → {}, _compat_level non-dict no-level-attr → D, revoked skill blocked, non-revoked not blocked, no-revoked-file → empty set, _load_revoked extracts ids, audit allowed/blocked entries, signature_invalid blocks install
├── test_station_profiles.py  # 39 — compatibility checker, optional fields, no-services branch, empty-required+nonempty-available, all-required-present+nonempty-available, API, CLI
├── test_orbit_bridge.py      # 39 — all severity mappings, filter rules, callback/timestamp, replay, timestamp_ms=0 preserved, replay event without data key
├── test_sim_modules.py       # 225 — event_replay __main__ block, visualizer.main(), FakeMiddleware, all main()s, _pick_context fallback, report_runner release_out+missing-OEM-ctx+non-dir-skip, failure_scenarios exception branch+detail else-branches, demo fail_fast break, scenario_runner non-dir skip, marketplace_demo exit-1+pick-ctx-path-not-exists, ascii_timeline empty-result+no-summary-keys+zero-duration, run_traced open-primitive cleanup, _plot_gantt matplotlib happy path + --save main branch + plt.show() no-save path, validate_examples failing-package
├── test_acceptance.py        # 98 — 39 YAML scenarios + AcceptanceMiddleware topics, _run_test edges, adapter safety branches (exo/cobot/wia/mobed/assembly/inspect/atlas), main() CLI, inject empty-patch, legacy 'expected' key, inject without at_primitive+safety_state, test_id name/unknown fallback, _load_run default entrypoint, main() no-skill directory scan, failed-suite SystemExit(1), exo no-middleware defaults + lumbar mode + read-only, atlas no-middleware defaults + handover loop sleep, wia no-middleware defaults + mid-traverse abort, cobot no-middleware defaults, mobed no-middleware + mid-segment abort, inspect no-middleware defaults
├── test_ros2_bridge.py       # 43 — server/client main(--dry-run), no-middleware branches, all-8 parametrized, main() without --dry-run → run_ros2(), full rclpy mock: ActionServer callback capture + invocation, client timeout/rejected/happy-path, client feedback callback invocation, local-execute sys.path.insert branch
├── test_signing.py           # 62 — generate/sign/verify main(), keypair gen, release_package, all-8 roundtrip, generic-name else-branch, release validation failure exit-1, whitespace pub-key → False, actual signing else-branch, manifest-parse exception → default version, verify no-sig-file prints error
├── test_skill_composer.py    # 57 — SkillStep validation/from_dict/to_dict, ComposedSkill from_dict/to_dict, SafetyContext violations/abort, StepResult.succeeded, mock_executor, SkillComposer.validate (no-steps/self-ref/store-miss/version-unsatisfiable), run (success/abort/skip/retry/exhausted-retry/exception/shared-ctx/pre-aborted/durations), ComposedSkillResult.summary/to_dict, load_composed_skill, CLI compose validate|run
├── test_cross_platform.py    # 64 — HumanoidPlatform (families/primitives/to_dict), BUILTIN_PLATFORMS (6 platforms, namespaces, families), load_skill_info, HumanoidRegistry (register/unregister/get/list), check_compat (same-platform/compatible/incompatible/family-mismatch/topic-remappings/unknown-platform/missing-capability-flags), PlatformCompatResult (summary/to_dict), compat_matrix (no-skill/with-skill/family-filter), render_matrix_ascii, CLI platform list|check|matrix
├── test_onrobot_store.py     # 66 — CachedEntitlement (expiry/covers/wildcard/to_dict), EntitlementCache (add/get/evict/list/valid_count/persist/node_id), CachedManifest (roundtrip/defaults), SkillManifestCache (put/get/remove/list/persist/source_node), MeshSyncRecord (roundtrip), MeshSync (register/announce/receive/sync_status/auto-register/clear-pending), OnRobotStore (install_offline/is_available/sync_from_central/get_offline_skills/evict/summary/to_dict/autocreate-dir), CLI onrobot cache list|add|evict + sync status
├── test_fleet_manager.py     # 61 — RobotNode (defaults/to_dict), NodeDeployResult (roundtrip), FleetDeployment (counts/summary/to_dict), FleetHealthSnapshot (to_dict/render_ascii), FleetManager (register/replace/unregister/get/list/persist/autocreate), heartbeat (status/last_seen/skills/unknown), deploy (all-ok/unknown-node/partial/updates-inventory/no-duplicates/completed_at/result-fields/persists/platform-compat-incompatible/compat-compatible), deployment queries (list-all/filter-skill/filter-status/get/not-found/count), fleet_status (node-counts/coverage/deployment-count/to_dict/render_ascii), CLI fleet nodes list|register|unregister + deploy + status + deployments
├── test_api_extensions.py    # 51 — /platform/list (count/structure/atlas), /platform/platform/{id} (found/404/families), /platform/check (compatible/incompatible/topic-remappings/family-mismatch), /platform/matrix (30-pairs/no-self/with-skill/family-filter), /fleet/nodes (list/register-201/list-after/get/get-404/delete/delete-404/heartbeat/heartbeat-404), /fleet/deployments (deploy-201/completed/structure/list/get/get-404/filter-skill), /fleet/status (200/structure), /compose/validate (valid/invalid-no-steps/self-ref/skill-id), /compose/run (200/success/step-results/multi-step/structure), /compose/examples (list/structure/validate/run/404s)
├── test_telemetry_analytics.py # 70 — ExecutionEvent (dict/round-trip/defaults), ExecutionRecord (make/succeeded/events/round-trip), _percentile (empty/single/median/p100/p0), TelemetryStore (count/record/persist/query-filters/limit/newest-first/skill_ids/node_ids/clear/malformed-skipped/parent-dirs/since), TelemetryAnalyzer (stats-none/counts/rate/durations/failures/percentiles/to_dict/summary, node_stats-empty/populated, recent_failures/limit-zero, anomalies-insufficient/zero-stdev/outlier/sorted/skill-filter, report-structure/empty), REST API /telemetry (record-201/explicit-ids, list-200/empty/filter-skill/status/limit, stats-404/200/structure, report-200/structure/empty, anomalies-200/structure/detects/z_score/skill-filter)
├── test_dependency_resolver.py # 59 — SkillDependency (dict/round-trip/defaults/optional), DependencyGraph (resolve-leaf/order/unknown/cycle/self-cycle, detect_cycles-none/found, transitive_deps/leaf/cycle-empty, missing-none/all/partial), DependencyResolver (install_order/check_satisfied-optional-excluded/dep_tree-nested/cycle-flagged/from_dict/cycles), DependencyStore (register/get/list/remove/update/persist/create-dir/corrupt/resolver()), REST API /deps (register-201, list/get/delete-CRUD, order-no-deps/with-deps/cycle-409, tree-200, check-satisfied/missing, cycles-none/detected)
├── test_scheduler.py           # 64 — ScheduledJob (to_dict/round-trip/defaults/JobRunResult), add_job (interval-next-run/once-run-at/validation-raises), CRUD (get/list-filters/newest-first/remove/count/persist/create-dir/corrupt-empty), pause/resume (transitions/wrong-status-false/unknown-false), due_jobs (future/past/paused/done/sorted), record_run (count/last-run/interval-advance/once-done/success-flag/result/unknown-None), REST API /scheduler (create-201/422, list-200/filter, get/delete/pause-409/resume-409/due/record-run-200/404)
├── test_quota_manager.py       # 58 — QuotaPolicy (dict/round-trip/specificity-4-cases/defaults), QuotaManager policies (set/get/list/remove/update/persist/create-dir), check (no-policy/disabled/under|at-hourly/burst/hourly-window/daily-limit/daily-window/remaining/no-limit-None/policy_matched/wildcard-matches/specific-overrides-wildcard/node-specific/to_dict), usage (record/empty/filter-skill|node/persist/clear-all/by-skill/returns-count), REST API /quota (policy-CRUD/check-no-policy|structure|blocks-after-record/record-201|in-usage/usage-200|empty|filter|clear)
└── test_ab_testing.py          # 66 — ABVariant (dict/round-trip/defaults), ABExperiment (make/to_dict/round-trip/get_variant/route/route-zero-weight/route-raises-paused|concluded|all-zero/pause-resume-conclude/transitions/raise-twice), ABExperimentStore (save/get/list/filter/delete/persist/update/newest-first/parent-dirs/corrupt-empty), ABAnalyzer (compare-structure/no-data/with-data, recommend-None/success-rate-wins/duration-tiebreak/to_dict), REST API /ab (create-201/has-id/one-variant-422, list-200/empty/after/filter, get-found/404, delete-200/404/then-404, pause-200/404/409, resume-200/409, conclude-200/409-twice, route-200/paused-409, results-200/structure/404, recommend-200/no-data-None/404)
```

Run: `python -m pytest` — 1798 tests, all passing.

---

## CI

GitHub Actions runs `validate_examples.py` + `sim/report_runner.py` + pytest + acceptance runner on every push and pull request (`.github/workflows/validate-examples.yml`).

---

## Key documents

- [`docs/INDEX.md`](docs/INDEX.md) — full document index + implementation status
- [`docs/architecture.md`](docs/architecture.md) — layered architecture
- [`docs/package-format.md`](docs/package-format.md) — skill package file layout
- [`docs/atlas-integration-notes.md`](docs/atlas-integration-notes.md) — Boston Dynamics / Atlas integration boundary
- [`docs/hyundai-integration-notes.md`](docs/hyundai-integration-notes.md) — Hyundai WIA welding, MobED AMR, and VEX exoskeleton integration boundaries
- [`docs/licensing-and-commercialization.md`](docs/licensing-and-commercialization.md) — open/commercial models
- [`docs/marketplace-commercial-policy.md`](docs/marketplace-commercial-policy.md) — marketplace policy
- [`docs/use-cases-automotive.md`](docs/use-cases-automotive.md) — automotive production use cases
- [`CHANGELOG.md`](CHANGELOG.md) — version history

---

## License

[LICENSE](LICENSE)
