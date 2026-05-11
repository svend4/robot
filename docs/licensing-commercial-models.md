# Skill Licensing and Commercial Models

## Purpose

This document describes how robot skill packages can be distributed as open-source, free community packages, commercial packages, or private enterprise packages.

The key distinction is:

> The robot core remains controlled and certified by the OEM. Commercialization applies to application-layer skill packages, task policies, datasets, and integration logic.

---

## 1. What public reporting says about Unitree

Public reports describe Unitree's humanoid robot platform as a marketplace-like system where developers and users can upload, share, download, and install robot actions and training datasets.

Important public signals:

- The platform contains an **Action Library** for downloadable motion/action sets.
- Actions can synchronize to a mobile app and appear in an **Applet Library**.
- The platform also contains a dataset/developer component.
- The first public examples are entertainment or demonstration-oriented actions such as dance and martial-arts routines.
- Public reporting does **not** clearly describe a mature paid marketplace or a fixed monetization structure yet.
- Unitree also has a separate open-source ecosystem with SDKs, simulation tools, robot learning repositories, and datasets.

Practical interpretation:

> Unitree's public platform currently looks closer to a beta/community/developer distribution model than to a mature industrial paid app store. Paid monetization may emerge, but public reporting does not yet establish a complete pricing, licensing, or DRM model.

---

## 2. ETD marketplace license types

ETD Skill Store should support multiple distribution models.

### 2.1 Open-source package

The source code and metadata are public.

Typical use:

- research;
- university labs;
- community skills;
- reference packages;
- SDK samples.

Protection:

- license compliance;
- package signing for integrity, not secrecy;
- audit logs;
- safety validation.

Example:

```json
{
  "licenseType": "open_source",
  "sourceAvailability": "public_source",
  "commercialMode": "free",
  "protectionProfile": "signed_integrity_only"
}
```

---

### 2.2 Free community package

The package may be free to install, but source code may or may not be public.

Typical use:

- hobbyist skills;
- demo skills;
- educational packages;
- non-critical actions.

Protection:

- package signing;
- runtime validation;
- optional publisher verification.

---

### 2.3 Commercial closed-source package

The package is sold or licensed. Source code is not public.

Typical use:

- industrial pick/place optimization;
- precision assembly package;
- paid QA inspection policy;
- premium cobot-assist package;
- vertical factory workflow connector.

Protection:

- signed packages;
- encrypted proprietary policy payloads;
- license entitlement;
- robot-bound or site-bound activation;
- audit logs;
- watermarking/fingerprinting.

Example:

```json
{
  "licenseType": "commercial_closed_source",
  "sourceAvailability": "closed_source",
  "commercialMode": "paid_subscription",
  "priceModel": "per_robot_per_year",
  "protectionProfile": "signed_entitled_encrypted_payload"
}
```

---

### 2.4 Commercial source-available package

The customer can inspect source code under contract, but redistribution is restricted.

Typical use:

- enterprise due diligence;
- safety review;
- on-prem industrial deployment;
- regulated customers.

Protection:

- legal license;
- customer-specific access;
- signed package;
- entitlement token;
- no public redistribution.

---

### 2.5 Enterprise-private package

A package created for one plant, one customer, or one robot fleet.

Typical use:

- private automotive line skill;
- proprietary handling procedure;
- custom MES/WMS connector;
- customer-specific QA routine.

Protection:

- site-bound license;
- private registry;
- no public marketplace listing;
- customer-specific signing key;
- audit and rollback controls.

---

## 3. Pricing models

Potential pricing models for ETD skill packages:

| Model | Description | Best for |
|---|---|---|
| Free | No payment | Community/reference skills |
| One-time purchase | Pay once per package | Consumer/demo skills |
| Per-robot subscription | Annual license per robot | Industrial fleets |
| Per-site subscription | License for a factory/site | Automotive plants |
| Per-workcell license | License bound to station/workcell | Precision assembly cells |
| Per-execution fee | Pay per task execution | Cloud marketplace models |
| Support contract | Paid maintenance/support | Enterprise customers |
| Revenue share | Marketplace operator takes percentage | Public app stores |

For industrial robots, the most practical early models are:

1. **Per-site subscription**
2. **Per-robot subscription**
3. **Enterprise-private development + support contract**

---

## 4. Revenue-share model

A commercial ETD skill store could use a revenue-share structure:

```text
Customer payment
  -> marketplace operator fee
  -> payment processing / compliance
  -> developer payout
  -> optional support reserve
```

Example split:

```text
Developer: 70%
Marketplace/runtime operator: 20%
Support/certification reserve: 10%
```

For industrial safety-critical environments, the marketplace operator may need a higher share if it provides:

- validation;
- simulator certification;
- safety review;
- on-site support;
- rollback infrastructure;
- integration with OEM systems.

---

## 5. What can be sold

A "skill" may include several asset classes:

| Asset | Can be open? | Can be commercial? | Notes |
|---|---:|---:|---|
| Manifest metadata | Yes | Usually not secret | Needed for validation |
| CHS profiles | Yes | Sometimes | May contain factory-specific data |
| Policy code | Yes | Yes | Can be open or closed |
| Motion primitives | Yes | Yes | May be proprietary if optimized |
| Model weights | Sometimes | Yes | Often protected/encrypted |
| Training dataset | Sometimes | Yes | May contain sensitive factory data |
| Station profile | No, often private | Yes | Customer-specific |
| Integration adapter | Yes/No | Yes | Depends on OEM/customer APIs |

---

## 6. What should remain open

Even in commercial packages, some information should remain visible to the runtime and customer:

- package identity;
- version;
- publisher;
- required services;
- requested capabilities;
- forbidden capabilities;
- safety boundaries;
- telemetry events;
- known limitations;
- acceptance tests.

This is necessary because a robot skill cannot be treated like an opaque phone app. A robot can damage equipment or injure people if a package behaves incorrectly.

---

## 7. What can be protected

Commercial packages can protect:

- proprietary policy code;
- learned model weights;
- optimized parameter sets;
- task-specific heuristics;
- proprietary datasets;
- proprietary adapter logic;
- enterprise workflow mappings.

Protection should never hide safety-critical behavior from the runtime. The runtime must still be able to enforce:

- capability boundaries;
- timeout limits;
- force/speed/workspace limits;
- station compatibility;
- rollback criteria.

---

## 8. Recommended ETD license fields

Every marketplace entry should include:

```json
{
  "licenseType": "open_source | community_free | commercial_closed_source | commercial_source_available | enterprise_private",
  "sourceAvailability": "public_source | source_available_under_contract | closed_source",
  "commercialMode": "free | paid_one_time | paid_subscription | enterprise_contract",
  "priceModel": "none | per_robot | per_site | per_workcell | per_execution",
  "entitlementRequired": true,
  "protectionProfile": "signed_integrity_only | signed_entitled | signed_entitled_encrypted_payload",
  "redistributionAllowed": false,
  "supportLevel": "community | standard | enterprise"
}
```

---

## 9. Recommendation for this prototype

For `v0.1`, use:

- open-source/reference packages for examples;
- signed-integrity-only profile for packaging;
- no paid billing yet;
- marketplace metadata fields already present;
- commercial model documented but not enforced;
- future roadmap for entitlement and encrypted payloads.

For `v0.2`, add:

- package signatures;
- package hash manifest;
- license metadata validation;
- entitlement stub;
- publisher identity;
- source availability flags;
- private package support.
