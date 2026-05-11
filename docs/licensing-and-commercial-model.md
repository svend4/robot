# Licensing and Commercial Model for ETD Skill Packages

## Purpose

This document describes how ETD skill packages can be distributed as open-source, free, paid, private, or enterprise-licensed modules.

The goal is to separate three layers that are often confused:

1. **Runtime framework** — validator, schemas, adapters, tooling.
2. **Skill package format** — manifest, CHS profiles, capabilities, execution contract.
3. **Skill content** — actual behavior logic, policy, trajectory templates, trained models, datasets, or task recipes.

The first two layers may be open source, while the third layer can be open, free, paid, proprietary, site-specific, or enterprise-only.

---

## 1. What is publicly visible in the Unitree model

Based on public reporting, Unitree's humanoid robot app-store / developer platform is currently described as a public-beta ecosystem with four major areas: User Plaza, Action Library, Dataset hub and Developer Center. Users can connect robots through a mobile app and install cloud-based motion algorithms or action routines; developers and users can upload/share actions and datasets. The early examples mentioned publicly are mostly demonstration and entertainment actions such as Funny Actions, Twist Dance and Bruce Lee-style routines.

Important commercial-status observation:

- Public sources describe **sharing**, **uploading**, **downloading**, **developer rewards**, and **open-source developer resources**.
- Public sources do **not yet show a fully defined paid marketplace model** comparable to Apple App Store with visible prices, commissions, subscriptions, entitlement management, refunds, tax handling and commercial licensing terms.
- Therefore, the safest interpretation is: Unitree's skill-store direction is real, but the commercial model appears to be early / beta / not fully public.

---

## 2. Open-source does not mean every skill is open

A robotics company can have all of these at the same time:

- open-source SDKs;
- open-source simulator tools;
- open-source templates;
- open datasets;
- free downloadable skills;
- proprietary vendor-provided skills;
- commercial third-party skills;
- private customer-specific skills.

For example, an app template repository may be open source, while a polished industrial skill package built on that template may be proprietary.

In ETD terms:

```text
Open-source layer:
- schemas
- validator
- package template
- demo packages
- adapters
- simulator examples

Commercial layer:
- certified industrial packages
- trained policies
- customer-specific CHS profiles
- high-value workflows
- support/SLA
- marketplace analytics
```

---

## 3. Recommended ETD license tiers

## 3.1 Open-source packages

Use when the goal is community adoption and research.

Recommended for:

- package templates;
- examples;
- schemas;
- validators;
- simulation demos;
- educational skill packages.

Possible licenses:

- MIT
- BSD-3-Clause
- Apache-2.0

Advantages:

- easy adoption;
- easy developer onboarding;
- easier academic collaboration;
- transparent safety review.

Disadvantages:

- weak monetization;
- competitors can copy implementation;
- limited IP defensibility.

---

## 3.2 Free but proprietary packages

Use when a vendor wants adoption without revealing implementation.

Recommended for:

- basic customer demos;
- free starter skills;
- robot onboarding packages;
- showcase motions.

Properties:

- free download;
- no source code access;
- signed package;
- limited redistribution;
- tied to marketplace terms.

---

## 3.3 Paid commercial packages

Use when a skill has clear industrial value.

Recommended for:

- precision assembly;
- automotive sequencing;
- inspection;
- machine tending;
- cobot assistance;
- rework workflows.

Possible pricing models:

1. **Per-robot license**
   - one fee per robot seat;
   - good for factory fleets.

2. **Per-site license**
   - one fee per factory or production site;
   - good for enterprise procurement.

3. **Subscription**
   - monthly or annual access;
   - includes updates and support.

4. **Usage-based**
   - per cycle, per task, per runtime hour;
   - harder to implement but attractive for outcome-based robotics.

5. **Support/SLA bundle**
   - software may be cheap or free;
   - revenue comes from integration, tuning, monitoring, support and certification.

---

## 3.4 Private enterprise packages

Use for customer-specific skills that should never be public.

Examples:

- a Hyundai-specific assembly station package;
- a private QA inspection skill;
- proprietary factory sequence logic;
- site-specific safety envelope profiles;
- takt-time optimized workcell routines.

Properties:

- visible only to approved customer account;
- signed by vendor and customer;
- may be tied to station profile IDs;
- cannot be redistributed;
- may include confidential CHS profiles and operational metadata.

---

## 4. How a paid ETD marketplace should work

A commercial ETD marketplace should not simply allow arbitrary downloads. It should follow a controlled lifecycle:

```text
Developer submits package
    ↓
Schema validation
    ↓
Capability validation
    ↓
Safety boundary review
    ↓
Simulation tests
    ↓
Station compatibility declaration
    ↓
Commercial license selection
    ↓
Package signing
    ↓
Marketplace listing
    ↓
Customer entitlement purchase/assignment
    ↓
Runtime install
    ↓
Activation check
    ↓
Telemetry / audit / rollback
```

---

## 5. Marketplace listing fields

Each marketplace item should include:

```json
{
  "skillId": "etd.assembly.precision",
  "version": "0.1.0",
  "publisher": "etd-lab",
  "licenseModel": "commercial_per_robot",
  "priceModel": "subscription",
  "riskLevel": "medium",
  "robotClass": ["humanoid", "fixed_manipulator"],
  "requiredServices": [
    "perception.part_alignment",
    "force_control.contact_feedback",
    "manipulation.arm_control"
  ],
  "safetyReview": "required",
  "sourceAvailable": false,
  "redistributionAllowed": false,
  "supportIncluded": true
}
```

---

## 6. Commercial package states

```text
DRAFT
SUBMITTED
VALIDATED
SAFETY_REVIEW_REQUIRED
APPROVED
PUBLISHED
PURCHASED
INSTALLED
ACTIVE
SUSPENDED
REVOKED
DEPRECATED
```

---

## 7. How developers get paid

Possible models:

1. **Marketplace rewards**
   - early beta model;
   - platform pays selected developers;
   - not necessarily direct customer payment.

2. **Revenue share**
   - customer pays for skill;
   - marketplace keeps commission;
   - developer receives remainder.

3. **Enterprise contract**
   - customer pays vendor/developer directly;
   - marketplace only handles distribution and validation.

4. **Bounty model**
   - factory requests a skill;
   - developers compete or submit;
   - accepted solution is paid.

5. **Certification bounty**
   - developer receives additional payment if package passes industrial validation or pilot KPIs.

---

## 8. Recommended ETD model

For ETD, the most defensible commercial architecture is **open-core + paid industrial skills**.

Open core:

- validator;
- schemas;
- demo packages;
- basic adapters;
- basic simulation.

Commercial packages:

- automotive pick/sequence package;
- precision assembly package;
- inspection package;
- customer-specific station packages;
- certified deployment support.

Why this works:

- community can inspect the package standard;
- industrial customers can trust the validation logic;
- commercial value remains in station-specific CHS profiles, tuned policies, datasets, tests, support and certification.

---

## 9. What should be open and what should be protected

## Recommended open components

- package schema;
- validator;
- simple examples;
- documentation;
- marketplace protocol;
- non-sensitive simulation tools.

## Recommended protected components

- trained policy weights;
- factory-specific CHS profiles;
- production station metadata;
- motion optimization parameters;
- proprietary datasets;
- customer workflows;
- support tooling;
- package signing keys.

---

## 10. Practical conclusion

For the current ETD prototype, the recommended licensing strategy is:

1. Keep the **framework source** open or source-available.
2. Keep demo skills open.
3. Treat industrial skill packages as separately licensable marketplace artifacts.
4. Add package signing and entitlement checks before calling anything production-ready.
5. Never sell a skill as safe unless it has passed runtime validation, simulation tests, station compatibility checks and site acceptance testing.
