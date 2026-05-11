# Licensing and Monetization for ETD Skill Packages

## Purpose

This document explains how ETD skill packages can be distributed, licensed, sold, and protected.
It also clarifies the difference between:

- open-source robot tooling;
- free community skills;
- commercial skill packages;
- enterprise-licensed industrial packages;
- protected binary/model packages.

The ETD framework should support all of these models.

---

## 1. Current Public Signal from Unitree-Style Robot Skill Stores

Public reporting about Unitree's humanoid robot app-store concept indicates a beta/developer platform where users and developers can upload, share, download, and run robot actions and datasets.
The public information available so far does **not** show a mature, clearly published paid-pricing model for every skill.
Some reporting states that monetization is still unclear and that Unitree has mentioned possible rewards for exceptional developers.

Therefore, Unitree's current model appears to be closer to:

- developer beta;
- shared action library;
- dataset exchange;
- community and ecosystem growth;
- possible future rewards or monetization.

It should not yet be treated as proof of a fully mature paid marketplace with Apple-App-Store-style billing, revenue share, and commercial enforcement.

---

## 2. ETD Distribution Models

ETD packages can use several distribution models.

### 2.1 Open-source package

The package source code, manifest, CHS profiles, and policies are publicly visible.

Recommended for:

- reference packages;
- research;
- university use;
- community testing;
- safety review transparency.

Typical licenses:

- MIT;
- Apache-2.0;
- BSD-3-Clause.

Pros:

- easy adoption;
- easy inspection;
- easier community contributions;
- safer review process.

Cons:

- weak commercial exclusivity;
- competitors can reuse logic;
- model weights and proprietary data may leak if included.

---

### 2.2 Free but closed package

The package is free to install, but source code is not published.

Recommended for:

- vendor demos;
- ecosystem bootstrapping;
- limited-function skills;
- early-stage market adoption.

Pros:

- protects implementation;
- easy for users;
- can promote a platform.

Cons:

- less transparent;
- harder third-party audit;
- less developer trust.

---

### 2.3 Paid commercial package

The package is sold as a commercial application-layer skill.

Possible pricing models:

- one-time purchase;
- subscription per robot;
- subscription per site;
- subscription per station/workcell;
- usage-based fee per execution/cycle;
- annual enterprise license;
- OEM bundle license.

Recommended for:

- industrial skills;
- precision assembly;
- QA/inspection;
- process-specific cobot assistance;
- station-specific automation.

Pros:

- clear revenue model;
- supports professional support;
- can fund validation, QA, and certification.

Cons:

- requires license enforcement;
- requires support process;
- may require liability and warranty terms.

---

### 2.4 Dual-license model

The core is open-source, while industrial extensions are commercial.

Example:

```text
ETD Runtime Core        Apache-2.0
ETD schemas             Apache-2.0
Reference packages      MIT / Apache-2.0
Industrial packages     Commercial License
Marketplace connector   Commercial License
```

This is often the best model for ETD.

Pros:

- public trust in the standard;
- commercial value in advanced packages;
- easier academic and developer adoption.

Cons:

- requires careful boundary between open and commercial modules.

---

### 2.5 Enterprise-only package

The package is licensed directly to a factory, OEM, integrator, or robotics company.

Typical terms:

- fixed site license;
- robot-count limit;
- station-count limit;
- support SLA;
- private deployment;
- private station profiles;
- custom validation tests.

Recommended for:

- automotive factories;
- logistics warehouses;
- sensitive production lines;
- OEM integrations.

---

## 3. What Exactly Is Being Sold?

A robot skill package is not a single simple file. It may contain several IP layers.

### 3.1 Manifest and metadata

Usually not the core IP.

Contains:

- package name;
- version;
- compatibility;
- required services;
- risk level.

### 3.2 Skill logic

Can be valuable IP.

Contains:

- CHS profile selection;
- primitive sequencing;
- fallback logic;
- station-aware decisions.

### 3.3 Motion primitives

Can be valuable IP.

Contains:

- approach patterns;
- insertion patterns;
- contact strategies;
- safe retreat strategies.

### 3.4 Trained models

Often the most valuable IP.

Contains:

- imitation learning models;
- VLA / policy models;
- perception classifiers;
- contact prediction models.

### 3.5 Datasets

Can be separately licensed.

Contains:

- demonstrations;
- motion capture;
- teleoperation data;
- video/sensor data;
- action labels.

### 3.6 Station profiles

May be customer-confidential.

Contains:

- workcell geometry;
- station constraints;
- takt-time requirements;
- safety zones;
- factory-specific workflows.

---

## 4. Suggested ETD License Classes

ETD marketplace entries should declare a license class.

```json
{
  "licenseClass": "open_source",
  "license": "Apache-2.0",
  "pricingModel": "free",
  "sourceAvailability": "public_source"
}
```

Supported classes:

| Class | Meaning |
|---|---|
| `open_source` | Source available under OSI-style license |
| `freeware` | Free to use, source not necessarily open |
| `source_available` | Source visible, but commercial restrictions apply |
| `commercial` | Paid license required |
| `enterprise_private` | Private deployment under contract |
| `research_only` | Non-commercial research use only |
| `dataset_only` | Data package, not executable skill |
| `model_only` | Model package, not full skill package |

---

## 5. Suggested Pricing Fields

Marketplace metadata should include:

```json
{
  "pricing": {
    "pricingModel": "subscription_per_robot",
    "currency": "USD",
    "listPrice": 250,
    "billingPeriod": "monthly",
    "enterpriseQuoteRequired": false
  }
}
```

Supported pricing models:

- `free`
- `one_time_purchase`
- `subscription_per_robot`
- `subscription_per_site`
- `subscription_per_station`
- `usage_based`
- `enterprise_quote`
- `bundled_with_oem`
- `reward_only`

---

## 6. Recommended Default for This Prototype

For the current ETD prototype:

```text
Runtime core:           open-source / Apache-2.0 style
Schemas:                open-source / Apache-2.0 style
Reference examples:     open-source / MIT or Apache-2.0 style
Industrial skills:      commercial or enterprise_private
Marketplace layer:      source-available or commercial
Station profiles:       private/customer-confidential
```

This keeps the standard open while preserving commercial value in industrial packages.
