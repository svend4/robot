# ETD Skill Economics and Licensing Model

## Purpose

This document explains how ETD skill packages can be distributed as open-source, free proprietary, paid commercial, enterprise-certified, or private OEM packages.

The goal is to support a marketplace model without confusing **distribution model**, **source availability**, **safety certification**, and **commercial licensing**. These are separate dimensions.

## Why this matters

A humanoid robot skill store can follow the smartphone app-store pattern in some ways, but the economics and risk model are different:

- robot skills can cause physical motion;
- wrong motion can damage equipment or injure people;
- useful industrial skills may contain proprietary process knowledge;
- training data and model weights may be more valuable than code;
- per-site certification may be more important than general availability.

## Distribution categories

### 1. Open-source reference package

Example:

- `etd.pickplace.basic`
- `etd.inspect.vision`

Typical license:

- MIT
- Apache-2.0
- BSD-3-Clause

Recommended use:

- schemas;
- validators;
- demo packages;
- educational skill examples;
- non-critical examples for adoption.

Commercial model:

- free;
- monetization through consulting, support, integration, or certification services.

Protection model:

- public source code;
- no secrecy;
- value comes from adoption, ecosystem control, and services.

### 2. Open model / open dataset package

Typical license:

- dataset license;
- research-only license;
- CC BY / CC BY-NC;
- Apache/MIT for code, separate license for weights/data.

Recommended use:

- training demonstrations;
- motion datasets;
- simulation datasets;
- benchmark packages.

Commercial model:

- free research release;
- paid enterprise dataset access;
- paid data-cleaning and validation services.

Protection model:

- dataset provenance;
- watermarking;
- dataset access logs;
- usage restrictions in license.

### 3. Free proprietary package

Source availability:

- closed source;
- free to install;
- package signed by publisher.

Recommended use:

- vendor demos;
- partner previews;
- marketing skills;
- limited-use robot routines.

Commercial model:

- free acquisition;
- monetization via hardware sales, subscriptions, or upgrades.

Protection model:

- package signing;
- robot/fleet entitlement;
- encrypted package payload;
- limited redistribution rights.

### 4. Paid commercial package

Source availability:

- usually closed source;
- may include encrypted model weights;
- may include protected workflow logic.

Typical pricing:

- one-time purchase per robot;
- subscription per robot per month;
- per-site license;
- per-fleet license;
- pay-per-use / per-cycle;
- paid support tier.

Recommended use:

- industrial pick-and-place;
- assembly recipes;
- inspection pipelines;
- line-specific factory automation;
- high-value process skills.

Protection model:

- license server;
- offline license tokens;
- robot serial binding;
- organization entitlement;
- signed package manifest;
- encrypted payload;
- runtime attestation where available;
- revocation list;
- telemetry-based audit.

### 5. Enterprise-certified package

Source availability:

- usually closed source or source-available under NDA;
- may be customized per site.

Commercial model:

- integration project;
- annual license;
- maintenance contract;
- safety validation contract;
- per-workcell certification.

Recommended use:

- automotive assembly;
- human-aware cobot tasks;
- production QA;
- safety-sensitive line operations.

Protection model:

- signed release artifacts;
- locked station profile;
- signed compatibility report;
- acceptance-test record;
- audit logs;
- controlled rollout;
- rollback policy;
- legal service-level agreement.

### 6. Private OEM / factory package

Source availability:

- private;
- may never appear in a public store.

Commercial model:

- internal development;
- OEM integration;
- factory-specific automation.

Recommended use:

- proprietary manufacturing process;
- confidential product handling;
- internal logistics workflows.

Protection model:

- private registry;
- VPN/private cloud deployment;
- organization-only entitlement;
- strict access control;
- audit trail;
- no public marketplace listing.

## Recommended ETD business model

ETD should use an **open-core plus certified marketplace** model.

### Open core

Open-source:

- schemas;
- validator;
- demo runner;
- example packages;
- documentation;
- basic adapters.

Purpose:

- build trust;
- encourage adoption;
- make package format inspectable;
- allow third-party developers to learn.

### Commercial extensions

Commercial:

- certified industrial skills;
- station-specific packages;
- advanced adapters;
- safety review tooling;
- fleet rollout dashboard;
- support contracts;
- data/model validation services.

Purpose:

- generate revenue;
- protect high-value work;
- support industrial deployment.

## Recommended marketplace listing fields

Each store entry should include:

```json
{
  "skillId": "etd.assembly.precision",
  "version": "0.1.0",
  "publisher": "etd-lab",
  "licenseType": "commercial",
  "sourceAvailability": "closed_source",
  "pricingModel": "per_robot_subscription",
  "riskLevel": "medium",
  "certificationState": "station_validated",
  "requiresEntitlement": true,
  "supportsOfflineLicense": true,
  "redistributionAllowed": false,
  "packageSignatureRequired": true,
  "targetUse": "precision insertion and seating"
}
```

## Pricing models

### Free

Good for reference packages and community examples.

### Freemium

Basic package free; advanced CHS profiles or enterprise station support paid.

### Per robot

One license per physical robot.

### Per site

One license for a factory site.

### Per workcell

License bound to station profile, cell type, or line segment.

### Subscription

Monthly or annual license with updates and support.

### Usage-based

Fee per execution, per production cycle, or per successful task.

### Enterprise support

Paid support, integration, validation, and maintenance.

## Revenue sharing

A store operator may use:

- 70/30 platform split;
- 85/15 enterprise split;
- certification fee plus low transaction fee;
- subscription revenue share;
- private contract model for enterprise packages.

## What should remain open

For ETD adoption, these should remain open or source-available:

- package format;
- validation logic;
- capability policy definitions;
- safety boundary definitions;
- reference skill packages;
- documentation.

## What can be commercial

These can be commercial:

- optimized skills;
- line-specific skills;
- trained model weights;
- proprietary CHS profiles;
- motion policies;
- high-quality datasets;
- certified deployment bundles;
- support and maintenance.

## Key recommendation

Do not make everything commercial immediately. The standard must be trusted first. A good path is:

1. Open-source ETD core.
2. Free reference packages.
3. Paid industrial packages.
4. Enterprise-certified private deployments.

This mirrors the best ecosystem pattern: open format, open validator, commercial high-value skills.
