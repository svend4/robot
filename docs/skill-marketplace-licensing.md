# ETD Skill Marketplace Licensing and Commercial Model

## 1. Purpose

This document explains how ETD skill packages can be distributed in a robot skill marketplace.

It answers four practical questions:

1. Can ETD skills be open source?
2. Can ETD skills be commercial paid products?
3. How should paid skills be protected?
4. How should a marketplace distinguish safe industrial packages from casual motion/demo packages?

The short answer: **all three models are possible**.

ETD packages can be:

- open source;
- free but closed-source;
- commercial paid packages;
- enterprise-only private packages;
- OEM-certified packages;
- research/demo packages.

The runtime should not assume one business model. It should treat licensing as metadata plus policy enforcement.

---

## 2. Public Unitree comparison

Public reporting on Unitree's humanoid robot app/skill platform describes a system where users and developers can upload, share, download, and use robot action sequences, motion routines, datasets, and prebuilt demonstrations through a smartphone/developer platform.

Publicly described examples include:

- martial arts routines;
- dance routines;
- ballet-like sequences;
- remote-control programs;
- user-shared datasets;
- downloadable action sequences.

Based on the public information reviewed, the strongest confirmed point is:

> Unitree is moving toward a downloadable robot-skill ecosystem.

What is **not clearly confirmed** in the public material reviewed:

- whether all skills are free;
- whether paid commercial sales are already active;
- whether developers receive revenue share;
- whether paid skill packages use DRM;
- whether package code is open-source or closed-source;
- whether industrial safety certification is part of the store workflow.

Therefore, for ETD, the correct approach is to design a marketplace that supports both open and commercial distribution from the start.

---

## 3. Skill package distribution models

## 3.1 Open-source package

An open-source ETD skill package exposes its source code and metadata.

Typical use:

- research;
- education;
- community improvement;
- university labs;
- reference examples;
- non-critical simulation demos.

Example metadata:

```json
{
  "licenseModel": "open_source",
  "license": "Apache-2.0",
  "sourceAvailable": true,
  "commercialUseAllowed": true,
  "redistributionAllowed": true,
  "requiresActivation": false
}
```

Advantages:

- easier peer review;
- easier safety audit;
- easier academic adoption;
- lower trust barrier;
- faster ecosystem growth.

Risks:

- competitors can copy the package;
- monetization is harder;
- support burden may increase;
- unsafe forks may appear.

---

## 3.2 Free closed-source package

A free closed-source package is distributed without payment, but the source code is not visible.

Typical use:

- OEM sample package;
- free teaser/demo;
- proprietary but non-commercial plugin;
- vendor-provided utility skill.

Example metadata:

```json
{
  "licenseModel": "free_closed_source",
  "license": "Freeware-EULA",
  "sourceAvailable": false,
  "commercialUseAllowed": false,
  "redistributionAllowed": false,
  "requiresActivation": false
}
```

Advantages:

- protects internal implementation;
- easy to distribute;
- can build adoption before monetization.

Risks:

- lower transparency;
- harder third-party audit;
- user trust depends on vendor reputation.

---

## 3.3 Commercial paid package

A commercial ETD skill package is sold or licensed for money.

Possible pricing:

- one-time purchase;
- subscription;
- per-robot license;
- per-site license;
- per-fleet license;
- usage-based pricing;
- maintenance/support contract;
- certification/support bundle.

Example metadata:

```json
{
  "licenseModel": "commercial_paid",
  "license": "Commercial-EULA",
  "sourceAvailable": false,
  "commercialUseAllowed": true,
  "redistributionAllowed": false,
  "requiresActivation": true,
  "pricingModel": "per_robot_subscription",
  "supportIncluded": true
}
```

Typical use:

- industrial assembly skill;
- certified inspection package;
- vendor-specific integration adapter;
- automotive station workflow package;
- high-value production skill.

Advantages:

- monetizable;
- supports professional support;
- creates incentives for developers;
- can fund safety validation and certification.

Risks:

- requires license enforcement;
- requires marketplace trust;
- requires liability model;
- may need cyber-security review;
- needs careful protection against unsafe modifications.

---

## 3.4 Enterprise-private package

An enterprise-private skill is not sold publicly. It is developed for a specific customer, factory, robot fleet, or workcell.

Example metadata:

```json
{
  "licenseModel": "enterprise_private",
  "license": "Customer-Specific-License",
  "sourceAvailable": false,
  "commercialUseAllowed": true,
  "redistributionAllowed": false,
  "requiresActivation": true,
  "allowedOrganizations": ["customer-automotive-oem"],
  "allowedSites": ["plant-a", "plant-b"]
}
```

Typical use:

- Hyundai-style automotive plant package;
- confidential assembly flow;
- internal QA routine;
- factory-specific station integration;
- MES/WMS custom connector.

Advantages:

- strongest fit to real production;
- can include customer-specific station data;
- avoids public disclosure of production workflow.

Risks:

- less reusable;
- requires access control;
- requires strict confidentiality;
- customer data must be protected.

---

## 3.5 OEM-certified package

An OEM-certified package is reviewed by the robot manufacturer or platform operator.

Example metadata:

```json
{
  "licenseModel": "oem_certified_commercial",
  "certificationState": "oem_certified",
  "certifiedFor": ["atlas_style_humanoid_v1"],
  "sourceAvailable": false,
  "requiresActivation": true,
  "safetyReviewRequired": true
}
```

Typical use:

- production-grade humanoid skills;
- high-force manipulation;
- human-aware cobot operation;
- safety-sensitive automotive tasks.

Advantages:

- higher trust;
- easier enterprise adoption;
- clearer liability boundary;
- better compatibility guarantees.

Risks:

- slower approval;
- higher certification cost;
- potential platform lock-in.

---

## 4. Protection model for commercial skills

Commercial ETD packages should be protected at multiple layers.

No single mechanism is sufficient. A robust model combines:

1. package signing;
2. license tokens;
3. device/fleet entitlement;
4. encrypted payloads;
5. runtime attestation;
6. capability sandboxing;
7. audit logs;
8. marketplace policy enforcement.

---

## 5. Package signing

Every released package should be cryptographically signed.

Purpose:

- prove publisher identity;
- detect tampering;
- prevent modified unsafe packages;
- support trusted installation.

Suggested metadata:

```json
{
  "signature": {
    "algorithm": "ed25519",
    "publisherKeyId": "etd-lab-prod-001",
    "signatureFile": "package.sig",
    "manifestDigest": "sha256:..."
  }
}
```

Runtime policy:

- unsigned packages may run only in simulation;
- signed packages may run on test robots;
- production robots require trusted publisher keys;
- revoked keys must block installation.

---

## 6. License entitlement

Paid packages should require entitlement checks.

Possible entitlement levels:

- robot entitlement;
- user entitlement;
- organization entitlement;
- site entitlement;
- fleet entitlement;
- time-limited trial entitlement.

Example:

```json
{
  "entitlement": {
    "required": true,
    "scope": "per_robot",
    "licenseServer": "https://license.example.com",
    "offlineGracePeriodHours": 72,
    "allowedRobotIds": ["robot-001", "robot-002"]
  }
}
```

Important: entitlement should block only the application-layer skill, not the robot's safety behavior.

---

## 7. Encrypted package payloads

Commercial packages may ship policy logic, compiled modules, or models in encrypted form.

Use cases:

- protect trained policies;
- protect proprietary station logic;
- protect customer-specific workflow adapters;
- protect datasets and motion templates.

Recommended rule:

- metadata remains readable;
- safety/capability metadata remains readable;
- license and signature metadata remains readable;
- proprietary executable payload may be encrypted.

This lets validators inspect safety-critical metadata even if business logic is protected.

---

## 8. Runtime sandboxing

Commercial protection must not create safety risk.

A protected package should still be sandboxed.

A package cannot request:

- direct servo torque access;
- emergency stop override;
- collision disable;
- joint limit override;
- balance-core override.

A paid package should be held to **higher**, not lower, safety standards.

---

## 9. Marketplace listing fields

A marketplace listing should include at least:

```json
{
  "skillId": "etd.assembly.precision",
  "version": "0.1.0",
  "publisher": "etd-lab",
  "licenseModel": "commercial_paid",
  "pricingModel": "per_robot_subscription",
  "riskLevel": "medium",
  "certificationState": "reference_validated",
  "sourceAvailable": false,
  "requiresActivation": true,
  "supportIncluded": true,
  "refundPolicy": "enterprise_contract",
  "allowedRobotClasses": ["humanoid", "fixed_manipulator"],
  "requiredRuntime": ">=0.1.0"
}
```

---

## 10. Recommended ETD marketplace policy

For ETD, the marketplace should allow multiple license models, but enforce safety uniformly.

Suggested rules:

1. Open-source packages can be listed if they pass schema and capability validation.
2. Commercial packages must be signed.
3. Commercial packages must declare license model and activation requirements.
4. Production deployment requires compatibility level A or B.
5. High-risk packages require manual review.
6. Cobot and human-aware packages require special safety review.
7. Any package requesting forbidden capabilities is blocked.
8. Runtime must preserve audit logs.
9. Marketplace can delist packages with repeated safety failures.
10. Source availability does not bypass safety review.

---

## 11. Practical answer to the business question

### Are Unitree skills open source or commercial?

Based on public reporting reviewed, Unitree publicly emphasizes sharing, downloading, and uploading actions/datasets. It is not clear from the available public material whether the current platform has a full paid commercial marketplace with revenue share, DRM, paid licensing, or enterprise-grade protection.

### Should ETD skills be open source or commercial?

Both options should exist.

Recommended split:

- reference packages: open source;
- basic demo packages: free;
- industrial packages: commercial;
- customer-specific packages: enterprise-private;
- safety-sensitive packages: OEM/platform certified.

### How should commercial ETD skills be protected?

Commercial packages should use:

- signed package manifests;
- license entitlement;
- encrypted proprietary payloads;
- runtime capability sandbox;
- installation validation;
- station compatibility checks;
- audit logs;
- rollback support;
- revocation support.

---

## 12. Strategic positioning

A consumer robot app store can be built around entertainment, actions, dances, gestures, and demonstrations.

An industrial ETD marketplace should be built around:

- validated skill packages;
- station compatibility;
- workcell profiles;
- enterprise rollout;
- safety boundaries;
- telemetry;
- certification status;
- commercial support.

That distinction is important.

ETD should not compete as a casual action library only. Its stronger position is:

> A safety-aware, industrial skill-package framework for humanoid and mobile-manipulator robot platforms.
