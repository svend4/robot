# Unitree Skill Store Business Analysis

## Purpose

This document compares public information about Unitree's humanoid robot app-store / developer-platform direction with the ETD Skill Store prototype.

---

## 1. Public picture of Unitree's platform

Public reporting describes Unitree's platform as a humanoid robot app-store-like system that lets users and developers upload, share, download, and install action routines and datasets.

Reported components include:

- User Plaza;
- Action Library;
- Dataset hub;
- Developer Center;
- mobile app synchronization;
- Applet Library;
- ready-to-use routines such as dance or martial-arts demos.

The early public examples appear to be mostly motion/action sequences and datasets rather than full industrial workflow packages.

---

## 2. Open-source or commercial?

The public picture is mixed.

### Open-source signal

Unitree has a visible open-source ecosystem:

- SDKs;
- ROS / ROS2 repositories;
- simulation tools;
- reinforcement learning repositories;
- humanoid manipulation datasets;
- VLA / embodied AI model work;
- app templates.

This indicates that Unitree is intentionally supporting developer participation.

### Commercial marketplace signal

Public reports describe an app-store-style distribution model, but they do not clearly establish mature pricing, paid packages, DRM, or app-store revenue share.

Some reporting says monetization is not yet clear and that top developers may receive rewards. That sounds closer to beta/community contribution than to a mature paid store.

### Proprietary signal

At least some showcased actions, such as advanced martial-arts routines, are described as using proprietary dynamics algorithms and motion-capture data. That suggests the ecosystem may contain both open and proprietary assets.

---

## 3. Likely future commercial models

Even if early Unitree actions are free or community-shared, a mature robot skill store is likely to evolve toward multiple categories:

1. free demo actions;
2. open-source developer samples;
3. paid premium actions;
4. enterprise/private skills;
5. datasets sold or licensed for training;
6. OEM-certified skill bundles;
7. subscription access to skill libraries.

This is similar to the evolution of smartphone app stores, game asset stores, and robotics SDK ecosystems.

---

## 4. ETD differentiation

ETD should not copy a consumer motion app store directly.

The stronger ETD position is:

> ETD Skill Store is an industrial skill-package marketplace with validation, safety boundaries, station compatibility, and runtime entitlement.

Unitree-like store:

```text
Upload action -> user downloads -> action appears in app -> robot performs routine
```

ETD industrial store:

```text
Upload package
  -> schema validation
  -> capability validation
  -> safety review
  -> station compatibility
  -> license/entitlement check
  -> simulation/failure testing
  -> signed release
  -> controlled deployment
  -> telemetry/rollback
```

---

## 5. Why this matters

For entertainment or simple demos, one-click action downloads may be acceptable.

For automotive or industrial humanoids, a skill store must answer:

- Is the package compatible with this robot?
- Is it compatible with this station?
- What capabilities does it request?
- Does it try to override safety?
- What happens if a human enters the zone?
- What happens if payload is too high?
- Can the package be rolled back?
- Who published it?
- Is there an entitlement/license?
- Is the package signed?
- Are proprietary assets protected?

This is where the ETD design is stronger than a simple action library.

---

## 6. Recommended ETD response to Unitree

The ETD project should explicitly position itself as:

1. **Not only an action library** — a full skill package framework.
2. **Not only consumer/hobbyist** — industrial application layer.
3. **Not a replacement for OEM core** — safe layer above robot core.
4. **Not merely open-source or closed-source** — supports both through license metadata.
5. **Not just distribution** — validation, station compatibility, telemetry, rollback.

---

## 7. Product message

Suggested wording:

> Unitree validates the market need for robot skill stores. ETD extends the idea toward industrial robots by adding package schemas, safety guardrails, capability policies, station compatibility, simulation checks, commercial licensing metadata, and rollback-ready deployment.

---

## 8. Research questions to track

Need to monitor:

- Does Unitree publish pricing for App Store skills?
- Are third-party developers paid?
- Are Unitree app packages signed?
- Is there vetting/review?
- Are paid skills source-visible or closed-source?
- How are datasets licensed?
- Can packages be bound to robot serial numbers?
- What safety review is performed before publication?
- Does the platform support industrial workflows or only actions?
