# Generic Cobot Skills — ETD Reference

ETD integrates with generic cobot and fixed-manipulator platforms through four reference
skill packages. These packages are platform-agnostic: they run on any robot whose station
profile provides the required services. Like all ETD skills, they sit **above** the OEM
real-time control kernel and communicate through service interfaces — they do not replace,
patch, or override any certified safety or motion-control subsystem.

---

## 1. ETD Pick & Place Basic

**Skill**: `etd.pickplace.basic`
**Family**: pickplace
**Payload**: ≤ 8 kg
**Object size**: ≤ 60 cm
**Realtime class**: non_safety_critical
**Cycle time**: ≤ 18 s (timeout 28 s)
**Retry policy**: bounded_retry (max 2)

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Task type, payload class, destination, priority, tolerance, fragility |
| SVS | Arm trajectory, approach curve, elbow path, obstacle bypass |
| MVS | Wrist pose, force window, contact stability, grasp mode |
| BVS | Stance, centre-of-mass margin, reachability |

### What ETD cannot override

- Emergency stop
- Collision core
- Locomotion balance core
- Certified torque limits
- Human protective stop

### Primitive sequence

```
approach_arc
  → guarded_grasp
    → lift_stabilize
      → transport_safe
        → place_release
```

Every primitive begins with a `state.safety_state` read. If `human_in_forbidden_zone = True`
the skill publishes `skill.aborted` and returns immediately.

### CHS profiles

| Profile | `payloadKg` | `fragility` | `graspMode` | `speedProfile` | `forceWindowN` |
|---|---|---|---|---|---|
| `small_box` | 1.5 | low | parallel_grip | normal | default |
| `fragile_item` | 0.8 | high | soft_contact | gentle | [2, 10] |

### Required services

`perception.object_pose`, `manipulation.arm_control`, `workflow.job_context`,
`state.robot_pose`, `state.arm_state`, `state.wrist_state`, `state.safety_state`,
`safety.zone_monitor`

**Optional**: `perception.part_alignment`, `telemetry.metrics`

### Key telemetry events

`skill.started`, `primitive.entered`, `primitive.exited`, `fallback.triggered`,
`skill.completed`, `skill.aborted`

### Integration boundary

ETD publishes `command.skill_intent` with `body_mode = stable_reach`,
`arm_mode = guarded_arc`, `wrist_mode = adaptive_contact`, and `force_profile = adaptive`.
The OEM arm controller executes the motion within its own safety envelope. ETD reads
`state.arm_state` and `state.wrist_state` for confirmation; it does not write joint angles
or torque setpoints directly.

### Compatible station profiles

`assembly_station_a`, `logistics_cell_a`, `cobot_zone_a`

---

## 2. ETD Assembly Precision

**Skill**: `etd.assembly.precision`
**Family**: assembly
**Payload**: ≤ 5 kg
**Object size**: ≤ 60 cm
**Realtime class**: bounded_contact_sensitive
**Cycle time**: ≤ 35 s (timeout 45 s)
**Retry policy**: bounded_retry (max 2)

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Task type, payload class, precision target, tolerance, alignment mode |
| SVS | Insertion axis trajectory, approach curve, slow-axis approach |
| MVS | Wrist micro-adjustment, force window compliance, contact probing |
| BVS | Rigid stable stance, reachability during insertion, CoM margin |

### What ETD cannot override

- Emergency stop
- Collision core
- Locomotion balance core
- Certified torque limits
- Human protective stop

### Primitive sequence

```
approach_align
  → contact_probe
    → micro_adjust
      → controlled_insert
        → settle_and_verify
          → release_safe
```

`contact_probe` reads `force_control.contact_feedback`. If contact force exceeds the
`forceWindowN` upper bound without alignment confirmation, the skill aborts with
`contact_force_exceeded`. The `micro_adjust` step uses `perception.part_alignment` (required
for this skill) to bring the part within `precisionMm` tolerance before insertion begins.

### CHS profiles

| Profile | `payloadKg` | `precisionMm` | `targetDepthMm` | `forceWindowN` | `alignmentMode` |
|---|---|---|---|---|---|
| `peg_in_hole` | 0.8 | 0.5 | 18 | [5, 20] | vision_plus_contact |
| `connector_insert` | 0.4 | 0.3 | 12 | [4, 15] | fine_vision_guided |

### Required services

`perception.object_pose`, `perception.part_alignment`, `manipulation.arm_control`,
`force_control.contact_feedback`, `workflow.job_context`, `state.robot_pose`,
`state.arm_state`, `state.wrist_state`, `state.safety_state`, `safety.zone_monitor`

**Optional**: `telemetry.metrics`

### Key telemetry events

`skill.started`, `primitive.entered`, `primitive.exited`, `fallback.triggered`,
`skill.completed`, `skill.aborted`

### Integration boundary

ETD publishes `command.skill_intent` with `arm_mode = insertion_axis_hold` (peg_in_hole)
or `slow_axis_approach` (connector_insert), and `wrist_mode = micro_adjust` or
`soft_contact`. The OEM controller executes compliant insertion within its certified force
limits. ETD reads `force_control.contact_feedback` at each step to gate progression;
it does not set servo current or compliance parameters directly.

### Compatible station profiles

`assembly_station_a`

---

## 3. ETD Vision Inspection

**Skill**: `etd.inspect.vision`
**Family**: inspect
**Payload**: ≤ 2 kg (camera head / scanner)
**Object size**: ≤ 60 cm
**Realtime class**: non_safety_critical
**Cycle time**: ≤ 20 s (timeout 30 s)
**Retry policy**: bounded_retry (max 2)

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Task type, inspection target, scan mode, precision, fragility class |
| SVS | Arm sweep trajectory, viewpoint approach, scan arc path |
| MVS | Wrist camera alignment, scan angle, standoff distance |
| BVS | Stable scan stance, reachability to all viewpoints, CoM margin |

### What ETD cannot override

- Emergency stop
- Collision core
- Locomotion balance core
- Certified torque limits
- Human protective stop

### Primitive sequence

```
approach_viewpoint
  → scan_target
    → capture_evidence
      → classify_result
        → report_quality
```

`scan_target` reads `perception.object_pose` to lock the scan reference frame. If
`confidence < minConfidence` (0.82) the skill aborts with `missing_service` rather than
producing a low-confidence quality result. `classify_result` evaluates the captured
evidence against the quality gate defined in the CHS profile. `report_quality` publishes
the classification result via `workflow.job_context` for MES/WMS consumption.

### CHS profiles

| Profile | `payloadKg` | `precisionMm` | `speedProfile` | `bodyMode` | `armMode` | `wristMode` |
|---|---|---|---|---|---|---|
| `barcode_qa` | 0.2 | 1.0 | normal | stable_scan | scan_arc | camera_align |
| `defect_scan` | 0.2 | 0.5 | slow_scan | micro_stable | vision_sweep | camera_align |

### Required services

`perception.object_pose`, `manipulation.arm_control`, `workflow.job_context`,
`state.robot_pose`, `state.arm_state`, `state.wrist_state`, `state.safety_state`,
`safety.zone_monitor`

**Optional**: `perception.part_alignment`, `telemetry.metrics`

### Key telemetry events

`skill.started`, `primitive.entered`, `primitive.exited`, `fallback.triggered`,
`skill.completed`, `skill.aborted`

### Integration boundary

ETD publishes `command.skill_intent` with `arm_mode = scan_arc` or `vision_sweep` and
`wrist_mode = camera_align`. The OEM controller moves the arm through the viewpoint
sequence; ETD reads `state.arm_state` to confirm each viewpoint is reached. ETD does not
control camera exposure, lighting, or sensor settings — those remain under the OEM
perception stack or station infrastructure.

### Compatible station profiles

`assembly_station_a`, `logistics_cell_a`, `cobot_zone_a`

---

## 4. ETD Cobot Safe Assist

**Skill**: `etd.cobot.safeassist`
**Family**: cobot
**Payload**: ≤ 3 kg
**Object size**: ≤ 60 cm
**Realtime class**: non_safety_critical
**Cycle time**: ≤ 30 s (timeout 40 s)
**Retry policy**: bounded_retry (max 2)

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Task type, payload class, fragility, handover mode, human proximity policy |
| SVS | Handover arc trajectory, approach path to handover zone |
| MVS | Wrist compliance during transfer, grasp hold, compliant release |
| BVS | Social-standby body pose, stable reach to handover position |

### What ETD cannot override

- Emergency stop
- Collision core
- Locomotion balance core
- Certified torque limits
- Human protective stop

### Primitive sequence

```
detect_human_ready
  → approach_handover_zone
    → hold_for_transfer
      → release_on_confirmation
        → retreat_safe
```

**Human-ready gate** (`detect_human_ready`): reads `state.safety_state`. If
`human_in_forbidden_zone = True` at skill start, the skill aborts immediately. The
`detect_human_ready` primitive waits for a human-present signal within the handover zone;
if the zone is clear, the skill waits up to `defaultTimeoutSec` before aborting with
`handover_timeout`.

**Compliant hold** (`hold_for_transfer`): the skill holds the payload with `forceWindowN`
bounds ([2, 12] N for `safe_handover`, [2, 10] N for `tool_pass`) and `wristMode =
compliant_release`. The OEM arm holds the object compliantly — ETD does not command the
exact grip force, only the force window and wrist compliance mode.

**Release gate** (`release_on_confirmation`): reads `state.safety_state` for a human
acceptance signal (equivalent to `human_ready_signal = True`). If not received within
`maxCycleTimeSec`, the skill aborts with `handover_timeout` and retreats safely.

### CHS profiles

| Profile | `payloadKg` | `forceWindowN` | `speedProfile` | `graspMode` | `wristMode` |
|---|---|---|---|---|---|
| `safe_handover` | 2.0 | [2, 12] | human_aware | soft_contact | compliant_release |
| `tool_pass` | 1.0 | [2, 10] | human_aware | secure_hold | compliant_release |

### Required services

`perception.object_pose`, `manipulation.arm_control`, `workflow.job_context`,
`state.robot_pose`, `state.arm_state`, `state.wrist_state`, `state.safety_state`,
`safety.zone_monitor`

**Optional**: `perception.part_alignment`, `telemetry.metrics`

### Key telemetry events

`skill.started`, `primitive.entered`, `primitive.exited`, `fallback.triggered`,
`skill.completed`, `skill.aborted`

### Integration boundary

ETD publishes `command.skill_intent` with `body_mode = social_standby`,
`arm_mode = handover_arc`, `wrist_mode = compliant_release`, and `force_window_n = [2, 12]`.
The OEM controller executes compliant motion within its certified safety envelope. ETD does
not command the human-detection sensor, proximity lighting, or collaborative safety zone
geometry — those are station infrastructure controlled by the OEM safety kernel.

### Compatible station profiles

`assembly_station_a`, `cobot_zone_a`

---

## Common principles across all four packages

### Safety model

All four skills share the same top-level constraint: every primitive begins with a
`state.safety_state` read. If `human_in_forbidden_zone = True` at any primitive boundary,
the skill publishes `skill.aborted` and returns immediately.

No generic cobot ETD skill overrides `emergency_stop`, `collision_core`, or
`human_protective_stop`. These remain exclusively under OEM kernel control.

### Middleware contract

All four adapters follow the standard ETD middleware pattern:

```python
if hasattr(middleware, 'read'):
    value = middleware.read(topic)
else:
    value = <simulation_default>

if hasattr(middleware, 'publish'):
    middleware.publish(topic, msg)
```

This means all four skills run in simulation without any OEM middleware installed.
In production, the OEM middleware implements `.read(topic)` and `.publish(topic, msg)`
against the actual sensor and actuator buses.

### Skill intent protocol

ETD communicates high-level intent via `command.skill_intent` messages:

- `type`: always `command.skill_intent`
- `primitive`: current primitive name
- `body_mode / arm_mode / wrist_mode`: motion constraint profile
- `force_window_n`: `[min, max]` allowed force range
- `timestamp`: Unix epoch float

The OEM controller is responsible for converting intent into real-time motion. ETD never
writes joint-space commands.

### Fallback behaviour

All four skills declare `fallbackSkill: etd.safe_stop_and_retreat` and
`fallbackMode: safe_hold_or_abort`. On any abort, ETD publishes `skill.aborted` with a
`reason` field before returning. The OEM platform's fallback controller takes over once
the skill returns.

### Compatibility level

All four packages validate at compatibility **level A** against JSON Schema Draft 2020-12.
The reference packages are signed with Ed25519 and their release artifacts are in
`release_out/`.
