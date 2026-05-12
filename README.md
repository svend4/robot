# ETD Robotics Skill Runtime — Prototype v0.5.0

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
├── examples/                           # 8 reference skill packages (all level A)
│   ├── etd.pickplace.basic/            # pick-and-place (MIT, free)
│   ├── etd.assembly.precision/         # precision force-controlled insertion
│   ├── etd.inspect.vision/             # vision QA / defect scan
│   ├── etd.cobot.safeassist/           # human-collaborative handover
│   ├── etd.atlas.humanoid_walkfetch/   # Boston Dynamics Atlas walk-and-fetch
│   ├── etd.hyundai.wia_welding/        # Hyundai WIA H-Motion arc-welding
│   ├── etd.hyundai.mobed_transport/    # Hyundai MobED AMR logistics
│   └── etd.hyundai.vest_exoskeleton/  # Hyundai VEX/H-MEX wearable assist
├── marketplace/                        # skill store: index, policy, license profiles
├── adapters/                           # orbit event bridge, station profile loader, OEM adapters
├── sim/                                # simulation, demo runners, visualizer
├── schemas/                            # JSON Schema Draft 2020-12 for all package files
├── station_profiles/                   # 6 station compatibility profiles
├── scripts/                            # release packaging, signing, keypair generation
├── api/                                # FastAPI REST skill store
├── tests/                              # 160 pytest tests
├── docs/                               # architecture, roadmap, licensing, commercialization
├── integrations/ros2/                  # ROS 2 action server/client bridge (stub)
├── etd_reference_validator.py          # core validator
├── etd_cli.py                          # CLI: validate, install, stations, info
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

# REST API
uvicorn api.app:app --reload
# GET  http://localhost:8000/store/skills
# POST http://localhost:8000/store/install  {"skillId": "etd.pickplace.basic"}
# GET  http://localhost:8000/store/stations

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
├── test_validator.py         # 47 — semantic checks, main() pretty/json/fallback ctx, score degradation
├── test_api.py               # 27 — REST endpoints incl. absolute path, family filters, station install
├── test_cli.py               # 40 — stations command, install not-found, _check_station_entry(None)
├── test_marketplace.py       # 33 — validation_failed reason, adapters/__init__ + sim/__init__ exports
├── test_station_profiles.py  # 37 — compatibility checker, optional fields, no-services branch, API, CLI
├── test_orbit_bridge.py      # 37 — all severity mappings, filter rules, callback/timestamp, replay
├── test_sim_modules.py       # 204 — visualizer.main(), ascii_timeline edges, _plot_gantt ImportError, FakeMiddleware
├── test_acceptance.py        # 46 — 39 YAML scenarios + AcceptanceMiddleware topics, _run_test edges, main() CLI
├── test_ros2_bridge.py       # 34 — server/client main(--dry-run), no-middleware branches, all-8 parametrized
└── test_signing.py           # 47 — _package_digest missing files, sign/verify partial, release_package.main()
```

Run: `python -m pytest` — 552 tests, all passing.

---

## CI

GitHub Actions runs `validate_examples.py` + `sim/report_runner.py` + pytest + acceptance runner on every push and pull request (`.github/workflows/validate-examples.yml`).

---

## Key documents

- [`docs/INDEX.md`](docs/INDEX.md) — full document index + implementation status
- [`docs/architecture.md`](docs/architecture.md) — layered architecture
- [`docs/package-format.md`](docs/package-format.md) — skill package file layout
- [`docs/atlas-integration-notes.md`](docs/atlas-integration-notes.md) — Boston Dynamics / Atlas integration boundary
- [`docs/licensing-and-commercialization.md`](docs/licensing-and-commercialization.md) — open/commercial models
- [`docs/marketplace-commercial-policy.md`](docs/marketplace-commercial-policy.md) — marketplace policy
- [`docs/use-cases-automotive.md`](docs/use-cases-automotive.md) — automotive production use cases
- [`CHANGELOG.md`](CHANGELOG.md) — version history

---

## License

[LICENSE](LICENSE)
