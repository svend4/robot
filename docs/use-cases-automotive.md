# Automotive Use Cases

ETD's eight reference skill packages map directly to production tasks in
an automotive assembly plant. Each package targets a specific robot platform
and workcell role.

---

## 1. Pick-and-place — `etd.pickplace.basic`

**Platform**: generic cobot / fixed manipulator
**Station**: `assembly_station_a`, `cobot_zone_a`

Moves parts between conveyor, tray, and assembly fixture. Covers the
full pick-place cycle: arc approach, guarded grasp, lift and stabilise,
transport with sway damping, and controlled release.

**Automotive context**: body-shop panel sequencing, door trim kitting,
engine bay sub-assembly part feeding.

**Profiles**: `small_box` (1.2 kg, standard force window), `fragile_item`
(0.4 kg, soft contact, reduced speed).

---

## 2. Precision assembly — `etd.assembly.precision`

**Platform**: generic cobot / fixed manipulator
**Station**: `assembly_station_a`

Force-controlled insertion for parts that require tight alignment tolerances.
Vision alignment confirms part pose before insertion begins; adaptive force
ramp controls depth; seating force verification confirms full engagement.

**Automotive context**: wiring harness connector insertion, clip and stud
fastening, sensor housing snap-fit, bearing press-fit.

**Profiles**: `peg_in_hole` (0.5 mm precision, 18 mm depth),
`connector_insert` (0.3 mm precision, 12 mm depth).

**Key gate**: alignment confidence must exceed 90–92% (profile-dependent)
before insertion begins. If offset exceeds `precision_mm × 3`, the skill
aborts to avoid forcing a misaligned part.

---

## 3. Vision inspection — `etd.inspect.vision`

**Platform**: generic cobot (camera-mounted) / fixed vision station
**Station**: `assembly_station_a`, `cobot_zone_a`

Camera-based quality inspection: captures a frame, runs defect detection,
classifies the result, and reports pass/fail with confidence score. Supports
a re-inspect retry before final rejection.

**Automotive context**: weld seam quality gate, painted surface defect scan,
fastener torque-angle verification (camera + vision), dimensional check on
machined parts.

**Profiles**: `defect_scan` (0.96 confidence threshold, full-area scan),
`seam_check` (0.94 confidence, seam region only).

---

## 4. Collaborative handover — `etd.cobot.safeassist`

**Platform**: generic cobot with human-awareness
**Station**: `cobot_zone_a`

Presents a tool, part, or assembly to an operator at a safe handover point.
Monitors human proximity and ready signal; confirms handover completion
before releasing. Reduces speed when a human is in the safety radius.

**Automotive context**: delivering fasteners or sub-assemblies to a human
assembler, tool-change handover at a manual torque station, end-of-line
part handoff to quality inspector.

**Profiles**: `safe_handover` (15 N max contact force, 2 s dwell after
contact), `tool_transfer` (8 N max, precision placement).

---

## 5. Humanoid walk-and-fetch — `etd.atlas.humanoid_walkfetch`

**Platform**: Boston Dynamics Atlas (Hyundai Motor Group)
**Station**: `humanoid_hmgma_a`

Full walk-and-fetch mission: localise target in scene map, plan walk path,
walk to target, grasp object, adopt carry posture, walk to destination,
deposit or hand to human. Atlas's balance and locomotion core remain under
OEM control throughout.

**Automotive context**: HMGMA (Hyundai Motor Group Manufacturing Alabama)
sequencing tasks — carrying kitted parts from storage to assembly cell,
fetching tools from a crib, or delivering sub-assemblies between workstations
in a flexible, humanoid-accessible layout.

**Profiles**: `sequencing_carry` (deposit mode, 5 kg max), `precision_pick`
(higher confidence threshold, 3 kg max), `human_handover` (human-ready signal
required, timeout 15 s).

**Planned deployment**: 2028 (HMGMA, per Hyundai AI Robotics Strategy, CES 2026).

---

## 6. Arc welding — `etd.hyundai.wia_welding`

**Platform**: Hyundai WIA H-Motion cobot
**Station**: `weld_station_a`

Vision-guided seam tracking with force-controlled torch positioning and
post-weld inspection. Enforces a 1.5 m arc exclusion zone. Aborts immediately
on zone intrusion or seam loss during traverse.

**Automotive context**: body-in-white MIG/MAG seam welding — rocker panels,
floor pan, A-pillar/B-pillar joints, door frame. Replaces fixed-program
welding with adaptive seam following for mixed-model lines.

**Profiles**: `standard_seam` (6 mm/s travel, 160 A, 150 mm seam),
`short_seam` (5 mm/s, 140 A, 80 mm).

---

## 7. AMR transport — `etd.hyundai.mobed_transport`

**Platform**: Hyundai MobED autonomous mobile robot
**Station**: `mobed_logistics_a`

Point-to-point transport with obstacle avoidance, payload lift/lower, and
human-aware speed adaptation. Handles up to 100 kg at 1.2 m/s (0.4 m/s
near humans).

**Automotive context**: just-in-time parts delivery from supermarket to
assembly cell, kanban replenishment, empty-container return, inter-building
tote transport.

**Profiles**: `standard_carry` (50 kg, 1.2 m/s), `heavy_carry` (100 kg,
0.8 m/s, reduced acceleration).

---

## 8. Exoskeleton assist — `etd.hyundai.vest_exoskeleton`

**Platform**: Hyundai VEX (Vest Exoskeleton) / H-MEX
**Station**: `exo_assembly_a`

Wearable assist for operators in high-load or repetitive tasks. Detects
operator intent, delivers torque assist proportional to load, and adapts
gain as fatigue increases. Monitors ergonomic metrics continuously and
aborts if fatigue threshold is reached.

**Automotive context**: overhead assembly (headliner, ceiling harness,
sunroof mechanism), heavy door hang, underbody fastening — any task where
sustained arm elevation or heavy holding loads cause rapid operator fatigue.

**Modes**: `overhead` (shoulder unloading, reach extension), `lumbar`
(lumbar support torque, back brace actuation). Mode is detected from
operator motion intent via `perception.intent_detector`.

**Profiles**: `overhead_assembly` (120 N max assist, 70% fatigue threshold),
`heavy_carry` (150 N max assist, 60% threshold).

---

## Platform and station mapping

| Skill | Platform | Station profile |
|---|---|---|
| `etd.pickplace.basic` | generic cobot | `assembly_station_a` |
| `etd.assembly.precision` | generic cobot | `assembly_station_a` |
| `etd.inspect.vision` | generic cobot / vision station | `assembly_station_a` |
| `etd.cobot.safeassist` | generic cobot | `cobot_zone_a` |
| `etd.atlas.humanoid_walkfetch` | Boston Dynamics Atlas | `humanoid_hmgma_a` |
| `etd.hyundai.wia_welding` | Hyundai WIA H-Motion | `weld_station_a` |
| `etd.hyundai.mobed_transport` | Hyundai MobED AMR | `mobed_logistics_a` |
| `etd.hyundai.vest_exoskeleton` | Hyundai VEX / H-MEX | `exo_assembly_a` |
