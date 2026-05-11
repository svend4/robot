# ETD Skill Licensing and Commercialization Model

## Purpose

This document explains how ETD robot skill packages can be distributed as open-source, free, commercial, or enterprise-private packages. It also explains how commercial packages can be protected without allowing unsafe control over the robot core.

The document is written for marketplace designers, robotics vendors, enterprise buyers, and developers who may publish ETD skill packages.

---

## 1. Public market context

The humanoid robot industry is moving toward installable skill ecosystems. Public reporting on Unitree's developer platform describes a robot app-store-style system with an Action Library, user sharing, datasets, a developer center, and one-click installation of actions through a mobile app. Public reports also describe early examples such as dance routines and martial arts movements.

However, public information does not yet clearly establish a mature monetization model for Unitree's skill store. Some reporting indicates that developers may receive rewards, and that the early system is closer to sharing or downloading actions than to a fully commercial software marketplace.

Unitree also maintains official open-source resources, SDKs, datasets, simulation tools, and model/tooling pages. That means the public ecosystem appears to be a mixture of open-source infrastructure, shared datasets, demonstration skills, proprietary algorithms, and possible future commercial incentives.

---

## 2. Key distinction: open source vs signed packages

In robotics there are two separate issues that are often confused:

1. **Open-source code**: the source code of a skill package is visible and can be inspected or modified under a license.
2. **Cryptographic keys**: a package may be digitally signed with private keys and verified with public keys, even if the source code is open or closed.

A package can therefore be:

- open-source and signed;
- closed-source and signed;
- free but closed-source;
- commercial and source-available;
- enterprise-private and not publicly listed.

For robots, signed packages are important even for open-source skills, because physical execution requires identity, integrity, and tamper protection.

---

## 3. ETD package distribution classes

## 3.1 Community open-source package

**Example**: `etd.pickplace.basic-community`

Characteristics:

- source code visible;
- license can be MIT, Apache-2.0, BSD, GPL, or custom academic license;
- free distribution;
- community review;
- still must be signed before execution;
- may be used as a reference implementation.

Best for:

- education;
- research;
- demos;
- non-critical skills;
- templates.

Risk:

- quality may vary;
- unsafe forks may appear;
- support is not guaranteed.

Required protection:

- validation;
- signature;
- version pinning;
- risk classification;
- store review.

---

## 3.2 Free binary package

Characteristics:

- no purchase price;
- source code may not be public;
- binary/model files are distributed through the store;
- useful for OEM demo skills or partner demos.

Best for:

- official samples;
- marketing demos;
- starter packages;
- certified demonstration routines.

Protection:

- package signature;
- checksum;
- compatibility check;
- runtime entitlement check if required.

---

## 3.3 Commercial paid package

Characteristics:

- sold for money;
- may be subscription, per-robot, per-site, or per-execution;
- may contain proprietary policy code, models, datasets, or tuned parameters;
- should include support terms and liability boundaries.

Best for:

- industrial workcell skills;
- precision assembly;
- inspection workflows;
- paid service robots;
- premium humanoid skills.

Common pricing models:

| Model | Description | Example |
|---|---|---|
| Per robot | One license per robot | 20 robots on a line |
| Per site | One license per factory/site | One automotive plant |
| Subscription | Monthly or annual fee | Updates and support included |
| Per execution | Metered usage | Inspection or QA skill calls |
| Per skill family | Bundle | Assembly + inspection package |
| Enterprise contract | Negotiated | OEM or Tier-1 supplier deployment |

Protection:

- signed package;
- publisher identity;
- entitlement token;
- license server or offline license file;
- robot/device binding;
- encrypted model weights if needed;
- audit log;
- package watermark;
- immutable release hashes;
- revocation list for compromised packages.

---

## 3.4 Enterprise-private package

Characteristics:

- not listed publicly;
- developed for one company or factory;
- may encode proprietary workcell data, part geometry, station routing, or QA thresholds;
- distributed through a private registry.

Best for:

- automotive factories;
- high-value manufacturing;
- confidential production workflows;
- regulated environments.

Protection:

- private store;
- customer-specific certificate authority;
- strict station allow-list;
- source escrow or binary escrow;
- deployment approval workflow;
- site-level entitlement;
- no external telemetry unless agreed contractually.

---

## 3.5 Dataset or model package

Characteristics:

- not always a skill by itself;
- may provide demonstrations, trajectories, policy weights, calibration data, or station-specific reference data;
- may be open or commercial.

Best for:

- training;
- simulation;
- imitation learning;
- evaluation;
- skill fine-tuning.

Protection:

- data license;
- provenance tracking;
- dataset hash;
- access control;
- redistribution restrictions;
- privacy and factory-data rules.

---

## 4. Recommended ETD marketplace licensing fields

Every marketplace entry should include these fields:

```json
{
  "licenseModel": "open_source | free_binary | commercial | enterprise_private | dataset_license",
  "sourceAvailability": "source_available | binary_only | model_only | dataset_only",
  "pricingModel": "free | subscription | per_robot | per_site | per_execution | enterprise_contract",
  "requiresEntitlement": true,
  "requiresSignature": true,
  "redistributionAllowed": false,
  "commercialUseAllowed": true,
  "supportLevel": "community | standard | premium | enterprise",
  "publisherVerification": "unverified | verified | oem | enterprise_partner"
}
```

---

## 5. Package protection model

## 5.1 Protection goals

A robot skill marketplace must protect:

1. the user from unsafe skills;
2. the robot from malicious commands;
3. the factory from workflow disruption;
4. the developer's intellectual property;
5. the marketplace from untrusted packages;
6. the OEM safety boundary from override attempts.

## 5.2 Required controls

| Control | Purpose |
|---|---|
| Package signature | Confirms publisher and integrity |
| Hash/checksum | Detects tampering |
| Capability policy | Blocks forbidden control access |
| Entitlement check | Confirms right to use paid package |
| Device binding | Limits paid package to allowed robots |
| Station allow-list | Limits use to approved workcells |
| Sandbox execution | Prevents unsafe system access |
| Runtime validation | Checks schema and compatibility |
| Simulation review | Tests common scenarios |
| Audit log | Records install and execution |
| Revocation list | Blocks compromised packages |

---

## 6. Why encryption alone is not enough

Commercial developers often ask for encryption or obfuscation. These are useful, but they do not make a robot skill safe.

For ETD, the priority order should be:

1. safety boundary;
2. capability restriction;
3. package signing;
4. compatibility validation;
5. station validation;
6. entitlement/licensing;
7. encryption/obfuscation for IP protection.

A closed-source commercial package must still be prevented from touching forbidden robot capabilities.

---

## 7. Commercial ETD store flow

Recommended flow for a paid skill:

```text
Developer submits package
    ↓
Schema validation
    ↓
Capability validation
    ↓
Simulation review
    ↓
Station compatibility review
    ↓
Commercial license metadata check
    ↓
Publisher signing
    ↓
Marketplace listing
    ↓
Buyer purchase / entitlement issued
    ↓
Robot downloads signed package
    ↓
Runtime verifies signature + entitlement
    ↓
Skill can be activated only in approved station context
```

---

## 8. Revenue models

Possible revenue splits:

| Model | Marketplace share | Developer share | Notes |
|---|---:|---:|---|
| Community open-source | 0% | 0% | Free distribution |
| Paid app store | 15-30% | 70-85% | Similar to software app stores |
| Enterprise marketplace | Negotiated | Negotiated | Includes support and integration |
| OEM-certified package | OEM-defined | Developer/OEM split | Stronger certification requirements |
| Support subscription | 0-20% | 80-100% | Package may be free, support is paid |

For industrial robotics, support and integration may be more valuable than the package itself.

---

## 9. Recommended ETD policy

For this repository, the default policy should be:

- reference examples: open-source or source-available;
- production industrial skills: commercial or enterprise-private;
- safety-critical controls: not package-controlled;
- datasets: licensed separately;
- model weights: open, commercial, or enterprise-private depending on source;
- every executable package: signed and validated.

---

## 10. Practical answer to the Unitree question

Based on public reporting available at the time of writing:

- the early Unitree store appears to be a beta/developer platform, not a mature paid marketplace;
- public examples emphasize downloadable action routines, applets, datasets, and user/developer sharing;
- some Unitree development resources are openly published as SDKs, datasets, model/tooling resources, and repositories;
- public reporting does not clearly confirm a full paid app-store model with pricing, revenue share, or DRM;
- developer rewards have been mentioned publicly, but that is not the same as a complete commercial marketplace;
- some routines or algorithms may still be proprietary even if surrounding tools are open-source.

For ETD, the better industrial model is mixed:

```text
Open-source reference packages
+ free demonstration packages
+ paid commercial skill packages
+ enterprise-private factory packages
+ licensed datasets and model weights
+ mandatory signatures and safety validation for all executable packages
```

---

## 11. Recommended next implementation tasks

1. Add `licenseModel`, `pricingModel`, and `sourceAvailability` to `skill_store_index.json`.
2. Add `commercialPolicy` to `marketplace_policy.json`.
3. Add package signing placeholder.
4. Add entitlement simulation.
5. Add `marketplace/skill_store.py` for listing, validation, and install simulation.
6. Add `sim/marketplace_demo.py`.

