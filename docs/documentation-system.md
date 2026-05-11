# ETD Documentation System

## Purpose

This document defines how the ETD Robotics Skill Runtime Prototype should be documented so that it can be understood by four different audiences:

1. **Robotics engineers** — need architecture, APIs, validation rules, adapters, runtime boundaries.
2. **Skill developers** — need package format, examples, tests, release process, licensing rules.
3. **Industrial customers** — need use cases, safety boundaries, deployment model, station compatibility.
4. **Investors / partners** — need positioning, commercial model, defensibility, roadmap, risk controls.

The goal is to make the project readable as a serious proto-framework, not only as a code archive.

---

## 1. Recommended documentation map

```text
docs/
├── architecture.md
├── package-format.md
├── documentation-system.md
├── use-cases-automotive.md
├── atlas-integration-notes.md
├── unitree-skill-marketplace-analysis.md
├── marketplace-architecture.md
├── licensing-and-commercial-model.md
├── ip-protection-and-package-security.md
├── productization-notes.md
├── roadmap-v0.2.md
├── funding-pitch-outline.md
└── technical-due-diligence-checklist.md
```

---

## 2. Document types

## 2.1 Architecture document

Should answer:

- What is the ETD runtime?
- What is a skill package?
- What is the boundary between ETD and the OEM robot core?
- What is allowed and forbidden?
- How do adapters, station profiles, marketplace, validation and simulation relate?

Recommended sections:

1. System overview
2. Layer model
3. Runtime components
4. Safety boundary
5. Adapter model
6. Marketplace model
7. Validation flow
8. Simulation flow
9. Known limitations

---

## 2.2 Package format document

Should answer:

- What files must each package contain?
- What is `manifest.yaml`?
- What is `skill.json`?
- What is `chs_profiles.json`?
- What are `capabilities.json` and `execution_contract.json`?
- What does the validator check?

Recommended sections:

1. Required file tree
2. Manifest schema
3. Skill schema
4. CHS profile schema
5. Capability policy
6. Execution contract
7. Telemetry and events
8. Tests
9. Release archive format
10. Versioning

---

## 2.3 Marketplace document

Should answer:

- What is a skill marketplace?
- What is listed in the marketplace index?
- How does a package move from submitted to approved?
- How is risk classified?
- What is the commercial model?
- How are paid and open packages handled differently?

Recommended sections:

1. Marketplace purpose
2. Unitree-style comparison
3. ETD industrial marketplace architecture
4. Package lifecycle
5. Trust and validation
6. Licensing models
7. Paid package flow
8. Customer entitlement flow
9. Revocation and rollback
10. Audit log

---

## 2.4 Integration document

Should answer:

- How does ETD integrate with an OEM robot platform?
- How does ETD integrate with an Orbit-style enterprise layer?
- How does ETD integrate with station profiles?
- What must never be touched?

Recommended sections:

1. OEM boundary
2. Generic OEM adapter
3. Orbit-style event bridge
4. Station profile loader
5. Enterprise event payloads
6. Safety restrictions
7. Deployment assumptions

---

## 2.5 Commercial and licensing document

Should answer:

- Are skill packages open source, free, paid or proprietary?
- How does the marketplace support different licensing models?
- How does a developer get paid?
- How does a customer receive usage rights?
- How are industrial packages protected?

Recommended sections:

1. Public facts from existing robot skill marketplaces
2. Open-source package model
3. Free package model
4. Commercial package model
5. Enterprise private package model
6. License enforcement
7. Package signing
8. IP protection limits
9. Safety review requirements
10. Recommended ETD policy

---

## 3. Per-skill documentation template

Each skill package should contain or link to a dedicated documentation page:

```markdown
# Skill: etd.<family>.<name>

## Purpose

## Supported robots / platform profiles

## Required services

## Optional services

## ETD decomposition
- MVS:
- SVS:
- BVS:
- CHS:

## CHS profiles

## Execution contract

## Safety boundary

## Inputs

## Outputs

## Telemetry events

## Metrics

## Acceptance tests

## Failure cases

## Licensing model

## Version history

## Known limitations
```

---

## 4. Package README template

Every package should include a `README.md` with this structure:

```markdown
# etd.pickplace.basic

## Summary

## Intended use

## Not intended use

## Required services

## CHS profiles

## Safety boundary

## How to validate

## How to release

## License / commercial model

## Known limitations
```

---

## 5. Documentation maturity levels

## Level 0 — Concept

Only a short idea description exists.

## Level 1 — Package documented

Package has README, manifest, skill file, CHS profiles and acceptance tests.

## Level 2 — Runtime documented

Package also has execution contract, capability policy and validator compatibility report.

## Level 3 — Integration documented

Package includes station compatibility, adapter notes and enterprise event mapping.

## Level 4 — Commercial-ready

Package includes license model, pricing tier, signed release archive, support terms and revocation policy.

## Level 5 — Industrial pilot-ready

Package includes safety review notes, site acceptance criteria, deployment checklist, rollback policy and measured KPIs.

---

## 6. Documentation principles

1. **Do not overclaim.** ETD is an application-layer skill framework, not a replacement for OEM robot core software.
2. **Make boundaries explicit.** Every document must say that ETD packages cannot override safety-critical controls.
3. **Keep package files machine-readable.** Documentation should explain package files but not replace schemas.
4. **Document failure modes.** Industrial customers care as much about blocked unsafe behavior as about successful demos.
5. **Separate open-source and commercial layers.** Runtime, templates and examples may be open; industrial skills may be commercial.
6. **Use validation reports as evidence.** A package should not be considered ready without validator output.

---

## 7. What to add next

Recommended next documentation additions:

1. `docs/skill-author-guide.md`
2. `docs/runtime-operator-guide.md`
3. `docs/marketplace-submission-guide.md`
4. `docs/security-review-guide.md`
5. `docs/customer-pilot-checklist.md`
