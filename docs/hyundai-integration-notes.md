# Hyundai Robot Platform Integration Notes

ETD integrates with three Hyundai robot platforms at the application layer.
In every case, ETD sits **above** the OEM real-time control kernel and
communicates through service interfaces — it does not replace, patch, or
override any certified safety or motion-control subsystem.

---

## 1. Hyundai WIA H-Motion Arc-Welding Cobot

**Skill**: `etd.hyundai.wia_welding`
**Family**: cobot / fixed_manipulator
**Payload**: ≤ 2 kg (torch + wire spool)
**Realtime class**: soft_realtime

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Seam type, wire feed, amperage, travel speed, inspection mode |
| SVS | Arm seam-path trajectory, seam offset correction, travel speed |
| MVS | Torch wrist micro-alignment, tip position, contact force, wrist angle |
| BVS | Cobot base stability, vibration damping, reach margin |

### What ETD cannot override

- Emergency stop
- Collision core
- Certified torque limits
- Human protective stop

### Primitive sequence

```
approach_seam_start
  → torch_align
    → ignite_arc
      → weld_traverse          ← seam tracking loop, per-step safety check
        → extinguish_arc
          → post_weld_inspect
            → retract_clear
```

**Arc ignition gate**: before `ignite_arc`, ETD reads `state.safety_state`
and requires `human_in_forbidden_zone = False`. The arc zone enforces a
1.5 m exclusion radius. If a human enters during `weld_traverse`, the skill
aborts immediately via `skill.aborted / human_in_forbidden_zone`.

**Seam tracking**: during `weld_traverse` the skill reads
`perception.seam_tracker` at each step. If `confidence < minConfidence`
(default 0.88) the arc is extinguished and the skill aborts with
`seam_lost`.

### Required services

`perception.seam_tracker`, `manipulation.arm_control`,
`force_control.contact_feedback`, `workflow.job_context`,
`state.arm_state`, `state.wrist_state`, `state.safety_state`,
`safety.zone_monitor`, `welding.torch_control`, `welding.arc_monitor`

### Key telemetry events

`welding.arc_started`, `welding.arc_stopped`, `welding.seam_progress`,
`inspection.result`

### Integration boundary

ETD publishes `command.skill_intent` with `force_window_n`, `travel_speed_mm_s`,
and `body/arm/wrist_mode` fields. The OEM H-Motion controller interprets the
intent and executes motion — ETD does not write joint angles or torque
setpoints directly.

---

## 2. Hyundai MobED Autonomous Mobile Robot (AMR)

**Skill**: `etd.hyundai.mobed_transport`
**Family**: mobile_manipulator / amr
**Payload**: ≤ 100 kg
**Max speed**: 1.2 m/s (0.4 m/s human-aware)
**Realtime class**: non_safety_critical

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Origin, destination, payload class, speed tier, human proximity policy |
| SVS | Drive path following, obstacle response, speed regulation |
| MVS | Lift platform fine control, payload balance, dock alignment |
| BVS | Platform tilt, centre of mass, payload inertia management |

### What ETD cannot override

- Emergency stop
- Collision core
- Locomotion balance core
- Human protective stop

### Primitive sequence

```
navigate_to_pickup
  → dock_and_lift
    → navigate_to_destination    ← navigation loop, per-segment safety check
      → dock_and_lower
        → confirm_delivery
```

**Human-aware speed**: during both navigation primitives the skill reads
`state.safety_state`. When `human_in_safety_radius = True` the commanded
speed drops to `humanAwareSpeedMs` (default 0.4 m/s). A full forbidden-zone
entry triggers abort.

**Navigation loop**: each navigation step reads `navigation.path_planner`
for a `path_ready` gate. If the planner reports no path, the skill aborts
with `path_not_ready`. Human-in-forbidden-zone inside the loop causes abort
with `human_in_forbidden_zone` at the current segment.

### Required services

`navigation.path_planner`, `perception.obstacle_detector`,
`manipulation.lift_control`, `workflow.job_context`,
`state.robot_pose`, `state.safety_state`, `safety.zone_monitor`

### Key telemetry events

`navigation.started`, `navigation.arrived`, `transport.lifted`,
`transport.delivered`, `safety.human_near`

### Integration boundary

ETD publishes waypoints and speed-tier intent to the MobED navigation stack.
The OEM platform handles obstacle avoidance, SLAM, and motor control. ETD
does not write wheel velocities or path plans — it requests a destination and
monitors progress via `state.robot_pose` and `navigation.path_planner`.

---

## 3. Hyundai VEX / H-MEX Wearable Exoskeleton

**Skill**: `etd.hyundai.vest_exoskeleton`
**Family**: exoskeleton / wearable
**Payload assist**: ≤ 30 kg
**Realtime class**: hard_realtime
**Session max**: 3600 s (1 hour)

### What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Assist mode, task type, payload class, operator profile, fatigue threshold |
| SVS | Limb trajectory, overhead-reach mode, carry-assist profile, fatigue-adaptive gain |
| MVS | Joint torque assist — elbow, shoulder, lumbar, wrist compliance |
| BVS | Whole-body posture, centre-of-gravity offset, gait synchronisation |

### What ETD cannot override

- Emergency stop
- Collision core
- Certified torque limits
- Human protective stop

### Primitive sequence

```
calibrate_fit
  → detect_intent
    → engage_assist             ← torque delivery, per-cycle safety + fatigue check
      → monitor_fatigue
        → adapt_gain
          → disengage_assist
```

**Intent detection gate** (`detect_intent`): reads
`perception.intent_detector`. If `confidence < intentConfidenceMin`
(default 0.82) the skill aborts with `intent_confidence_too_low`. The
detected `mode` field selects the assist sub-mode:

- `overhead` — shoulder unloading, reach extension
- `lumbar` — lumbar support torque, back brace actuation
- other modes — standard assist

**Fatigue monitoring** (`monitor_fatigue`): reads `state.fatigue_monitor`.
When `fatigue_pct ≥ fatigueThresholdPct` (default 70%) the skill publishes
`assist.fatigue_threshold_reached` and aborts with
`fatigue_threshold_reached`. This prevents operator overexertion.

**Operator panic release**: a panic signal on `state.safety_state` causes
an immediate torque-zero and abort. The fallback mode is `immediate_abort`
— no graceful retraction, no retry.

**Adaptive gain** (`adapt_gain`): reads `state.fatigue_monitor` again and
adjusts `adaptiveGain` based on remaining session time and fatigue level.
Gain reduction reduces assist force as the operator tires, preventing
dependency.

### Required services

`state.exo_joint_state`, `state.safety_state`, `perception.intent_detector`,
`perception.imu_pose`, `force_control.torque_assist`, `workflow.job_context`,
`safety.zone_monitor`, `telemetry.metrics`

### Key telemetry events

`assist.intent_detected`, `assist.torque_applied`,
`assist.overhead_mode_entered`, `assist.lumbar_mode_entered`,
`assist.fatigue_threshold_reached`, `assist.mode_switched`,
`safety.torque_limit_approached`, `safety.operator_panic_release`

### Integration boundary

ETD publishes `command.skill_intent` with `assist_mode`, `assist_force_n`,
and `adaptive_gain` fields. The OEM VEX/H-MEX controller translates these
into joint-level torque commands and enforces hardware torque limits. ETD
does not write motor current or servo setpoints directly.

IMU pose (`perception.imu_pose`) is read for ergonomic posture reporting
only — ETD does not use it to recompute balance or gait.

---

## Common principles across all three platforms

### Safety model

All three skills share the same top-level constraint: every primitive begins
with a `state.safety_state` read. If `human_in_forbidden_zone = True` at
any primitive boundary, the skill publishes `skill.aborted` and returns
immediately. Intra-primitive loops (weld traversal, navigation segments,
exo assist cycles) repeat this check at each step.

No Hyundai ETD skill overrides `emergency_stop`, `collision_core`, or
`human_protective_stop`. These remain exclusively under OEM kernel control.

### Middleware contract

Every skill adapter follows the same pattern:

```python
if hasattr(middleware, 'read'):
    value = middleware.read(topic)
else:
    value = <simulation_default>

if hasattr(middleware, 'publish'):
    middleware.publish(topic, msg)
```

This means all three skills run in simulation without any OEM middleware
installed. In production, the OEM middleware implements `.read(topic)` and
`.publish(topic, msg)` against the actual sensor and actuator buses.

### Skill intent protocol

ETD communicates high-level intent via `command.skill_intent` messages.
The intent payload includes:

- `type`: always `command.skill_intent`
- `primitive`: current primitive name
- `body_mode / arm_mode / wrist_mode`: motion constraint profile
- `force_window_n`: `[min, max]` allowed force range
- `timestamp`: Unix epoch float

The OEM controller is responsible for converting intent into real-time
motion. ETD never writes joint-space commands.

### Fallback behaviour

All three skills declare `fallbackSkill: etd.safe_stop_and_retreat` and
`fallbackMode: safe_hold_or_abort` (except VEX which uses
`immediate_abort`). On any abort, ETD publishes `skill.aborted` with a
`reason` field before returning. The OEM platform's fallback controller
takes over once the skill returns.

---

## Hyundai robot ecosystem — broader context

The three ETD-integrated platforms sit within a larger Hyundai Motor Group
robotics portfolio. Understanding the full ecosystem helps with integration
decisions and future skill package planning.

### Hyundai WIA H-Motion family (beyond the welding cobot)

In addition to the H-Motion cobot used for arc welding, Hyundai WIA's
H-Motion line includes:

- **H-Motion AMR** — autonomous mobile robot carrying up to **1.5 tonnes**
  (distinct from MobED; heavier industrial logistics use case)
- **Parking Robot** — operates in pairs; drives under a vehicle, lifts the
  wheels, and moves cars up to **3.4 tonnes** at up to **1.2 m/s**

These platforms share the H-Motion brand but serve different workcell roles
than the welding cobot.

### MobED (Mobile Eccentric Droid)

MobED is a Hyundai Robotics LAB platform with independent wheel-steering,
LiDAR-camera fusion, and autonomous navigation. In March 2026, Hyundai
launched the **MobED Alliance** to commercialize the platform for logistics
and service applications. The `etd.hyundai.mobed_transport` skill targets
the MobED (≤ 100 kg payload) rather than the heavier H-Motion AMR.

### Wearable robotics — X-ble family

Beyond the VEX/H-MEX exoskeleton covered by `etd.hyundai.vest_exoskeleton`,
Hyundai's wearable line includes:

- **X-ble Shoulder** — industrial shoulder-unloading exoskeleton for
  overhead work; in March 2026 became the **first wearable robot in South
  Korea to receive KS certification**
- **X-ble MEX** — medical exoskeleton for patients and people with limited
  mobility; targets medical and rehabilitation walking assistance

The `vest_exoskeleton` skill targets VEX/H-MEX. X-ble Shoulder represents
a potential future ETD skill package for shoulder-specific assist tasks.

### Service robots (Hyundai Robotics LAB)

- **ACR (Automatic Charging Robot)** — autonomous EV charging robot shown
  at CES 2026 as part of the autonomous mobility / EV infrastructure ecosystem
- **DAL-e / DAL-e Delivery** — service and delivery robots
- **Safety Inspection** — autonomous inspection robot

These platforms are not covered by current ETD skill packages but represent
natural extension targets.

### Software platform — Edge Brain

In January 2026, Hyundai Motor Group announced **Edge Brain**: proprietary
robotics software developed by Hyundai Robotics LAB in partnership with DEEPX.
Edge Brain targets on-device AI inference for robot platforms. Combined with
Boston Dynamics' **Orbit** (enterprise fleet orchestration, MES/WMS
integration), the Hyundai Motor Group software stack spans:

```
Orbit (fleet orchestration, enterprise APIs) — Boston Dynamics
ETD (skill packages, task context, application layer)
Edge Brain (on-device AI inference) — Hyundai Robotics LAB + DEEPX
OEM control stack (balance, locomotion, safety) — platform-specific
```

ETD targets the application layer between Orbit/MES and the OEM control
stack — this positioning is consistent across all Hyundai Motor Group
platforms.
