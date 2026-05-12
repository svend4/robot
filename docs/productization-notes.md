# Productization Notes

ETD should be positioned as an **industrial skill authoring, validation, and
integration layer** — not a full robot OS. The value proposition is the
governed package format, the safety-boundary enforcement, and the
vendor-neutral marketplace, not the motion control itself.

---

## Positioning

### What ETD is

- A **skill package standard**: format, schema, entrypoint contract, and
  telemetry conventions that any OEM can adopt.
- A **safety-boundary enforcer**: validates that no skill can override
  emergency stop, collision core, certified torque limits, or human
  protective stop — at schema time, not at runtime.
- A **governed distribution layer**: entitlement, license enforcement,
  station compatibility, and package signing before any skill reaches a
  robot.
- A **middleware-agnostic runtime bridge**: the CHS adapter pattern works
  with ROS 2, proprietary OEM stacks, or simulation — the skill code does
  not change.

### What ETD is not

- Not a robot OS. ETD does not own locomotion, balance, joint control, or
  any real-time subsystem.
- Not an OEM SDK replacement. ETD wraps OEM middleware through a thin
  `read` / `publish` interface — it does not replace it.
- Not a simulation platform. The `sim/` modules are for acceptance testing
  and demos; ETD's value is in production deployment.

---

## Target customers

| Segment | Pain point | ETD value |
|---|---|---|
| Automotive OEMs (Tier 1) | Skills written for one robot don't transfer to another; no governed distribution | Neutral package format + marketplace |
| Robot OEMs | Customers want to run third-party skills; no safe distribution mechanism | Validated, signed package format they can adopt |
| System integrators | Need to certify skill packages before deploying; no standard audit trail | Validation report + signing + acceptance test spec |
| Skill publishers | No marketplace to distribute skills safely to multiple OEM platforms | Publisher portal + entitlement + royalty model |

---

## Key differentiators

1. **Safety-first package format.** The schema enforces the forbidden
   capability list before a skill can be installed. This is not a runtime
   check — it is a structural constraint.

2. **Platform-neutral by design.** The same skill package runs on a generic
   cobot, a Hyundai WIA welding arm, a MobED AMR, an Atlas humanoid, and a
   VEX exoskeleton — with different middleware adapters but identical package
   format and validation rules.

3. **Governed distribution, not open access.** Unlike ROS packages or Python
   wheels, ETD packages require entitlement, station compatibility, and a
   valid signature. Commercial skills cannot be copied and redeployed.

4. **Production telemetry built in.** Every skill emits `skill.started`,
   `skill.completed`, and `skill.aborted` events with structured payloads.
   The telemetry schema is part of the package format — not an afterthought.

---

## Go-to-market path

### Phase 1 — OEM adoption (current)
Publish the open-source reference packages and validator. Attract OEM and
integrator attention via the package format spec and the Atlas/Hyundai
reference implementations.

### Phase 2 — Pilot deployment
Work with one Tier-1 automotive OEM to deploy ETD on a real workcell. Use
the pilot to validate the station compatibility model and the telemetry
pipeline. Produce a case study.

### Phase 3 — Publisher onboarding
Open a publisher submission portal. First cohort of external skill publishers
(vision QA vendors, force-control specialists) submit packages for review.
Charge a listing fee or revenue share on commercial skills.

### Phase 4 — Platform fees
Charge OEMs a platform fee for hosting the marketplace index and providing
the signing infrastructure. Charge publishers a per-install royalty for
commercial skill packages.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| OEMs build proprietary alternatives | Publish the skill package schema as an open standard; ETD becomes the reference implementation |
| Safety liability concerns | ETD validates but does not certify. OEM safety kernels remain responsible for real-time safety; ETD's role is application-layer validation |
| Skill quality on the marketplace | Automated review pipeline + human review for high-risk packages; revocation mechanism for post-deployment issues |
| ROS 2 lock-in | The CHS adapter pattern is ROS-agnostic; the ROS 2 bridge is one of several possible middleware adapters |
