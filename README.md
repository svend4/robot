# ETD Robotics Skill Runtime — Prototype

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
├── examples/                     # 4 reference skill packages
│   ├── etd.pickplace.basic/      # pick-and-place (MIT, free)
│   ├── etd.assembly.precision/   # precision insertion (commercial, per-site)
│   ├── etd.inspect.vision/       # vision QA inspection (commercial, subscription)
│   └── etd.cobot.safeassist/     # human-aware cobot assist (enterprise)
├── marketplace/                  # skill store: index, policy, license profiles
├── sim/                          # simulation and demo runners
├── adapters/                     # OEM/middleware integration adapters
├── schemas/                      # JSON schemas for all package files
├── station_profiles/             # example station compatibility profiles
├── scripts/                      # release packaging tool
├── docs/                         # architecture, roadmap, licensing, commercialization
├── etd_reference_validator.py    # core validator
├── validate_examples.py          # run all 4 examples through validator
├── runtime_context.json          # example runtime context
└── requirements.txt              # PyYAML >= 6.0
```

---

## Quick start

```bash
pip install -r requirements.txt

# Validate all 4 example packages
python validate_examples.py

# Run simulation scenarios
python sim/run_sim_demo.py
python sim/run_assembly_demo.py
python sim/scenario_runner.py
python sim/failure_scenarios.py

# Generate a validation report
python sim/report_runner.py

# Marketplace install-decision demo
python sim/marketplace_demo.py
```

All four packages should report `valid=True, level=A, score=1.0`.

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

## Safety model

Every package **must** declare that it cannot override:
- emergency stop
- collision core
- locomotion balance core
- certified torque limits
- human protective stop

A package that requests any forbidden capability is blocked by the validator.

---

## Marketplace model

| License | Source | Entitlement | Example |
|---|---|---|---|
| `open_source` | full source | no | `etd.pickplace.basic` |
| `commercial` | partial/binary | yes | `etd.assembly.precision` |
| `commercial` | binary only | yes | `etd.inspect.vision` |
| `enterprise_private` | private | yes | `etd.cobot.safeassist` |

---

## CI

GitHub Actions runs `validate_examples.py` + `sim/report_runner.py` on every push and pull request (`.github/workflows/validate-examples.yml`).

---

## Roadmap (v0.2)

- Real JSON Schema validation (replace manual checks)
- Package signing (Ed25519)
- Simulator certification flow
- Fleet rollout policy
- REST API for skill store

---

## Key documents

- [`docs/architecture.md`](docs/architecture.md) — layered architecture
- [`docs/roadmap-v0.2.md`](docs/roadmap-v0.2.md) — next milestones
- [`docs/licensing-and-commercialization.md`](docs/licensing-and-commercialization.md) — open/commercial models
- [`docs/marketplace-commercial-policy.md`](docs/marketplace-commercial-policy.md) — marketplace policy
- [`docs/atlas-integration-notes.md`](docs/atlas-integration-notes.md) — Boston Dynamics / Atlas integration
- [`docs/use-cases-automotive.md`](docs/use-cases-automotive.md) — automotive production use cases
- [`CHANGELOG.md`](CHANGELOG.md) — version history

---

## License

[LICENSE](LICENSE)
