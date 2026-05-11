# Robot Skill Marketplace — Open, Free, Paid, and Enterprise Models

## Purpose

This document explains how robot skill packages may be distributed commercially or openly, and how this applies to the ETD proto-framework.

It also distinguishes what is publicly known about Unitree's robot app store from what is a recommended architecture for an ETD-style industrial skill marketplace.

## Public signal from Unitree

Public reporting describes Unitree's humanoid robot app store / developer platform as a hub for uploading, sharing, downloading, and running robot actions or training data. The described components include an Action Library, Dataset area, Developer Center, and synchronization into the user's mobile app / Applet Library.

Current public reports do not establish a complete commercial model for every skill. The available descriptions emphasize sharing, uploading, downloading, beta access, developer participation, and rewards for strong developers. Some sources describe it as an app-store-like platform, but pricing, commissions, refunds, paid licensing, and DRM details are not clearly documented publicly.

Therefore, the safe interpretation is:

- some content may be free or beta/demo content;
- some developer contributions may be shared openly;
- Unitree also maintains separate open-source resources for SDKs, datasets, and models;
- a future paid marketplace is plausible, but the public information does not prove a mature paid-store model for all skills.

## Important distinction: open source vs marketplace content

A robotics company can simultaneously have:

1. open-source SDKs;
2. open-source datasets;
3. free community actions;
4. paid skill packages;
5. enterprise-only packages;
6. private internal packages;
7. OEM-certified packages.

These categories should not be confused.

Open-source SDKs do not mean every marketplace skill is open source. A free download does not mean source code is available. A paid skill does not necessarily mean the skill is encrypted or closed-source. Each package needs its own license metadata.

## Recommended ETD licensing classes

ETD should support multiple distribution types.

### 1. Open-source skill

The package includes source code, schemas, profiles, and tests under an open license.

Recommended fields:

```json
{
  "licenseClass": "open_source",
  "license": "Apache-2.0",
  "sourceAvailable": true,
  "commercialUseAllowed": true,
  "redistributionAllowed": true
}
```

Use cases:

- research;
- education;
- community skill libraries;
- reference packages;
- public benchmarks.

### 2. Free proprietary skill

The package is free to install but not open-source.

```json
{
  "licenseClass": "free_proprietary",
  "license": "ETD-Free-Use",
  "sourceAvailable": false,
  "commercialUseAllowed": true,
  "redistributionAllowed": false
}
```

Use cases:

- OEM demo skills;
- partner onboarding;
- limited beta packages;
- free but controlled industrial templates.

### 3. Paid one-time skill

The user buys a specific version once.

```json
{
  "licenseClass": "paid_one_time",
  "priceModel": "one_time",
  "sourceAvailable": false,
  "redistributionAllowed": false,
  "seatLimit": 1,
  "robotLimit": 1
}
```

Use cases:

- specialized robot motions;
- factory task templates;
- inspection routines;
- warehouse operations.

### 4. Subscription skill

The customer pays for continued access, updates, validation, and support.

```json
{
  "licenseClass": "subscription",
  "priceModel": "monthly_or_annual",
  "includesUpdates": true,
  "includesSupport": true,
  "robotLimit": 10
}
```

Use cases:

- enterprise fleets;
- frequently updated skills;
- compliance-sensitive packages;
- supported industrial workflows.

### 5. Enterprise private skill

The package belongs to one company or one site.

```json
{
  "licenseClass": "enterprise_private",
  "distribution": "private_registry",
  "customerId": "customer_acme_auto",
  "siteRestricted": true,
  "redistributionAllowed": false
}
```

Use cases:

- automotive workcells;
- proprietary assembly sequences;
- private factory know-how;
- customer-specific tuning.

### 6. OEM-certified skill

The package is approved by robot manufacturer or certified integrator.

```json
{
  "licenseClass": "oem_certified",
  "certificationLevel": "application_layer_certified",
  "certifiedFor": ["humanoid_v1", "industrial_arm_v2"],
  "requiresSignedPackage": true
}
```

Use cases:

- safety-sensitive deployments;
- fleet rollout;
- public marketplace listing;
- regulated industries.

## Marketplace revenue models

A robot skill marketplace can support several business models:

### Free community model

Developers publish skills freely. Marketplace value comes from adoption, reputation, and community growth.

### Developer reward model

Developers do not sell directly, but the platform rewards high-quality contributors.

### Paid listing model

Developers set prices. The marketplace takes a commission.

### Subscription library model

Customers subscribe to a full skill library. Developers receive revenue share based on usage, downloads, or rating.

### Enterprise licensing model

Skills are sold to companies per site, per robot, or per fleet.

### Certified integrator model

An integrator creates and maintains custom skill packages for a factory. The customer pays for implementation and support.

## Recommended ETD marketplace model

For ETD, the most realistic model is mixed:

1. open-source reference packages;
2. free demo packages;
3. paid specialist skills;
4. private enterprise packages;
5. OEM/integrator-certified packages.

The ETD framework itself can be open-source while individual skill packages can be open or commercial.

## Marketplace metadata extension

Add this to package metadata:

```json
{
  "commercial": {
    "licenseClass": "paid_one_time",
    "priceModel": "one_time",
    "currency": "USD",
    "price": 199,
    "trialAvailable": true,
    "sourceAvailable": false,
    "redistributionAllowed": false,
    "robotLimit": 1,
    "siteLimit": null,
    "requiresOnlineActivation": true,
    "supportIncluded": false
  }
}
```

## ETD policy

The marketplace must not install a commercial package only because payment succeeded. It must still pass:

- schema validation;
- capability validation;
- station compatibility;
- robot compatibility;
- safety boundary checks;
- signature validation;
- license validation.

Payment is not a safety decision.

## Recommendation for this repo

Use this model:

- ETD core: open-source or source-available.
- Example skill packages: open-source reference packages.
- Future industrial skills: paid, private, or certified depending on customer.
- Validation and marketplace policy: open and auditable.
