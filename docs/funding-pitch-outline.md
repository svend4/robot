# Funding Pitch Outline

## Thesis

Robots need a safe, governed application-layer marketplace for validated
skills. ETD provides the package format, validation engine, runtime bridge,
station compatibility model, and distribution infrastructure — the "App Store
layer" for industrial robots, with safety enforcement built into the format
rather than bolted on after the fact.

---

## Problem

Industrial robots are powerful but locked into proprietary skill silos:
- Skills written for one OEM platform cannot run on another
- No standard format for describing what a skill can and cannot do
- No governed distribution mechanism — skills are deployed via ad-hoc scripts
- No safety audit trail between skill authoring and workcell deployment
- Automotive OEMs face this at scale: 50+ robot models, thousands of workcells,
  no interoperability layer

The humanoid wave (Atlas, Unitree, Hyundai Boston Dynamics) makes this worse —
each humanoid has its own SDK, its own skill format, and its own risk surface.

---

## Solution

ETD is a vendor-neutral, safety-first skill package runtime:

1. **Standard package format** — `manifest.yaml`, `skill.json`,
   `chs_profiles.json`, `capabilities.json`, Ed25519-signed `package.sig`
2. **Safety-boundary enforcement** — JSON Schema validation blocks any
   package that requests forbidden capabilities at install time, not at runtime
3. **Station compatibility gating** — installs are blocked if the station
   does not provide the services the skill requires
4. **Governed marketplace** — entitlement, license enforcement, and revocation
   before any skill reaches a robot
5. **Middleware-agnostic bridge** — the same skill runs on ROS 2, proprietary
   OEM stacks, and simulation through a thin adapter interface

---

## Traction (v0.5.0 prototype)

- 8 reference skill packages across 5 robot platforms (generic cobot, Atlas,
  Hyundai WIA welding, Hyundai MobED AMR, Hyundai VEX exoskeleton)
- All 8 packages validate at level A (fully compatible)
- 689 automated tests, branch coverage ≥ 96%
- REST API (`/store/skills`, `/store/install`, `/validate`)
- ROS 2 action server/client bridge (dry-run + mocked)
- Ed25519 signing and release pipeline for all 8 packages
- Acceptance test runner with 39 YAML scenarios per package

---

## Market

**Immediate**: automotive Tier-1 OEMs managing multi-robot workcells.
Hyundai Motor Group alone operates HMGMA (Alabama), Ulsan, and Asan plants
with thousands of robot installations. Boston Dynamics Atlas is planned for
HMGMA sequencing tasks by 2028.

**Adjacent**: electronics, logistics, and aerospace — same problem of
heterogeneous robot fleets needing governed skill distribution.

**Humanoid wave**: by 2028–2030, humanoids will reach production in
automotive plants. ETD is positioned as the neutral integration layer that
prevents vendor lock-in for humanoid skills.

---

## Business model

| Revenue stream | When | Mechanism |
|---|---|---|
| Platform fee | Phase 2 | OEM pays per robot/year for marketplace access |
| Publisher listing fee | Phase 3 | Skill publisher pays to list on marketplace |
| Commercial skill royalty | Phase 3 | % of per-install fee on commercial skills |
| Integration services | Phase 1–2 | Paid integration work for first OEM pilots |
| Enterprise license | Phase 2+ | Site license for private marketplace instance |

Open-source core (validator, package format, reference adapters) drives
adoption. Commercial layers (marketplace infrastructure, signing service,
fleet rollout, dashboard) are the revenue source.

---

## Ask

**Seed round**: to fund:
- ROS 2 bridge completion and first OEM pilot deployment
- Publisher submission portal (web UI + review pipeline)
- Two platform engineers + one robotics integration specialist

**Target OEM partnership**: Hyundai Motor Group (natural fit given Atlas
ownership + VEX/MobED/WIA product lines already covered by reference packages).

---

## Why now

1. Hyundai acquired Boston Dynamics (2021) — one entity now controls multiple
   robot platforms that ETD already integrates
2. HMGMA humanoid deployment announced at CES 2026 — creates immediate demand
   for a governance layer
3. Unitree, Figure, and Agility entering automotive — OEMs need a
   vendor-neutral layer before they get locked in to proprietary skill formats
4. EU AI Act and emerging robot safety regulations create compliance pressure
   — ETD's audit trail and safety schema are early movers on this requirement
