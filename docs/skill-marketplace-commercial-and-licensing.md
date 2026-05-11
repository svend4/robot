# Skill Marketplace Commercial and Licensing Model

## Purpose

This document explains how a robot skill marketplace can support both open-source and commercial skill packages, and how ETD packages should represent licensing, pricing, ownership, and protection.

It also compares the ETD marketplace concept with the publicly reported Unitree Robotics Developer Platform / humanoid App Store direction.

---

## Current public picture: Unitree-style skill marketplace

Public reporting describes Unitree's humanoid App Store / Developer Platform as a hub where users and developers can upload, share, and download robot actions or skills. The early examples appear to focus on expressive motion demos such as dance, martial arts, and other prepackaged actions for Unitree's G1 platform.

The public information available at this stage suggests four important points:

1. The platform is centered on actions or skills rather than traditional screen applications.
2. Users can obtain actions and then run them through Unitree's mobile app / Applet Library style interface.
3. Developers can upload actions and datasets.
4. Unitree also maintains open-source robotics resources, SDKs, datasets, and learning frameworks outside the app-store layer.

However, public sources do not yet provide a complete, stable commercial policy for every skill. In particular, it is not yet clear from public materials whether all marketplace actions are free, whether some will be paid, what the revenue split is, what exact license terms apply, or what review/security process will govern third-party skill publication.

---

## Open-source vs commercial: the important distinction

A robot ecosystem can contain several different kinds of artifacts:

| Artifact type | Example | Usually open? | Usually paid? |
|---|---|---:|---:|
| SDK | Robot communication library | Often yes | Usually no |
| Simulation package | URDF, Gazebo, MuJoCo, Isaac tools | Often yes | Usually no |
| Dataset | Teleoperation or manipulation data | Sometimes | Sometimes |
| AI model | VLA, WMA, policy model | Sometimes with restrictions | Sometimes |
| Action / skill package | Robot behavior module | Could be either | Could be either |
| Industrial skill | Factory operation package | Rarely fully open | Often paid |
| Certified skill | Safety-reviewed production package | Usually closed/source-available | Usually paid |

The mistake would be to treat “Unitree has open source” as meaning “all app-store skills are open source”. These are different layers.

A company can open-source SDKs and datasets while still selling curated robot skills, certified packages, support contracts, or enterprise marketplace access.

---

## Possible marketplace models

### 1. Free community skills

These are free packages uploaded by users or researchers.

Typical examples:

- dance motion
- demo action
- educational routine
- simple navigation behavior
- simple manipulation demo

Recommended ETD license metadata:

```json
{
  "licenseType": "open-source",
  "licenseId": "Apache-2.0",
  "commercialUseAllowed": true,
  "sourceAvailable": true,
  "redistributionAllowed": true
}
```

Best for:

- community growth
- research
- education
- non-critical experimentation

Risks:

- untested behavior
- unsafe trajectories
- poor compatibility
- unclear ownership of training data

### 2. Source-available but not fully open

The user can inspect the package but cannot freely resell it.

Example:

```json
{
  "licenseType": "source-available",
  "licenseId": "ETD-Source-Available-Research-1.0",
  "commercialUseAllowed": false,
  "sourceAvailable": true,
  "redistributionAllowed": false
}
```

Best for:

- academic pilots
- partner review
- grant-funded demos
- technical due diligence

### 3. Paid commercial skills

The customer pays for the skill package or for the right to run it on a robot fleet.

Pricing options:

- one-time purchase per robot
- subscription per robot per month
- subscription per station/workcell
- per-execution billing
- enterprise site license
- support-and-maintenance contract
- paid certification and validation package

Example license metadata:

```json
{
  "licenseType": "commercial",
  "licenseId": "ETD-Commercial-Skill-1.0",
  "commercialUseAllowed": true,
  "sourceAvailable": false,
  "redistributionAllowed": false,
  "pricingModel": "per_robot_subscription",
  "licenseCheckRequired": true
}
```

Best for:

- factory operations
- warehouse operations
- high-value industrial skills
- support-backed deployments

### 4. Enterprise private packages

A skill is built for one customer and kept in a private marketplace.

Example:

```json
{
  "licenseType": "enterprise-private",
  "customer": "automotive-oem-a",
  "commercialUseAllowed": true,
  "sourceAvailable": "escrow-only",
  "redistributionAllowed": false,
  "deploymentScope": "site-license"
}
```

Best for:

- automotive plants
- confidential station workflows
- proprietary manipulation processes
- customer-specific safety review

### 5. Certified industrial packages

These are not just “apps”. They are packages with validation evidence.

They should include:

- schema validation report
- simulation evidence
- station compatibility report
- failure scenario report
- telemetry report
- known limitations
- safety boundary declaration
- versioned release artifact
- customer acceptance tests

Recommended metadata:

```json
{
  "licenseType": "certified-commercial",
  "certificationStatus": "validated-for-specific-station",
  "stationProfiles": ["assembly_station_a"],
  "runtimeValidationRequired": true,
  "auditTrailRequired": true
}
```

---

## How paid robot skills can be protected

No protection is perfect. The practical approach is layered protection.

### 1. Package signing

Every released skill package should be signed by the publisher.

Purpose:

- prove publisher identity
- detect tampering
- allow runtime to reject unsigned packages

ETD package metadata:

```json
{
  "signature": {
    "algorithm": "ed25519",
    "publisherKeyId": "etd-lab-prod-001",
    "digest": "sha256:...",
    "signatureValue": "..."
  }
}
```

### 2. Hash-based integrity checks

The marketplace index should store package hashes.

```json
{
  "packageHash": "sha256:abc123...",
  "manifestHash": "sha256:def456..."
}
```

Purpose:

- detect corrupted packages
- detect unauthorized modification
- support reproducible releases

### 3. License token / activation server

Commercial packages may require activation before execution.

Model:

- package installs locally
- runtime contacts license server
- server grants a signed token
- token allows execution on approved robot IDs or station IDs

Metadata:

```json
{
  "licenseCheckRequired": true,
  "activationScope": "robot_id_and_station_id",
  "offlineGracePeriodHours": 72
}
```

### 4. Hardware binding

A license may bind execution to:

- robot serial number
- customer account
- station profile
- site ID
- runtime instance ID

Useful for enterprise contracts, but it must not break emergency fallback behavior.

### 5. Capability sandboxing

Even a paid package should not get unlimited control.

Runtime should enforce:

- allowed read capabilities
- allowed write capabilities
- forbidden safety-core capabilities
- command rate limits
- station profile limits
- payload limits

### 6. Encrypted or obfuscated policy payloads

A commercial package may hide part of its policy code or model weights.

Possible approaches:

- encrypted package payload
- encrypted model weights
- compiled extension modules
- obfuscated Python
- remote policy inference

Limitations:

- obfuscation can be reverse engineered
- remote inference adds latency and reliability risk
- encrypted packages still execute somewhere
- safety-critical logic must remain inspectable by runtime or certification process

### 7. Source escrow

For industrial buyers, a good compromise is:

- customer receives binary/runtime package
- source code is stored in escrow
- source can be released under defined business-continuity conditions

### 8. Audit logs and telemetry

A paid/certified skill should emit:

- execution records
- package version
- publisher ID
- robot ID
- station ID
- task ID
- success/failure events
- safety-near events

This supports billing, debugging, warranty, and compliance.

---

## Recommended ETD marketplace license fields

Add to `marketplace/skill_store_index.json`:

```json
{
  "skillId": "etd.assembly.precision",
  "publisher": "etd-lab",
  "version": "0.1.0",
  "license": {
    "type": "commercial",
    "licenseId": "ETD-Commercial-Skill-1.0",
    "sourceAvailable": false,
    "commercialUseAllowed": true,
    "redistributionAllowed": false,
    "licenseCheckRequired": true,
    "pricingModel": "per_robot_subscription"
  },
  "protection": {
    "packageSigningRequired": true,
    "hashVerificationRequired": true,
    "runtimeCapabilitySandboxRequired": true,
    "activationRequired": true
  }
}
```

---

## Recommended pricing models for ETD

### Community package

- Price: free
- License: Apache-2.0 or MIT
- Support: community only
- Use case: demos, research, education

### Research package

- Price: free or low cost
- License: non-commercial
- Support: limited
- Use case: universities, labs, early validation

### Professional package

- Price: per package or per robot
- License: commercial
- Support: email / updates
- Use case: integrators and advanced users

### Enterprise package

- Price: site license or annual contract
- License: enterprise private
- Support: SLA
- Use case: automotive, warehousing, factory deployments

### Certified station package

- Price: high-value deployment package
- License: certified commercial
- Support: commissioning, validation, updates, rollback
- Use case: production station

---

## Suggested ETD license taxonomy

```text
ETD-OPEN-1.0
  Open-source skill package.

ETD-RESEARCH-1.0
  Source-available, non-commercial research use.

ETD-COMMERCIAL-1.0
  Paid commercial runtime license.

ETD-ENTERPRISE-PRIVATE-1.0
  Customer-specific package, not redistributable.

ETD-CERTIFIED-STATION-1.0
  Commercial package validated for a named station profile.
```

---

## What should be open in the ETD project

Recommended open-source components:

- schemas
- reference validator
- example packages
- demo runner
- simulator sandbox
- adapter interfaces
- marketplace index format
- documentation

Recommended commercial/protected components:

- high-value industrial policies
- customer-specific station packages
- trained models
- proprietary action primitives
- production validation datasets
- certified deployment reports
- enterprise support tooling

This hybrid model is common in robotics: open enough to create an ecosystem, protected enough to support commercial deployment.

---

## ETD vs Unitree marketplace positioning

### Unitree-style early marketplace

Public descriptions suggest:

- actions / applets for humanoid robots
- user upload and download
- dataset sharing
- mobile app synchronization
- early focus on expressive actions and demos

### ETD industrial marketplace

ETD should position itself differently:

- validated skill packages
- station compatibility
- capability policy
- risk scoring
- failure scenarios
- release artifacts
- audit trail
- enterprise licensing
- no safety-kernel override

The strongest commercial difference is:

> Unitree-style store demonstrates that robot skills can be distributed like apps. ETD adds the industrial controls needed before such skills can be trusted in factories.

---

## Key answer: are robot skills open-source or commercial?

They can be either.

The correct model is not one universal answer. A real robot skill marketplace should support multiple categories:

1. **Free open-source skills** for education and community development.
2. **Free but closed demo skills** published by the robot manufacturer.
3. **Source-available research skills** for labs and pilots.
4. **Paid commercial skills** for professional users.
5. **Private enterprise skills** built for one customer.
6. **Certified industrial skills** sold with support, validation, and deployment guarantees.

For Unitree specifically, public information shows open-source SDKs, datasets, and models in the wider Unitree ecosystem, and public reporting describes upload/share/download behavior for app-store actions. Public information does not yet establish a full pricing/revenue/protection model for all Unitree App Store skills.

For ETD, the recommended strategy is a hybrid model:

- open-source the runtime, schemas, validator, and simple examples;
- sell or license advanced industrial skill packages;
- protect paid packages with signing, hashes, activation tokens, capability sandboxing, audit logs, and enterprise contracts.
