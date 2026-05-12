# ETD Documentation Index

All documents are source material — retained as references, drafts, and starting points for further development.
Grouped by topic below.

---

## 1. Architecture & Design

| File | Summary |
|---|---|
| [architecture.md](architecture.md) | Layered architecture: ETD sits above OEM middleware, below enterprise workflow |
| [package-format.md](package-format.md) | Skill package file layout, required files, naming conventions |
| [atlas-integration-notes.md](atlas-integration-notes.md) | Boston Dynamics / Atlas integration boundary — what ETD can and cannot touch |
| [use-cases-automotive.md](use-cases-automotive.md) | Automotive production line use cases: sequencing, assembly, inspection |

---

## 2. Roadmap & Product Direction

| File | Summary |
|---|---|
| [roadmap-v0.2.md](roadmap-v0.2.md) | Immediate next milestones: JSON Schema, signing, simulator cert, REST API |
| [productization-notes.md](productization-notes.md) | Notes on turning the PoC into a shippable product |
| [funding-pitch-outline.md](funding-pitch-outline.md) | Thesis and pitch structure for investor conversations |
| [technical-due-diligence-checklist.md](technical-due-diligence-checklist.md) | Due-diligence checklist for technical reviewers and investors |

---

## 3. Skill Marketplace — Business & Governance

| File | Summary |
|---|---|
| [marketplace-architecture.md](marketplace-architecture.md) | Skill store architecture: index, policy, entitlement, signing |
| [marketplace-commercial-policy.md](marketplace-commercial-policy.md) | Policy rules: what is required/blocked for each license model |
| [marketplace-commercial-model.md](marketplace-commercial-model.md) | Revenue model: open-source core + commercial skill tiers |
| [marketplace-protection-model.md](marketplace-protection-model.md) | Package protection: signing, sandboxing, audit trails |
| [marketplace-submission-and-review.md](marketplace-submission-and-review.md) | Publisher submission flow and review process |
| [store-governance-review-model.md](store-governance-review-model.md) | Governance model for approving, suspending, and revoking packages |
| [skill-store-positioning.md](skill-store-positioning.md) | Competitive positioning vs Unitree, ROS ecosystem, and app stores |

---

## 4. Licensing & IP Protection

| File | Summary |
|---|---|
| [licensing-and-commercialization.md](licensing-and-commercialization.md) | Open-source, free, paid, and enterprise-private licensing models |
| [licensing-and-commercial-model.md](licensing-and-commercial-model.md) | Detailed model: how each tier works, pricing logic |
| [licensing-commercial-models.md](licensing-commercial-models.md) | Side-by-side comparison of licensing approaches |
| [licensing-and-monetization.md](licensing-and-monetization.md) | Monetization strategies for skill publishers |
| [licensing-ip-protection.md](licensing-ip-protection.md) | IP protection mechanisms: source availability, binary-only, entitlement |
| [skill-economics-licensing.md](skill-economics-licensing.md) | Economic model for skill publishers and platform |
| [skill-marketplace-licensing.md](skill-marketplace-licensing.md) | Licensing rules within the marketplace context |
| [skill-marketplace-commercialization.md](skill-marketplace-commercialization.md) | Path from open-source to commercial skill packages |
| [skill-marketplace-commercial-and-licensing.md](skill-marketplace-commercial-and-licensing.md) | Combined view: commercial policy + licensing in one document |
| [ip-protection-and-package-security.md](ip-protection-and-package-security.md) | Technical IP protection: signing, sandboxing, obfuscation |
| [ip-protection-security.md](ip-protection-security.md) | Security model for skill packages in untrusted environments |
| [commercial-skill-protection.md](commercial-skill-protection.md) | Mechanisms for protecting commercial skill packages from copying |
| [commercialization-and-protection.md](commercialization-and-protection.md) | Combined commercialization and protection strategy |
| [skill-package-ip-and-protection.md](skill-package-ip-and-protection.md) | Per-package IP declaration and enforcement |
| [marketplace-commercial-model.md](marketplace-commercial-model.md) | Full commercial model breakdown |

---

## 5. Developer & Publisher Guides

| File | Summary |
|---|---|
| [publisher-developer-guide.md](publisher-developer-guide.md) | How to create, validate, sign, and publish a skill package |
| [skill-package-doc-template.md](skill-package-doc-template.md) | Template for per-skill documentation |
| [documentation-guide.md](documentation-guide.md) | Documentation style guide for ETD packages and specs |
| [documentation-system.md](documentation-system.md) | How the documentation system is structured and maintained |
| [documentation-blueprint.md](documentation-blueprint.md) | Blueprint for expanding thin docs into full technical handbooks |
| [documentation-expansion-guide.md](documentation-expansion-guide.md) | Step-by-step guide for expanding each document into full form |

---

## 6. Competitive Analysis & Positioning

| File | Summary |
|---|---|
| [unitree-skill-marketplace-analysis.md](unitree-skill-marketplace-analysis.md) | Unitree skill store: what is known, gaps, positioning for ETD |
| [unitree-skill-store-business-analysis.md](unitree-skill-store-business-analysis.md) | Business analysis of Unitree's approach vs ETD's approach |
| [unitree-open-vs-commercial-analysis.md](unitree-open-vs-commercial-analysis.md) | Detailed open vs commercial analysis for Unitree context |
| [unitree-open-vs-commercial-notes.md](unitree-open-vs-commercial-notes.md) | Working notes on Unitree open/commercial split |
| [competitive-landscape-unitree.md](competitive-landscape-unitree.md) | Broader competitive landscape including Unitree |

---

## 7. Implementation Status (v0.5.0)

Current prototype state — what is built and runnable:

| Component | Status | Notes |
|---|---|---|
| ETD reference validator | ✓ complete | JSON Schema Draft 2020-12, 4-level A–D compat, `etd_reference_validator.py` |
| CLI (`etd_cli.py`) | ✓ complete | validate, install, stations, info commands; `--station-profile` flag |
| REST API (`api/app.py`) | ✓ complete | FastAPI; `/store/*`, `/store/stations`, `/validate` |
| Skill marketplace | ✓ complete | `marketplace/skill_store.py`, 8-entry index, entitlement gating |
| Signing & release | ✓ complete | `scripts/sign_package.py`, `scripts/release_package.py`, 8 `.zip` artifacts |
| **Skill packages (8 total)** | ✓ all level A | |
| &nbsp; etd.pickplace.basic | ✓ | manipulator pick-and-place |
| &nbsp; etd.assembly.precision | ✓ | force-controlled peg-in-hole |
| &nbsp; etd.inspect.vision | ✓ | camera QA / defect scan |
| &nbsp; etd.cobot.safeassist | ✓ | human-collaborative handover |
| &nbsp; etd.atlas.humanoid_walkfetch | ✓ | Boston Dynamics Atlas walk-and-fetch |
| &nbsp; etd.hyundai.wia_welding | ✓ | Hyundai WIA H-Motion arc-welding |
| &nbsp; etd.hyundai.mobed_transport | ✓ | Hyundai MobED AMR logistics |
| &nbsp; etd.hyundai.vest_exoskeleton | ✓ | Hyundai VEX/H-MEX wearable assist |
| Station profiles (6 total) | ✓ complete | assembly, cobot, weld, mobed, humanoid, exo |
| Orbit event bridge | ✓ complete | severity filter, critical bypass, flush callback |
| Sim modules (5) | ✓ complete | event_replay, state_generator, fake_middleware, failure/scenario runners |
| Visualizer | ✓ complete | ASCII + matplotlib Gantt; all 8 packages |
| Test suite | ✓ 160 tests | validator, API, CLI, marketplace, orbit, station, sim modules |
| Acceptance tests | ✓ 39 scenarios | per-package YAML; `sim/acceptance_runner.py` |

---

## Usage note

Every document in `docs/` is intentionally kept — including versions, drafts, and working notes.
They serve as:
- **reference material** for further development
- **drafts** to be expanded into full specifications
- **inspiration** for new features and design decisions
- **decision log** showing how the design evolved

When a document needs expanding, open it and build on what is already there rather than starting from scratch.
