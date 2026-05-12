# ETD Architecture

## Overview

ETD (application-layer skill runtime) sits between enterprise/workflow
systems and OEM robot middleware. It validates skill packages, manages
entitlement, and emits bounded high-level skill intents — without touching
certified safety-critical control.

```
┌─────────────────────────────────────────────────┐
│          Enterprise / Workflow Layer            │
│  (MES, WMS, ERP, mission planners)              │
└────────────────────┬────────────────────────────┘
                     │  skill requests / job contexts
                     ▼
┌─────────────────────────────────────────────────┐
│              ETD Application Layer              │
│                                                 │
│  ┌─────────────┐  ┌──────────────┐             │
│  │  Validator  │  │  Marketplace │             │
│  │ (JSON Schema│  │  (index,     │             │
│  │  A–D levels)│  │   entitle-   │             │
│  └──────┬──────┘  │   ment,sign) │             │
│         │         └──────┬───────┘             │
│  ┌──────▼──────────────▼───────────────┐       │
│  │         Skill Runtime               │       │
│  │  validate → install → execute       │       │
│  │  (ETDSkillActionServer / adapter)   │       │
│  └──────────────────┬──────────────────┘       │
└─────────────────────┼───────────────────────────┘
                      │  command.skill_intent
                      ▼
┌─────────────────────────────────────────────────┐
│           OEM Robot Middleware                  │
│  (Boston Dynamics, Hyundai WIA, MobED, VEX…)   │
│  safety kernel · balance core · motion control  │
└─────────────────────────────────────────────────┘
                      │
                      ▼
              Physical Robot Hardware
```

---

## Components

### ETD Reference Validator (`etd_reference_validator.py`)

Validates a skill package against JSON Schema Draft 2020-12. Produces a
`ValidationReport` with:
- `valid`: bool
- `errors`: list of schema violation messages
- `compatibility`: `{ level: A–D, score: 0–1 }` — how well the package
  matches the runtime context

Levels: **A** = fully compatible, **B** = minor gaps, **C** = degraded,
**D** = incompatible. Only A/B packages can be installed.

### Skill Marketplace (`marketplace/skill_store.py`)

In-memory index of 8 reference packages. Handles:
- `find_skill(skill_id)` → raw package entry dict
- `get_entry(skill_id)` → `StoreEntry` dataclass (id, version, license,
  entitlement, path)
- `validate_for_install(skill_id, station_profile)` → `InstallDecision`
  (allowed, reason, entry)
- License types: `open_source`, `commercial`, `enterprise_private`
- Entitlement gating: commercial packages require `entitlement_checked = True`

### CLI (`etd_cli.py`)

Commands:
- `validate <path>` — validate a package directory against the runtime context
- `install <skill_id>` — check entitlement, validate, report compatibility
- `stations` — list available station profiles
- `info <skill_id>` — show package metadata and capabilities

Flags: `--station-profile`, `--runtime-context`, `--family`, `--free`,
`--robot-class`, `--service`, `--skip-sign`

### REST API (`api/app.py`)

FastAPI endpoints:
- `GET /store/skills` — list all packages in the index
- `GET /store/skills/{skill_id}` — package detail
- `POST /store/install` — install (entitlement + validation check)
- `GET /store/stations` — list station profiles
- `POST /validate` — validate a package path

### ROS 2 Bridge (`integrations/ros2/`)

`ETDSkillActionServer` wraps a skill adapter as a ROS 2 action server.
`ETDSkillActionClient` sends goals and waits for results. Both operate in
dry-run (no ROS 2) mode for testing.

### Signing & Release (`scripts/`)

`sign_package.py` — Ed25519 sign a package directory, writing `package.sig`.
`release_package.py` — validate → sign → zip into `release_out/`.
`generate_keypair.py` — generate a new Ed25519 key pair.
`verify_signature.py` — verify a `package.sig` against a public key.

---

## ETD mapping system

Each skill package declares four ETD layers in `manifest.yaml`:

| Layer | Abbreviation | Role |
|---|---|---|
| **Macro Velocity Subsystem** | MVS | Fine wrist/end-effector control: force, torque, micro-alignment |
| **Segment Velocity Subsystem** | SVS | Arm trajectory, path tracking, speed regulation |
| **Base Velocity Subsystem** | BVS | Base/body stability, locomotion, balance, gait |
| **Contextual Header Subsystem** | CHS | Task context: what the robot should do and with what parameters |

ETD emits `command.skill_intent` messages that declare `body_mode`,
`arm_mode`, `wrist_mode`, and `force_window_n`. The OEM middleware converts
these high-level intents into joint-space commands within its own certified
safety envelope.

---

## Skill execution flow

```
1. Receive job_context (chsProfile, payloadKg, destination, …)
2. Resolve CHS profile → skill parameters
3. For each primitive in PRIMITIVE_ORDER:
   a. Publish primitive.entered
   b. Read state.safety_state → abort if human_in_forbidden_zone
   c. Execute primitive logic (publish skill_intent, read sensors)
   d. Publish primitive.exited
4. Publish skill.completed → return result dict
```

Aborts at any step publish `skill.aborted` with `reason` and
`at_primitive` before returning `{ status: 'aborted', … }`.

---

## Station compatibility

Station profiles (`station_profiles/`) declare:
- `robotClass` — platform type (generic cobot, AMR, humanoid, exo)
- `maxPayloadKg` — maximum supported payload
- `skillFamilies` — which skill families are permitted
- `requiresServices` — mandatory services the station provides
- `humanAware` — whether a human-aware safety model is required

The validator cross-checks a skill's `requiresServices` against the
station's `availableServices` and rejects the install if any required
service is absent.

---

## Safety invariants

Every skill package **must** declare that it cannot override:
- `emergency_stop`
- `collision_core`
- `locomotion_balance_core` (where applicable)
- `certified_torque_limits`
- `human_protective_stop`

A package that requests any of these in its `capabilities.json` write
list is rejected by the validator at installation time.
