# Skill Package Documentation Template

Use this template when documenting a new ETD skill package.

---

# `<skillId>`

## 1. Summary

- Skill ID:
- Version:
- Family:
- Publisher:
- License class:
- Pricing model:
- Risk level:
- Certification state:

## 2. Purpose

Describe the practical task this skill performs.

## 3. Supported Robots

List supported robot classes:

- humanoid
- mobile manipulator
- fixed manipulator
- dual-arm system

## 4. Required Services

List required services:

- perception.object_pose
- manipulation.arm_control
- workflow.job_context
- safety.zone_monitor

## 5. ETD Mapping

### MVS

Fine contact, wrist, grasp, release.

### SVS

Arm trajectory, approach, insertion path.

### BVS

Body posture, reachability, stability.

### CHS

Task context, station context, product context.

## 6. CHS Profiles

List profiles and when they are used.

## 7. Primitives

List primitive order:

1. approach
2. contact / grasp
3. execute task
4. verify
5. release / retreat

## 8. Inputs

Describe required job context fields.

## 9. Outputs

Describe high-level SkillCommand fields.

## 10. Safety Boundaries

State clearly that the package cannot override:

- emergency stop;
- collision core;
- balance core;
- torque limits;
- human protective stop.

## 11. Failure Modes

Describe expected failures:

- missing required service;
- payload out of range;
- station incompatible;
- human too close;
- target pose invalid;
- low confidence.

## 12. Telemetry

List emitted events and metrics.

## 13. Validation

Attach validation report:

- schema valid;
- semantic checks pass;
- compatibility level;
- simulation result;
- failure scenario result.

## 14. Licensing

Declare:

- license class;
- source availability;
- pricing model;
- entitlement requirement;
- redistribution terms.

## 15. Support and Maintenance

Declare:

- support contact;
- update cadence;
- deprecation policy;
- rollback policy.
