# ETD Documentation Expansion Guide

## Purpose

This document defines how to turn the ETD Robotics Skill Runtime prototype from a technical proof-of-concept into a documented framework that can be understood by four audiences:

1. robotics engineers;
2. enterprise automation teams;
3. marketplace / product stakeholders;
4. investors, grant reviewers, and potential OEM partners.

The framework should be documented as an **application-layer skill packaging and validation system** for robots, not as a replacement for OEM robot firmware, locomotion control, servo loops, collision kernels, emergency stop logic, or certified human-safety functions.

---

## 1. Documentation goals

The documentation should make five points explicit:

1. **What ETD is** — a skill-package and task-abstraction layer above a robot platform.
2. **What ETD is not** — it is not a low-level robot operating system or certified control kernel.
3. **How a package is structured** — manifests, CHS profiles, capabilities, execution contracts, tests.
4. **How a package is validated** — schema checks, semantic checks, capability safety, station compatibility, runtime compatibility.
5. **How a package could be commercialized** — open packages, paid packages, enterprise packages, certified packages, support contracts.

---

## 2. Recommended documentation tree

```text
docs/
├── 00-overview.md
├── 01-architecture.md
├── 02-package-format.md
├── 03-runtime-core.md
├── 04-validator-guide.md
├── 05-skill-authoring-guide.md
├── 06-marketplace-architecture.md
├── 07-commercial-model.md
├── 08-licensing-ip-protection.md
├── 09-safety-and-capability-policy.md
├── 10-station-profiles.md
├── 11-simulation-and-scenarios.md
├── 12-automotive-use-cases.md
├── 13-atlas-integration-notes.md
├── 14-unitree-marketplace-comparison.md
├── 15-productization-notes.md
├── 16-technical-due-diligence-checklist.md
└── 17-roadmap.md
```

The current repository already contains several of these documents. The next step is to normalize naming, connect them with cross-links, and make the flow easier to read.

---

## 3. Core documentation sections

## 3.1 Overview

Explain the core idea in one page:

- robots need installable skills, not only better hardware;
- ETD packages are validated robot skills;
- each skill emits high-level intents, not raw motor commands;
- the runtime checks safety, compatibility, and capability boundaries;
- the marketplace only distributes packages that pass validation.

Suggested headline:

> ETD is a safe application-layer packaging system for robot skills.

---

## 3.2 Architecture

The architecture document should show this stack:

```text
Enterprise / MES / WMS / QA / Fleet Layer
                  ↑
Marketplace + Registry + Release Artifacts
                  ↑
ETD Runtime Core + Validator + Event Bus
                  ↑
ETD Skill Packages
                  ↑
OEM Robot Middleware
                  ↑
Certified Robot Core
```

The important boundary is between **ETD Runtime Core** and **OEM Robot Middleware**. ETD should not bypass OEM safety.

---

## 3.3 Package format

The package-format document should describe every required file:

```text
manifest.yaml
skill.json
chs_profiles.json
capabilities.json
execution_contract.json
telemetry/events.json
tests/acceptance_tests.yaml
policies/...
```

Each file should include:

- purpose;
- required fields;
- example;
- validation rules;
- common mistakes.

---

## 3.4 Skill authoring guide

This is a practical tutorial for developers.

Recommended tutorial path:

1. create a new `examples/etd.myfamily.myskill/` directory;
2. write `manifest.yaml`;
3. define `skill.json`;
4. add `chs_profiles.json`;
5. define allowed capabilities;
6. create the execution contract;
7. add events;
8. write the policy entrypoint;
9. run `python validate_examples.py`;
10. release the package with `scripts/release_package.py`.

---

## 3.5 Marketplace documentation

The marketplace documentation should define:

- package listing model;
- publisher identity;
- price / license model;
- risk level;
- safety validation status;
- supported robot classes;
- supported stations;
- supported runtime versions;
- installation and rollback procedure.

---

## 3.6 Commercial and licensing documentation

This part must distinguish between:

- **open skill** — source visible, free or community-maintained;
- **free closed skill** — free to use but not open-source;
- **paid skill** — one-time purchase or subscription;
- **enterprise skill** — licensed per site, robot, line, or fleet;
- **certified skill** — validated against stricter safety and reliability rules.

---

## 4. Documentation style

The project should use clear, engineering-first documentation:

- avoid vague claims such as “universal robot OS” unless clearly qualified;
- say “application-layer framework” instead of “replacement operating system”;
- separate conceptual ETD language from executable runtime logic;
- mark speculative or future parts as such;
- clearly identify which parts are implemented and which are roadmap items.

---

## 5. Suggested status labels

Every feature should have one status:

| Status | Meaning |
|---|---|
| Implemented | Exists in code and has been smoke-tested |
| Prototype | Exists but is not production-ready |
| Specified | Documented, but not implemented |
| Proposed | Conceptual roadmap item |
| External dependency | Depends on OEM or third-party API |

---

## 6. Recommended documentation additions for v0.2

1. `docs/skill-authoring-guide.md`
2. `docs/runtime-core-guide.md`
3. `docs/validator-reference.md`
4. `docs/marketplace-commercial-model.md`
5. `docs/licensing-ip-protection.md`
6. `docs/safety-case-template.md`
7. `docs/oem-integration-checklist.md`
8. `docs/faq.md`

---

## 7. Documentation principle

The documentation should always preserve one central distinction:

> ETD packages are installable robot skills, but they must remain subordinate to the certified robot core.

That distinction is the difference between a credible industrial framework and an unsafe “download random motion code into a physical machine” model.
