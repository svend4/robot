# ETD IP Protection and Package Security Model

## Purpose

This document explains how robot skill packages can be protected if they are distributed commercially, while preserving safety, auditability, and install-time validation.

The core principle is:

> A skill package may protect its intellectual property, but it must not hide its safety-relevant declarations from the runtime.

## Threat model

A robot skill marketplace must defend against:

1. Unauthorized copying of commercial packages.
2. Unauthorized redistribution.
3. Reverse engineering of proprietary models or policies.
4. Malicious packages requesting dangerous capabilities.
5. Packages that try to bypass safety boundaries.
6. Packages that are safe in one workcell but unsafe in another.
7. Supply-chain substitution of packages.
8. Use of expired or revoked packages.
9. Use on unsupported robot models.
10. Unsafe third-party code introduced through community uploads.

## What can be protected

A commercial package may protect:

- policy code;
- model weights;
- motion primitives;
- CHS optimization logic;
- station-specific recipes;
- proprietary datasets;
- calibrated parameters;
- enterprise workflow logic.

## What must remain visible

The runtime must always be able to inspect:

- `manifest.yaml`;
- `skill.json` metadata;
- declared capabilities;
- forbidden capabilities;
- execution contract;
- telemetry declarations;
- safety declarations;
- station compatibility fields;
- publisher identity;
- package signature;
- license metadata.

## Protection layers

### 1. Package signing

Every release package should be signed.

Purpose:

- prove publisher identity;
- detect tampering;
- support store approval;
- support revocation.

Recommended metadata:

```json
{
  "signature": {
    "algorithm": "ed25519",
    "publisherKeyId": "etd-lab-prod-001",
    "signedAt": "2026-05-11T00:00:00Z",
    "signatureValue": "..."
  }
}
```

### 2. License entitlement

A paid package should require an entitlement.

Entitlement may bind to:

- robot serial number;
- fleet ID;
- organization ID;
- station profile ID;
- license term;
- maximum number of robots;
- maximum number of executions.

Example:

```json
{
  "license": {
    "licenseType": "commercial",
    "entitlementId": "ENT-2026-000482",
    "organizationId": "factory-alpha",
    "allowedRobotClasses": ["humanoid"],
    "allowedStationProfiles": ["assembly_station_a"],
    "expiresAt": "2027-05-11T00:00:00Z"
  }
}
```

### 3. Encrypted payload

The public manifest can remain readable while the proprietary payload is encrypted.

Visible:

- metadata;
- capabilities;
- safety declarations;
- compatibility declarations.

Encrypted:

- model weights;
- proprietary policies;
- station-specific tuning;
- learned motion parameters.

Important limitation:

- encryption protects distribution, not absolute reverse-engineering;
- once code runs on a machine, sophisticated attackers may still inspect memory;
- use encryption as part of a layered protection model, not as the only defense.

### 4. Runtime sandbox

A package should execute in a restricted environment.

Allowed writes:

- `command.skill_intent`;
- `telemetry.events`;
- `telemetry.metrics`.

Forbidden writes:

- servo torque;
- joint limit override;
- collision disable;
- emergency stop override;
- balance core override.

### 5. Capability firewall

The runtime must reject packages that request forbidden capabilities.

This is more important than encryption. A signed package can still be unsafe if it requests unsafe authority.

### 6. Station-bound execution

A skill can be valid generally but unsafe at a specific station.

The store should check:

- allowed station profile;
- payload limits;
- human zone policy;
- required sensors;
- workcell geometry;
- fallback availability.

### 7. Revocation

The marketplace must support revocation of packages.

Reasons:

- safety defect;
- IP violation;
- expired license;
- publisher compromise;
- station incident;
- malicious update.

### 8. Audit logging

Every commercial skill execution should log:

- package ID;
- version;
- publisher;
- license ID;
- robot ID;
- station ID;
- timestamp;
- result;
- fallback count;
- abort reason;
- safety-near events.

### 9. Watermarking

For data and model packages:

- watermark model weights;
- watermark generated trajectories;
- fingerprint datasets;
- embed publisher identity into release metadata.

### 10. Legal layer

Technical protection is not enough. Paid packages also need:

- EULA;
- developer agreement;
- marketplace terms;
- safety disclaimer;
- support terms;
- IP ownership rules;
- export-control checks if applicable;
- liability allocation.

## Open-source vs protected package split

A strong ETD marketplace should separate:

### Open standard layer

- schemas;
- validator;
- package format;
- safety rules;
- reference examples.

### Protected value layer

- trained policies;
- industrial recipes;
- station calibration;
- line-specific motion tuning;
- QA logic;
- enterprise connectors.

## Recommended install flow for commercial packages

```text
1. Download package metadata
2. Verify store listing
3. Verify package signature
4. Validate manifest and capabilities
5. Check license entitlement
6. Check robot compatibility
7. Check station compatibility
8. Run simulation smoke test
9. Install package
10. Enable only for approved station/robot scope
11. Monitor execution telemetry
12. Revoke or rollback if thresholds fail
```

## Important design rule

Do not hide safety declarations behind encryption. If the runtime cannot inspect safety-relevant fields, the package should not be installable.
