# ETD Store Governance and Review Model

## Purpose

This document defines how an ETD Skill Store should review, approve, reject, publish, revoke, and monetize robot skill packages.

## Why robot app stores need stricter governance than phone app stores

A phone app can crash or leak data. A robot skill can move mass, apply force, enter human space, collide with fixtures, or damage products. Therefore review must include software validation and physical-risk validation.

## Store roles

### Publisher

Creates and submits skill packages.

Types:

- ETD core team;
- robot OEM;
- factory integrator;
- third-party developer;
- internal enterprise team.

### Store operator

Runs the marketplace, validates submissions, signs approved packages, handles revocation and distribution.

### Robot owner / fleet operator

Installs packages and defines station-specific approvals.

### Safety reviewer

Reviews medium/high-risk packages.

### Enterprise administrator

Controls licensing, entitlements, rollout, and rollback.

## Review levels

### Level 0 — reference-only

For documentation, schemas, and non-executable examples.

Requirements:

- no robot execution;
- no entitlement;
- no certification.

### Level 1 — low-risk executable

Examples:

- inspection-only;
- non-contact tasks;
- low-speed demo routines.

Requirements:

- schema valid;
- capability safe;
- no forbidden capabilities;
- basic simulation pass;
- signed package.

### Level 2 — medium-risk executable

Examples:

- pick-and-place;
- precision assembly;
- cobot assist;
- station-specific manipulation.

Requirements:

- all Level 1 checks;
- failure scenario tests;
- station compatibility;
- bounded retry policy;
- fallback policy;
- telemetry and audit hooks.

### Level 3 — high-risk executable

Examples:

- heavy payload;
- close human collaboration;
- tool use;
- fast motion;
- multi-robot coordination;
- safety-critical factory line operations.

Requirements:

- all Level 2 checks;
- manual safety review;
- site acceptance test;
- enterprise approval;
- staged rollout;
- automatic rollback thresholds;
- signed certification record.

## Submission package requirements

Every executable package must include:

- `manifest.yaml`;
- `skill.json`;
- `chs_profiles.json`;
- `capabilities.json`;
- `execution_contract.json`;
- `telemetry/events.json`;
- `tests/acceptance_tests.yaml`;
- policy entrypoint;
- license metadata;
- publisher identity;
- package signature for final release.

## Store listing fields

```json
{
  "skillId": "etd.pickplace.basic",
  "version": "0.1.0",
  "family": "pickplace",
  "publisher": "etd-lab",
  "licenseType": "open_source",
  "sourceAvailability": "source_available",
  "pricingModel": "free",
  "riskLevel": "low",
  "reviewLevel": 1,
  "certificationState": "reference_validated",
  "targetUse": "logistics and sequencing",
  "requiresEntitlement": false,
  "packageSignatureRequired": true,
  "stationValidationRequired": true
}
```

## Approval workflow

```text
1. Publisher submits package
2. Store runs schema validation
3. Store runs capability validation
4. Store runs compatibility validation
5. Store checks license metadata
6. Store checks station constraints
7. Store runs simulation tests
8. Store runs failure scenarios
9. Store assigns risk/review level
10. Store signs package if approved
11. Package becomes installable
```

## Monetization governance

Paid packages require:

- license metadata;
- price or contract model;
- refund/update policy;
- support contact;
- allowed robot/fleet/station scope;
- entitlement verification;
- revocation mechanism.

## Revenue models

The store may support:

- free;
- donation/reward;
- one-time purchase;
- subscription;
- enterprise contract;
- per-robot license;
- per-site license;
- per-execution pricing;
- certification fee.

## Revocation workflow

A package can be revoked if:

- a safety issue is found;
- a publisher key is compromised;
- the package violates IP rules;
- a license expires;
- telemetry shows excessive aborts/fallbacks;
- a station incident occurs.

Revocation should trigger:

- disablement on affected robots;
- rollback to last-known-good version;
- notification to fleet operator;
- incident report;
- optional refund/credit process for commercial packages.

## Open-source packages in the store

Open-source packages should still be validated and signed. Open source means the code is visible; it does not mean the package is automatically safe.

## Commercial packages in the store

Commercial packages should still expose all safety-relevant declarations. Commercial secrecy is acceptable for policy code or model weights, but not for manifest, capabilities, execution contract, safety declarations, or telemetry declarations.

## Key rule

The store operator must never approve a package solely because it is popular, paid, or signed. Safety and compatibility checks always come first.
