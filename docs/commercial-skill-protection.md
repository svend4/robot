# Commercial Skill Protection

## Purpose

This document explains how paid or enterprise ETD skill packages can be protected without violating the key safety boundary: ETD packages must never override OEM robot safety core, collision core, balance core, torque limits, or emergency-stop behavior.

Protection is about IP, licensing, provenance, and controlled installation. It is not about bypassing safety controls.

---

## 1. Protection Goals

Commercial ETD packages may need to protect:

1. source code;
2. trained models;
3. datasets;
4. motion primitives;
5. customer station profiles;
6. license terms;
7. publisher identity;
8. package integrity.

---

## 2. Package Signing

Every commercial package should be signed.

### Recommended metadata

```json
{
  "signature": {
    "algorithm": "ed25519",
    "publisherId": "publisher.etd-lab",
    "packageHash": "sha256:...",
    "signedAt": "2026-05-11T00:00:00Z"
  }
}
```

### Why it matters

Package signing helps ensure:

- the package has not been modified;
- the publisher is known;
- the runtime can reject untrusted packages;
- the marketplace can enforce version provenance.

---

## 3. License Entitlements

Commercial packages should require a license entitlement before activation.

### Example

```json
{
  "entitlement": {
    "licenseId": "lic_12345",
    "skillId": "etd.assembly.precision.pro",
    "licensedTo": "factory_site_A",
    "robotLimit": 10,
    "stationLimit": 3,
    "expiresAt": "2027-05-11T00:00:00Z"
  }
}
```

### Runtime enforcement

The ETD runtime should check:

- license active;
- package version allowed;
- robot ID allowed;
- station ID allowed;
- site ID allowed;
- expiration date;
- offline grace period.

---

## 4. Hardware / Robot Binding

For industrial deployments, a package can be bound to:

- robot ID;
- robot class;
- station ID;
- site ID;
- customer ID;
- runtime instance ID.

This prevents a paid package from being copied freely across unrelated robots or factories.

Recommended rule:

```text
Commercial package may run only if entitlement matches runtime robot/site/station context.
```

---

## 5. Source Protection

Options:

### 5.1 Open source

No source protection. Trust is created by transparency.

### 5.2 Source-available

Source visible under restrictive terms.

### 5.3 Closed source

Package ships as compiled bytecode, binary module, container image, or protected model bundle.

### 5.4 Split logic

Safety-critical and runtime validation remain local, but proprietary optimization or model inference may be separated into a protected module or enterprise service.

Important: the robot must still have a safe local fallback if the proprietary component is unavailable.

---

## 6. Model Protection

If a package contains trained models, possible protections include:

- encrypted model bundle;
- signed model metadata;
- watermarking;
- model version provenance;
- runtime license check before loading;
- separated model weights from public manifest.

Recommended metadata:

```json
{
  "modelAssets": [
    {
      "name": "alignment_policy_v1",
      "type": "policy_model",
      "protected": true,
      "hash": "sha256:...",
      "licenseRequired": true
    }
  ]
}
```

---

## 7. Dataset Protection

Datasets may be more sensitive than code.

Protection options:

- dataset license terms;
- dataset watermarking;
- access-controlled download;
- customer-private data partition;
- audit logs;
- prohibition against retraining competitors' models.

Dataset packages should be labeled separately from executable skill packages.

---

## 8. Marketplace Approval Flow

Recommended flow for paid/commercial ETD packages:

```text
1. Developer submits package
2. Marketplace validates schemas
3. Runtime validator checks safety and capabilities
4. Simulation tests run
5. Human review if medium/high risk
6. Package is signed
7. Package is listed
8. Buyer installs
9. Runtime checks entitlement
10. Package activates only in allowed robot/station context
```

---

## 9. Protection Levels

| Level | Name | Description |
|---|---|---|
| P0 | Open | Source visible, no license enforcement |
| P1 | Signed | Package integrity checked |
| P2 | Licensed | Activation requires valid license |
| P3 | Bound | License bound to robot/site/station |
| P4 | Protected model | Models are encrypted/signed |
| P5 | Enterprise | Private package, private station profiles, support SLA |

---

## 10. Important Safety Rule

Commercial protection must never be used to hide safety behavior from runtime validation.

Even closed commercial packages must expose enough manifest-level and contract-level information for the runtime to verify:

- required services;
- capabilities;
- forbidden capabilities;
- robot class;
- station compatibility;
- risk level;
- fallback behavior;
- event/telemetry declarations.

If a package cannot be validated, it must not be allowed to run.
