# Skill Package Format

Every ETD skill package is a directory whose name is the skill ID
(e.g. `etd.pickplace.basic`). The directory must contain the files
described below. Optional files extend the package but are not required
for validation to pass.

---

## Directory layout

```
etd.<vendor>.<name>/
├── manifest.yaml              # required — version, compatibility, safety, telemetry
├── skill.json                 # required — skill ID, entrypoint, primitives, profiles
├── chs_profiles.json          # required — CHS parameter profiles
├── capabilities.json          # required — read/write/forbidden topic lists
├── execution_contract.json    # required — body/arm/wrist mode, force/speed profile
├── telemetry/
│   └── events.json            # required — list of emitted event names
├── tests/
│   └── acceptance_tests.yaml  # required — acceptance test scenarios
├── policies/
│   └── chs_adapter.py         # required — skill entrypoint (run function)
└── package.sig                # optional — Ed25519 signature (added by release_package.py)
```

---

## File descriptions

### `manifest.yaml`

Top-level package descriptor. Fields:

```yaml
apiVersion: etd.robotics/v0.1
kind: SkillPackage
metadata:
  name: etd.pickplace.basic      # must match directory name
  version: 0.1.0
  title: "Human-readable title"
  vendor: etd-lab
  description: >
    One-paragraph description.
  license: MIT                   # MIT | commercial | enterprise_private
  tags: [manipulator, pick-place]

compatibility:
  robotClass: [cobot, fixed_manipulator]
  runtime: ">=0.1.0"
  osLayer: application
  requiresServices:              # mandatory — must be present in station profile
    - perception.object_pose
    - state.safety_state
  optionalServices:              # nice-to-have — missing ones are reported but not blocking
    - telemetry.metrics

etdMapping:
  MVS: { role: "...", concerns: [...] }
  SVS: { role: "...", concerns: [...] }
  BVS: { role: "...", concerns: [...] }
  CHS: { role: "...", concerns: [...] }

constraints:
  payloadKgMax: 20
  objectSizeCmMax: 60
  minConfidence: 0.85

safety:
  packageCanNotOverride:         # must include all five forbidden capabilities
    - emergency_stop
    - collision_core
    - locomotion_balance_core
    - certified_torque_limits
    - human_protective_stop
  fallbackSkill: etd.safe_stop_and_retreat
  fallbackMode: safe_hold_or_abort
  requiresHumanAwareBehavior: true

telemetry:
  events: [skill.started, primitive.entered, ...]
```

### `skill.json`

Runtime metadata for the skill runtime engine:

```json
{
  "skillId": "etd.pickplace.basic",
  "version": "0.1.0",
  "entrypoint": "policies/chs_adapter.py:run",
  "family": "pickplace",
  "executionMode": "task_oriented",
  "supportsTransfer": true,
  "supportsHumanAwareMode": true,
  "defaultChsProfile": "small_box",
  "chsProfiles": ["small_box", "fragile_item"],
  "primitiveOrder": [
    "approach_arc", "guarded_grasp", "lift_stabilize",
    "transport_safe", "place_release"
  ]
}
```

The `entrypoint` field is `<relative-path>:<function>`. The runtime loads
the Python module and calls `run(job_context, middleware)`.

### `chs_profiles.json`

Defines named parameter presets for the CHS layer. Each profile is a dict
of named values that `chs_adapter.py` reads to configure skill behaviour:

```json
{
  "small_box": {
    "payloadKg": 1.2,
    "forceWindowN": [5, 25],
    "approachSpeedMmS": 80
  },
  "fragile_item": {
    "payloadKg": 0.4,
    "forceWindowN": [2, 8],
    "approachSpeedMmS": 30
  }
}
```

The profile name is passed in `job_context.chsProfile`. Unrecognised
profile names fall back to the default profile defined in `skill.json`.

### `capabilities.json`

Declares exactly which topics the skill may read, write, or is forbidden
from touching:

```json
{
  "read": [
    "state.safety_state",
    "perception.object_pose"
  ],
  "write": [
    "command.skill_intent",
    "telemetry.events"
  ],
  "forbidden": [
    "command.servo_torque",
    "command.emergency_stop_override",
    "command.balance_core_override"
  ]
}
```

The validator blocks any package whose `write` list contains a topic
that appears in the global forbidden set
(`command.emergency_stop_override`, `command.balance_core_override`,
`command.collision_disable`, etc.).

### `execution_contract.json`

A sample execution intent payload showing the default body/arm/wrist mode
and force/speed profile. Used for documentation and validation of the
intent schema:

```json
{
  "body_mode": "stable_reach",
  "arm_mode": "guarded_arc",
  "wrist_mode": "adaptive_contact",
  "primitive": "approach_arc",
  "speed_profile": "industrial_safe",
  "force_profile": "adaptive",
  "timeout_sec": 18
}
```

### `telemetry/events.json`

List of event names the skill promises to emit. Used by the validator to
confirm that the package declares at least the required baseline events:

```json
{
  "events": [
    "skill.started",
    "primitive.entered",
    "primitive.exited",
    "skill.completed",
    "skill.aborted"
  ]
}
```

Additional domain-specific events (e.g. `welding.arc_started`,
`assist.torque_applied`) may be declared here.

### `tests/acceptance_tests.yaml`

Declarative acceptance test scenarios run by `sim/acceptance_runner.py`:

```yaml
suite: etd.pickplace.basic acceptance tests
version: 0.2.0
skill_id: etd.pickplace.basic

tests:
  - id: small_box_cycle_pass
    description: Default small_box profile completes full pick-place cycle
    profile: small_box
    input:
      job_context: {chsProfile: small_box, priority: normal}
    expect:
      status: completed

  - id: abort_at_approach
    description: Human in forbidden zone aborts at approach_arc
    profile: small_box
    input:
      job_context: {chsProfile: small_box}
    inject:
      at_primitive: approach_arc
      safety_state: {human_in_forbidden_zone: true}
    expect:
      status: aborted
      reason: human_in_forbidden_zone
```

Key fields: `id`, `description`, `profile`, `input.job_context`,
`inject` (optional — overrides a topic value at a specific primitive),
`expect` (status, reason, result_keys).

### `policies/chs_adapter.py`

The skill entrypoint. Must expose a `run(job_context, middleware)` function:

```python
def run(job_context: dict, middleware=None) -> dict:
    """
    Args:
        job_context: CHS job dict (chsProfile, payloadKg, …)
        middleware:  OEM adapter with .read(topic) and .publish(topic, msg)
                     If None, simulation defaults are used.
    Returns:
        { 'status': 'completed'|'aborted', 'reason': …, … }
    """
```

The middleware contract:
- `middleware.read(topic)` → dict or None
- `middleware.publish(topic, msg)` → None (fire-and-forget)
- Both methods are optional — `hasattr(middleware, 'read')` is checked before
  each call, allowing simulation without OEM middleware.

---

## Naming conventions

| Item | Convention | Example |
|---|---|---|
| Skill ID | `etd.<vendor>.<name>` | `etd.hyundai.wia_welding` |
| Directory name | equals skill ID | `etd.hyundai.wia_welding/` |
| Primitive names | `snake_case` verbs | `approach_seam_start` |
| CHS profile names | `snake_case` nouns | `standard_seam` |
| Topic names | `<domain>.<entity>` | `state.safety_state` |
| Event names | `<domain>.<verb>` | `welding.arc_started` |

---

## Validation levels

| Level | Meaning | Installable |
|---|---|---|
| A | Fully compatible — all required services present, all constraints met | Yes |
| B | Minor gaps — optional services missing or minor constraint mismatch | Yes |
| C | Degraded — required services missing or significant constraint mismatch | No |
| D | Incompatible — wrong robot class, safety violations, or schema errors | No |
