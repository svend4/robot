# ETD Documentation Guide

## Purpose

This document explains how to turn the ETD Robotics Skill Runtime prototype into a documented engineering project that can be shown to developers, robot OEMs, industrial partners, grant reviewers, and investors.

The project should be documented at four levels:

1. **Concept level** — why installable robot skills matter.
2. **Architecture level** — how ETD Runtime, packages, adapters, and marketplace fit together.
3. **Developer level** — how to create, validate, release, and test an ETD skill package.
4. **Commercial / safety level** — how packages are licensed, protected, reviewed, and deployed.

---

## Recommended documentation structure

```text
docs/
├── architecture.md
├── package-format.md
├── marketplace-architecture.md
├── documentation-guide.md
├── licensing-commercial-models.md
├── ip-protection-security.md
├── unitree-skill-store-business-analysis.md
├── use-cases-automotive.md
├── atlas-integration-notes.md
├── productization-notes.md
├── roadmap-v0.2.md
├── funding-pitch-outline.md
└── technical-due-diligence-checklist.md
```

---

## 1. Concept-level documentation

This part should answer the business and product question:

> Why should robot skills be packaged like apps?

Core points:

- A humanoid robot without a skill library has limited practical use.
- Industrial users do not want to program every task from scratch.
- A skill package can encode task context, constraints, telemetry, and safe execution requirements.
- The robot core remains controlled by the OEM; ETD only works at the application/skill layer.
- Unitree's humanoid app-store announcement validates the direction of downloadable robot actions, but industrial deployment needs stronger validation, safety, and licensing controls.

Recommended document: `docs/productization-notes.md`

---

## 2. Architecture-level documentation

This part should explain the stack:

```text
Enterprise Layer
  MES / WMS / QA / ERP / dashboards

Marketplace Layer
  skill index / license metadata / entitlement / review state

ETD Runtime Layer
  validator / registry / execution engine / event bus / rollout / rollback

ETD Skill Packages
  manifest / skill / CHS profiles / policies / tests

Adapters
  OEM adapter / Orbit-style event bridge / station profile loader

Robot Middleware
  perception / motion service / grasp service / safety zone monitor

Robot Core
  balance / locomotion / collision / emergency stop / torque limits
```

Recommended documents:

- `docs/architecture.md`
- `docs/marketplace-architecture.md`
- `docs/atlas-integration-notes.md`

---

## 3. Developer-level documentation

This part should show exactly how a developer creates a new package.

Minimum developer flow:

```bash
# 1. Create package folder
mkdir -p examples/etd.myfamily.myskill

# 2. Add required files
manifest.yaml
skill.json
chs_profiles.json
capabilities.json
execution_contract.json
telemetry/events.json
tests/acceptance_tests.yaml
policies/adapter.py

# 3. Validate
python etd_reference_validator.py examples/etd.myfamily.myskill

# 4. Run all examples
python validate_examples.py

# 5. Build release artifact
python scripts/release_package.py examples/etd.myfamily.myskill
```

Recommended document: `docs/package-format.md`

---

## 4. Commercial and safety documentation

This part should describe how packages can be open-source, free community packages, or commercial products.

Key topics:

- license type;
- source availability;
- entitlement model;
- package signing;
- hash verification;
- encrypted payloads if needed;
- runtime sandboxing;
- safety review levels;
- audit logs;
- fleet rollout and rollback.

Recommended documents:

- `docs/licensing-commercial-models.md`
- `docs/ip-protection-security.md`
- `docs/technical-due-diligence-checklist.md`

---

## 5. What should be documented for every skill package

Every skill package should include:

| Section | Purpose |
|---|---|
| Overview | What the skill does |
| Target robot class | Humanoid, mobile manipulator, fixed manipulator |
| Target workcell | Logistics, assembly, inspection, cobot zone |
| Required services | Perception, arm control, workflow context, safety monitor |
| CHS profiles | Task modes and task-specific parameters |
| Primitives | Ordered skill steps |
| Capabilities | Read/write/forbidden permissions |
| Safety boundaries | What the skill cannot override |
| Telemetry | Events and metrics emitted |
| Acceptance tests | Expected behavior in normal and failure paths |
| Commercial metadata | Open-source, commercial, enterprise-private, etc. |
| Protection profile | Unsigned, signed, signed+entitlement, signed+encrypted payload |

---

## 6. Documentation maturity levels

### Level 0 — Concept

- Short README
- Architecture diagram
- One example package

### Level 1 — Developer prototype

- Package format docs
- Validator docs
- Example packages
- Simulation runner

### Level 2 — Partner pilot

- Marketplace docs
- Licensing docs
- Safety and due-diligence docs
- Station profiles
- Failure scenarios

### Level 3 — Productization candidate

- API reference
- Security model
- Package-signing spec
- Entitlement model
- Audit logs
- Release certification workflow

---

## 7. Immediate documentation tasks

For the next iteration:

1. Convert `schemas/*.json` into a formal spec section.
2. Add a developer tutorial: build a new skill in 30 minutes.
3. Add a marketplace operator guide.
4. Add a commercial publisher guide.
5. Add a safety review guide.
6. Add a glossary: MVS, SVS, BVS, CHS, skill package, primitive, runtime, adapter, station profile.
