# ETD Documentation Blueprint

## Purpose

This document defines the documentation set needed to move ETD Robotics Skill Runtime from a proof-of-concept repository into a usable framework for robot-skill authors, integrators, safety reviewers, and business stakeholders.

ETD is not a low-level robot operating system. It is an application-layer skill packaging, validation, simulation, marketplace, and deployment framework for robots that already have an OEM control stack.

## Documentation audiences

### 1. Executive / partner audience

Needs to understand:

- what ETD is;
- why robot skills need packaging and validation;
- how ETD relates to Unitree-style and Atlas/Boston-Dynamics-style ecosystems;
- what is open-source, what is commercial, and what is enterprise-certified;
- what risks are controlled by the framework.

Recommended documents:

- `docs/productization-notes.md`
- `docs/funding-pitch-outline.md`
- `docs/skill-economics-licensing.md`
- `docs/use-cases-automotive.md`

### 2. Robot OEM / integrator audience

Needs to understand:

- how ETD sits above the OEM core;
- which commands ETD may emit;
- which commands ETD must never emit;
- how ETD packages are validated;
- how station compatibility is checked;
- how enterprise events are generated.

Recommended documents:

- `docs/architecture.md`
- `docs/atlas-integration-notes.md`
- `docs/package-format.md`
- `docs/ip-protection-and-package-security.md`
- `docs/store-governance-review-model.md`

### 3. Skill developer audience

Needs to understand:

- how to create a skill package;
- how to define `manifest.yaml`;
- how to define `skill.json`;
- how to write CHS profiles;
- how to declare capabilities;
- how to pass validation;
- how to release a package.

Recommended documents:

- `docs/package-format.md`
- `schemas/*.json`
- `examples/*`
- `scripts/release_package.py`

### 4. Safety / compliance audience

Needs to understand:

- which capability requests are blocked;
- how forbidden capabilities are represented;
- how failure scenarios are simulated;
- how marketplace review levels work;
- how package signing, revocation, and rollback should work.

Recommended documents:

- `docs/ip-protection-and-package-security.md`
- `docs/store-governance-review-model.md`
- `sim/failure_scenarios.py`
- `reports/report_summary.md`

## Recommended documentation tree

```text
docs/
├── architecture.md
├── package-format.md
├── documentation-blueprint.md
├── skill-author-guide.md              # planned
├── runtime-api.md                     # planned
├── marketplace-architecture.md
├── skill-economics-licensing.md
├── ip-protection-and-package-security.md
├── store-governance-review-model.md
├── use-cases-automotive.md
├── atlas-integration-notes.md
├── unitree-skill-marketplace-analysis.md
├── competitive-landscape-unitree.md
├── productization-notes.md
├── roadmap-v0.2.md
├── funding-pitch-outline.md
└── technical-due-diligence-checklist.md
```

## Documentation depth levels

### Level 0 — one-page summary

For decision-makers. Explains what ETD is and why it matters.

### Level 1 — architecture overview

For technical managers and robotics integrators. Explains modules, boundaries, and workflows.

### Level 2 — package authoring guide

For developers. Explains how to build a valid skill package.

### Level 3 — validation and safety specification

For safety engineers and platform operators. Explains schema validation, capability validation, compatibility validation, failure scenarios, and rollout/rollback.

### Level 4 — implementation reference

For maintainers. Explains code structure and test harnesses.

## Minimum documentation required before public release

Before a public GitHub release, the repository should contain:

1. `README.md` with quick start.
2. `docs/architecture.md`.
3. `docs/package-format.md`.
4. `docs/skill-economics-licensing.md`.
5. `docs/ip-protection-and-package-security.md`.
6. `docs/store-governance-review-model.md`.
7. `examples/` with at least two valid packages.
8. `schemas/` with machine-readable schemas.
9. `validate_examples.py`.
10. A generated report in `reports/report_summary.md`.

## Documentation principle

Every skill package should be documented as both:

- a **software artifact**; and
- a **physical-risk artifact**.

A downloadable robot skill is not equivalent to a smartphone app. It can move mass, apply force, enter a human workspace, and create liability. Therefore documentation must include safety limits, station assumptions, failure behavior, and rollback rules.
