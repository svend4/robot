# Changelog

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
