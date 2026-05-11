# ETD Publisher and Developer Guide

## Purpose

This guide explains how a developer, robotics integrator, or company should prepare an ETD skill package for publication in a skill store.

## Package author checklist

Before publishing a package, the author should provide:

- manifest;
- skill definition;
- CHS profiles;
- capability policy;
- execution contract;
- telemetry events;
- acceptance tests;
- station compatibility notes;
- license metadata;
- support contact;
- version number;
- changelog.

## Publication stages

### 1. Draft

The package is local only. It may be incomplete and should not run on a real robot.

### 2. Validated

The package passes schema and semantic validation.

### 3. Simulated

The package passes sandbox scenarios.

### 4. Station-approved

The package is approved for at least one station profile.

### 5. Marketplace-listed

The package is discoverable in a skill store.

### 6. Certified

The package has been reviewed by OEM, integrator, or internal safety team.

## Required metadata for marketplace publication

```json
{
  "publisher": {
    "name": "Example Robotics Lab",
    "type": "developer|integrator|oem|enterprise",
    "contact": "support@example.com",
    "verified": true
  },
  "commercial": {
    "licenseClass": "open_source|free_proprietary|paid_one_time|subscription|enterprise_private|oem_certified",
    "sourceAvailable": true,
    "redistributionAllowed": true,
    "commercialUseAllowed": true
  },
  "support": {
    "supportLevel": "community|standard|enterprise",
    "updatePolicy": "best_effort|versioned|sla",
    "securityContact": "security@example.com"
  }
}
```

## Skill quality levels

### Q0 — Draft

Not suitable for deployment.

### Q1 — Validated package

Schemas and semantic rules pass.

### Q2 — Simulated

Basic successful and failure scenarios pass.

### Q3 — Workcell tested

Tested against a station profile.

### Q4 — Pilot deployed

Used in supervised pilot.

### Q5 — Production certified

Approved for production rollout.

## Publisher obligations

A publisher should not:

- request forbidden capabilities;
- hide safety-critical metadata;
- misrepresent robot compatibility;
- bypass OEM safety systems;
- publish untested industrial packages as production-ready.

A publisher should:

- clearly state limitations;
- provide rollback guidance;
- provide telemetry expectations;
- define failure behavior;
- document required services and sensors.

## Marketplace review checklist

The skill store should verify:

- package identity;
- publisher identity;
- license metadata;
- package signature;
- schema validation;
- capability policy;
- execution contract;
- simulation results;
- station compatibility;
- risk level;
- user-facing description.

## User-facing listing template

```text
Skill name: ETD Pick & Place Basic
Category: Pick & Place
Publisher: ETD Lab
License: Apache-2.0 / Free Reference Package
Robot class: humanoid, mobile manipulator
Risk level: low
Requires: object pose, arm control, job context, safety state
Validated: yes
Station compatibility: logistics cell A
Production certified: no
```

## Pricing disclosure template

For paid packages, disclose:

- price;
- billing model;
- robot limit;
- site limit;
- refund policy;
- support policy;
- update policy;
- source availability;
- telemetry/data usage policy.

## Recommended next schema additions

Add optional schema files:

- `commercial.schema.json`
- `publisher.schema.json`
- `license.schema.json`
- `package_signature.schema.json`
- `marketplace_listing.schema.json`
