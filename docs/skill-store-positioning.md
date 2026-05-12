# ETD Skill Store Positioning

## One-line positioning

ETD is an application-layer standard for packaging, validating, simulating,
and deploying robot skills safely across industrial humanoid workcells.

## Store model

An ETD Skill Store distributes signed skill packages, not raw low-level
controller code. Each skill must include metadata, CHS profiles, capability
policy, execution contract, telemetry, and acceptance tests.

The store is not a code repository — it is a governed distribution layer
where every package has been validated, signed, and checked for station
compatibility before it reaches a robot.

## Required store checks

All 8 checks below must pass before a package can be listed:

| Check | Tool | Gate |
|---|---|---|
| Schema validation | `etd_reference_validator.py` | All 5 package files pass JSON Schema Draft 2020-12 |
| Capability safety | Validator | No forbidden capabilities in `capabilities.json` write list |
| Runtime compatibility | Validator | Compatibility level A or B |
| Station compatibility | `validate_for_install` | Required services present in station profile |
| Simulation smoke test | `sim/acceptance_runner.py` | All happy-path scenarios pass |
| Failure scenario test | `sim/failure_scenarios.py` | Human-zone abort, balance abort, and sensor-loss abort all trigger correctly |
| Release signature | `scripts/sign_package.py` | Ed25519 signature present and verifiable |
| Rollback metadata | `manifest.yaml` | `fallbackSkill` and `fallbackMode` declared |

## Current reference packages (v0.5.0)

Eight packages across five robot platforms, all passing at level A:

| Package | Category | Platform |
|---|---|---|
| `etd.pickplace.basic` | Pick & Place | Generic cobot |
| `etd.assembly.precision` | Precision Assembly | Generic cobot |
| `etd.inspect.vision` | Vision Inspection | Generic cobot |
| `etd.cobot.safeassist` | Cobot Safe Assist | Generic cobot |
| `etd.atlas.humanoid_walkfetch` | Humanoid Walk-and-Fetch | Boston Dynamics Atlas |
| `etd.hyundai.wia_welding` | Arc Welding | Hyundai WIA H-Motion |
| `etd.hyundai.mobed_transport` | AMR Transport | Hyundai MobED |
| `etd.hyundai.vest_exoskeleton` | Exoskeleton Assist | Hyundai VEX / H-MEX |

## Why this matters

The arrival of humanoid app stores (Unitree, Boston Dynamics / Hyundai) makes
a safe industrial standard more urgent. A downloadable skill for a walking
machine is not equivalent to a phone app: it carries physical safety, liability,
and station-context constraints that a consumer app store model cannot enforce.

ETD's position is to be the neutral layer that every OEM and integrator can
adopt — above their proprietary control stacks, below the enterprise workflow
layer — with safety enforcement built into the package format itself.
