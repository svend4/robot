# ETD Publisher and Developer Guide

This guide walks through creating, validating, signing, and publishing an ETD skill package
using the real ETD toolchain. Commands reference the actual CLI and scripts in this repository.

---

## Prerequisites

```
python -m pip install -r requirements.txt
```

Required tools (all in repo root):

| Tool | Purpose |
|---|---|
| `etd_cli.py` | Main CLI: validate, publish, sign, install, verify |
| `etd_reference_validator.py` | JSON Schema + semantic validation (called by CLI) |
| `scripts/sign_package.py` | Ed25519 package signing |
| `scripts/release_package.py` | Build release `.zip` archive |
| `sim/acceptance_runner.py` | Run YAML acceptance scenarios |
| `sim/failure_scenarios.py` | Run failure-mode scenarios |

---

## Step 1 — Create package directory structure

A minimal package requires these files:

```
my.skill.id/
├── manifest.yaml
├── skill.json
├── chs_profiles.json
├── capabilities.json
├── execution_contract.json
├── telemetry/
│   └── events.json
├── tests/
│   └── acceptance_tests.yaml
└── policies/
    └── chs_adapter.py
```

See `docs/package-format.md` for schema details and field requirements.
Use `examples/etd.pickplace.basic/` as the canonical starting point — it passes
all validations at compatibility level A.

---

## Step 2 — Validate the package

### Basic validation

```bash
python etd_cli.py validate examples/my.skill.id/
```

The validator checks all 5 required files against JSON Schema Draft 2020-12, then runs
semantic checks (forbidden capabilities, compatibility level, required fields).

Output example:

```
Skill ID   : my.skill.id
Valid      : True
Level      : A
Checks     :
  schema_manifest        PASS
  schema_skill           PASS
  schema_chs_profiles    PASS
  schema_capabilities    PASS
  schema_execution_contract PASS
  forbidden_capabilities PASS
  compatibility_level    A
```

### Validate against a specific station profile

```bash
python etd_cli.py validate examples/my.skill.id/ \
  --station-profile station_profiles/assembly_station_a.json
```

The station check verifies that every service the skill requires is present in the station
profile and that the robot family and payload are within station limits.

Available station profiles:

| File | Covers |
|---|---|
| `assembly_station_a.json` | precision assembly, cobot arm |
| `cobot_zone_a.json` | collaborative cobot workspace |
| `weld_station_a.json` | Hyundai WIA H-Motion arc-welding cell |
| `logistics_cell_a.json` | pick-and-place, logistics |
| `humanoid_hmgma_a.json` | Atlas humanoid (HMGMA layout) |
| `mobed_logistics_a.json` | Hyundai MobED AMR logistics |
| `exo_assembly_a.json` | Hyundai VEX/H-MEX exoskeleton station |

### Validate with JSON output

```bash
python etd_cli.py validate examples/my.skill.id/ --json
```

Useful for piping into CI or report aggregation.

---

## Step 3 — Run acceptance tests

The acceptance runner executes each YAML scenario in `tests/acceptance_tests.yaml` against
the skill's CHS adapter using the sim middleware:

```bash
python sim/acceptance_runner.py examples/my.skill.id/
```

Each scenario specifies a CHS profile, expected primitives, and expected telemetry events.
A passing result confirms the skill executes its primitive sequence correctly end-to-end
in simulation.

---

## Step 4 — Run failure scenarios

```bash
python sim/failure_scenarios.py
```

This exercises four failure modes that every marketplace-listed package must handle correctly:

| Scenario | Expected result |
|---|---|
| `human_too_close` | skill aborts with `human_in_forbidden_zone` before unsafe primitive |
| `payload_out_of_range` | rejected at CHS validation before execution |
| `missing_service` | validation degrades to compatibility level D |
| `station_incompatible` | station check blocks install |

All four must trigger correctly before a package can be listed.

---

## Step 5 — Generate a signing keypair

If you do not already have a keypair:

```bash
python etd_cli.py keygen --out-dir keys/
```

This creates:

- `keys/etd_signing_key.hex` — private key (keep secret, never commit)
- `keys/etd_signing_key.pub.hex` — public key (include in package metadata or publish separately)

The signing scheme is Ed25519. The `.hex` files are plain hex-encoded key material.

---

## Step 6 — Sign and publish the package

```bash
python etd_cli.py publish examples/my.skill.id/ \
  --key keys/etd_signing_key.hex \
  --out release_out/
```

The `publish` command:
1. Re-runs schema + semantic validation (must pass).
2. Signs the package with `scripts/sign_package.py` — produces `signature.json` inside the package.
3. Builds a `.zip` release archive in `release_out/`.

Output: `release_out/my.skill.id-<version>.zip`

To build the archive without signing (for testing only, not store-listable):

```bash
python etd_cli.py publish examples/my.skill.id/ --skip-sign
```

---

## Step 7 — Verify the signature

```bash
python etd_cli.py verify release_out/my.skill.id-<version>.zip \
  --pub-key keys/etd_signing_key.pub.hex
```

Returns `Signature valid` or `Signature INVALID`. The skill store runs this check
at install time; a package with an invalid or missing signature will not be installed.

---

## Step 8 — Check install eligibility

```bash
python etd_cli.py install my.skill.id \
  --station-profile station_profiles/assembly_station_a.json
```

This simulates the install check without copying any files. Use it to confirm that a package
from the store index can be installed at a given station before actually deploying.

For entitlement-gated (commercial) packages, pass the token:

```bash
python etd_cli.py install my.skill.id \
  --token <entitlement-token> \
  --station-profile station_profiles/assembly_station_a.json
```

---

## Step 9 — Browse the store and view package details

```bash
# List all packages in the store index
python etd_cli.py list

# Show full details for a specific package
python etd_cli.py info etd.pickplace.basic

# List all known station profiles
python etd_cli.py stations
```

---

## Step 10 — Start the REST API server (optional)

```bash
python etd_cli.py serve
```

Starts the FastAPI server at `http://localhost:8000`. Endpoints:

| Endpoint | Description |
|---|---|
| `GET /store/list` | List all packages |
| `GET /store/info/{skill_id}` | Package details |
| `GET /store/stations` | List station profiles |
| `POST /validate` | Validate a package (JSON body) |
| `POST /store/install` | Check install eligibility |

---

## Package author checklist

Before submitting for marketplace review, confirm:

| Item | How to verify |
|---|---|
| All 5 schema files pass | `etd_cli.py validate` → Level A |
| No forbidden capabilities | `etd_cli.py validate` → `forbidden_capabilities PASS` |
| Station compatibility verified | `etd_cli.py validate --station-profile <file>` |
| Acceptance scenarios pass | `sim/acceptance_runner.py` |
| Failure scenarios trigger correctly | `sim/failure_scenarios.py` |
| Package signed | `etd_cli.py publish --key <key>` |
| Signature verifiable | `etd_cli.py verify` → `Signature valid` |
| `fallbackSkill` declared in `manifest.yaml` | grep `fallbackSkill` |
| `fallbackMode` declared in `manifest.yaml` | grep `fallbackMode` |
| All required services listed | `manifest.yaml` `requiredServices` section |

---

## Publisher obligations

A publisher **must not**:

- request forbidden capabilities (`emergency_stop`, `collision_core`, `locomotion_balance_core`,
  `human_protective_stop`, `servo_torque_override`, `safety_config_write`);
- omit safety metadata (`capabilities.json`, `execution_contract.json`, fallback fields)
  — these must always be readable even in commercial packages;
- misrepresent station or robot compatibility;
- submit untested packages as production-ready;
- bypass or stub the failure scenario checks.

A publisher **must**:

- declare `fallbackSkill` and `fallbackMode` in `manifest.yaml`;
- list all services consumed in `requiredServices`;
- provide at least one passing acceptance scenario per CHS profile;
- state the license class and source availability in the manifest;
- provide a support contact.

---

## Publication stages

| Stage | Meaning | Gate |
|---|---|---|
| Q0 Draft | local only, may be incomplete | — |
| Q1 Validated | schemas + semantic checks pass | `etd_cli.py validate` → Level A or B |
| Q2 Simulated | happy-path and failure scenarios pass | acceptance + failure runner |
| Q3 Station-approved | at least one station profile verified | `--station-profile` check |
| Q4 Signed | Ed25519 signature present and verifiable | `etd_cli.py publish` + `verify` |
| Q5 Marketplace-listed | discoverable in store index | store review pass |
| Q6 Pilot-deployed | used in supervised pilot | operator sign-off |
| Q7 Production-certified | approved for production rollout | OEM / integrator / safety-team review |

---

## Required metadata for marketplace publication

```json
{
  "publisher": {
    "name": "Example Robotics Lab",
    "type": "developer|integrator|oem|enterprise",
    "contact": "support@example.com",
    "verified": true
  },
  "commercial": {
    "licenseClass": "open_source|free_proprietary|paid_one_time|subscription|enterprise_private|oem_certified",
    "sourceAvailable": true,
    "redistributionAllowed": true,
    "commercialUseAllowed": true
  },
  "support": {
    "supportLevel": "community|standard|enterprise",
    "updatePolicy": "best_effort|versioned|sla",
    "securityContact": "security@example.com"
  }
}
```

---

## User-facing store listing template

```
Skill name   : ETD Pick & Place Basic
Skill ID     : etd.pickplace.basic
Version      : 0.5.0
Category     : Pick & Place
Publisher    : ETD Lab (verified)
License      : Apache-2.0 — free reference package
Robot class  : cobot, mobile manipulator
Risk level   : low
Requires     : perception.object_pose, manipulation.arm_control,
               workflow.job_context, state.arm_state, safety.zone_monitor
Validated    : Level A
Station compat: assembly_station_a, logistics_cell_a, cobot_zone_a
Signed       : Yes (Ed25519)
Production certified: No (reference / demo)
```

---

## Pricing disclosure (for paid packages)

Commercial packages must disclose:

- per-unit price and billing model (one-time / subscription / site-licence);
- robot limit and site limit covered by the licence;
- whether source code is available (full / partial / binary-only);
- entitlement enforcement mechanism (token / robot-serial binding / cloud check);
- refund policy;
- update and security-patch policy;
- telemetry and data-usage policy.
