# Atlas / Boston Dynamics Integration Notes

ETD integrates with Boston Dynamics Atlas at the application layer.
ETD sits **above** the OEM real-time control kernel and communicates
through service interfaces — it does not replace, patch, or override
any certified safety, balance, locomotion, or collision subsystem.

> Hyundai context: at HMGMA (Hyundai Motor Group Manufacturing Alabama),
> Atlas is planned for deployment in automotive sequencing tasks by 2028.
> This skill covers the application-layer intent emission for such tasks.
> The OEM locomotion and balance core remain under Boston Dynamics /
> Hyundai certified control at all times.

---

## Skill: `etd.atlas.humanoid_walkfetch`

**Family**: humanoid
**Payload**: ≤ 10 kg
**Max reach**: 0.85 m
**Realtime class**: non_safety_critical
**Retry policy**: bounded_retry (max 1)

---

## What ETD controls

| ETD layer | Role |
|---|---|
| CHS | Fetch target, delivery destination, object class, payload class, priority, human handover mode |
| SVS | Arm trajectory — reach, approach curve, obstacle bypass, carry stabilisation |
| MVS | Wrist pose, grasp force, contact stability, object handover compliance |
| BVS | Gait plan, centre-of-mass margin, reachability during walk, balance during carry, stance at target |

---

## What ETD cannot override

- Emergency stop
- Collision core
- Locomotion balance core
- Certified torque limits
- Human protective stop

---

## Primitive sequence

```
localize_target
  → plan_walk_path
    → walk_to_target
      → stabilize_stance
        → approach_object
          → grasp_object
            → secure_carry_posture
              → walk_to_destination
                → deposit_or_handover
```

### Key gate conditions

**`stabilize_stance`**: reads `state.balance_state`. If `stable = False` or
`com_margin < threshold`, the skill aborts with `unstable_stance`. Balance
must be confirmed before arm motion begins — ETD does not command grasping
during active gait.

**`plan_walk_path`**: reads `perception.scene_map`. If `map_ready = False`,
the skill aborts with `scene_not_ready`. Walk planning is delegated entirely
to the OEM locomotion stack (`locomotion.walk_planner`); ETD only confirms
the map is available before requesting a walk.

**`grasp_object`**: reads `perception.object_pose`. If
`confidence < graspConfidenceMin` (default 0.85 for `sequencing_carry`,
0.92 for `precision_pick`), the skill aborts with
`grasp_confidence_below_threshold`. This gate prevents blind grasping.

**`deposit_or_handover`**: driven by `deliveryMode` in the CHS profile:

- `deposit` — robot places object in bin; publishes `delivery.deposited`
- `handover` — robot waits for human ready signal (`human_ready_signal = True`
  on `state.safety_state`) up to `humanReadyTimeoutSec` (default 15 s). If
  timeout elapses without confirmation, `handover_accepted = False` and the
  skill aborts with `handover_timeout`. If the human accepts, publishes
  `handover.accepted`.

---

## CHS profiles

| Profile | `deliveryMode` | `graspConfidenceMin` | Max payload |
|---|---|---|---|
| `sequencing_carry` | `deposit` | 0.85 | 5 kg |
| `precision_pick` | `deposit` | 0.92 | 3 kg |
| `human_handover` | `handover` | 0.85 | 5 kg |

---

## Required services

`perception.object_pose`, `perception.scene_map`,
`manipulation.arm_control`, `locomotion.walk_planner`,
`workflow.job_context`, `state.robot_pose`, `state.arm_state`,
`state.wrist_state`, `state.safety_state`, `state.balance_state`,
`safety.zone_monitor`, `safety.human_detector`

---

## Key telemetry events

`locomotion.walking_started`, `locomotion.target_reached`,
`grasp.contact_detected`, `grasp.object_secured`, `carry.balanced`,
`delivery.deposited`, `handover.offered`, `handover.accepted`,
`fallback.triggered`

---

## Integration boundary

ETD publishes `command.skill_intent` with `primitive`, `body_mode`,
`arm_mode`, `wrist_mode`, `force_window_n`, and `timestamp`. The OEM Atlas
controller converts these into joint-space commands and executes them within
its own safety envelope.

ETD reads `state.balance_state` and `state.robot_pose` for confirmation and
telemetry — it does not compute gait or balance corrections itself. If
`balance_state.stable = False` is observed mid-primitive, the skill aborts
and yields control back to the OEM balance recovery system.

---

## Safety model

Every primitive begins with a `state.safety_state` read. If
`human_in_forbidden_zone = True` at any primitive boundary, the skill
publishes `skill.aborted` and returns immediately without issuing further
intent commands. The OEM stack's human protective stop remains active
independently of this check.

The fallback is `etd.safe_stop_and_retreat` / `safe_hold_or_abort` — Atlas
comes to a controlled stop and holds its current posture while the OEM
safety kernel handles the alert.
