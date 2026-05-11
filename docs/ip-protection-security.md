# IP Protection and Package Security

## Purpose

This document describes how ETD skill packages can be protected when distributed through a skill store or enterprise registry.

The goal is to protect intellectual property while preserving safety, auditability, and runtime control.

---

## 1. Security principle

> A robot skill package may protect proprietary code or model weights, but it must not hide or override safety-critical behavior from the robot runtime.

The ETD runtime must always be able to inspect:

- package identity;
- version;
- publisher;
- requested capabilities;
- forbidden capabilities;
- runtime compatibility;
- safety boundaries;
- timeout limits;
- station constraints;
- telemetry events.

---

## 2. Protection layers

### Layer 1 — Manifest transparency

The manifest must remain readable.

Purpose:

- compatibility check;
- safety review;
- station routing;
- runtime validation;
- customer due diligence.

Protected? No.

---

### Layer 2 — Package integrity

The package should be signed and hashed.

Mechanisms:

- SHA-256 hash manifest;
- package signature;
- publisher certificate;
- immutable version ID.

Example:

```json
{
  "packageDigest": "sha256:...",
  "signatureAlgorithm": "ed25519",
  "publisherKeyId": "etd-lab-key-001",
  "signedAt": "2026-05-11T00:00:00Z"
}
```

Purpose:

- detect tampering;
- confirm publisher identity;
- support marketplace trust.

---

### Layer 3 — Entitlement / license check

Commercial packages should require an entitlement before activation.

Entitlement can be bound to:

- robot ID;
- fleet ID;
- site ID;
- workcell ID;
- customer ID;
- expiry date;
- package version.

Example:

```json
{
  "entitlementId": "ent-2026-00042",
  "skillId": "etd.assembly.precision",
  "allowedRobotIds": ["robot-07", "robot-08"],
  "allowedSiteIds": ["factory-stuttgart-line-a"],
  "expiresAt": "2027-05-11T00:00:00Z"
}
```

---

### Layer 4 — Encrypted proprietary payload

If a package contains proprietary model weights or policy code, those assets can be encrypted.

Visible files:

- `manifest.yaml`
- `skill.json`
- `capabilities.json`
- `execution_contract.json`
- `telemetry/events.json`

Encrypted files:

- `policies/policy_payload.enc`
- `models/weights.enc`
- `datasets/private_reference.enc`

The runtime decrypts only after:

1. signature verification;
2. entitlement validation;
3. compatibility validation;
4. station validation.

---

### Layer 5 — Runtime sandbox

Even a licensed package must execute inside a sandbox.

Sandbox restrictions:

- no direct servo torque access;
- no collision-core override;
- no emergency-stop override;
- no balance-core override;
- no arbitrary network access unless declared;
- no file-system writes outside package workspace;
- bounded execution time;
- audited commands.

---

### Layer 6 — Audit log

Every package activation should be recorded.

Minimum log:

```json
{
  "timestamp": "2026-05-11T12:00:00Z",
  "robotId": "robot-07",
  "skillId": "etd.pickplace.basic",
  "version": "0.1.0",
  "publisher": "etd-lab",
  "stationId": "logistics_cell_a",
  "entitlementId": "ent-2026-00042",
  "validationLevel": "A",
  "result": "activated"
}
```

---

## 3. Open-source vs commercial protection

| Distribution type | Signing | Entitlement | Encryption | Source visible |
|---|---:|---:|---:|---:|
| Open-source | Yes | No | No | Yes |
| Community free | Yes | Optional | Optional | Maybe |
| Commercial closed-source | Yes | Yes | Yes | No |
| Commercial source-available | Yes | Yes | Optional | Contract only |
| Enterprise-private | Yes | Yes | Optional/Yes | Customer-specific |

---

## 4. Package signing proposal

Add these files:

```text
package.sig
package.hashes.json
publisher.cert.json
```

### `package.hashes.json`

```json
{
  "algorithm": "sha256",
  "files": {
    "manifest.yaml": "sha256:...",
    "skill.json": "sha256:...",
    "chs_profiles.json": "sha256:...",
    "capabilities.json": "sha256:...",
    "execution_contract.json": "sha256:..."
  }
}
```

### `publisher.cert.json`

```json
{
  "publisherId": "etd-lab",
  "publisherName": "ETD Lab",
  "publicKeyId": "etd-lab-key-001",
  "trustLevel": "reference",
  "issuedAt": "2026-05-11T00:00:00Z"
}
```

---

## 5. What not to protect with DRM

Do not use DRM to hide:

- safety boundaries;
- requested capabilities;
- force/speed/workspace limits;
- telemetry events;
- failure conditions;
- runtime compatibility;
- acceptance tests.

These must remain inspectable.

---

## 6. IP risks

### Risk 1 — Package copying

Mitigation:

- package signing;
- entitlement binding;
- encrypted payloads;
- publisher audit logs.

### Risk 2 — Model extraction

Mitigation:

- encrypted weights;
- runtime-only decryption;
- watermarking;
- hardware-bound execution.

### Risk 3 — Dataset leakage

Mitigation:

- no raw private factory dataset in public packages;
- dataset hashes instead of dataset files;
- private registry for enterprise packages;
- data license terms.

### Risk 4 — Unsafe modified package

Mitigation:

- signature verification;
- hash manifest;
- validation before activation;
- reject unsigned modified packages.

### Risk 5 — Vendor lock-in

Mitigation:

- open manifest format;
- open schemas;
- portable capability model;
- adapter-based OEM integration.

---

## 7. Practical v0.2 roadmap

Add:

1. `package.hashes.json`
2. `publisher.cert.json`
3. `license.json`
4. `entitlement.example.json`
5. signature verification stub
6. marketplace review status
7. policy: reject unsigned packages in production mode

---

## 8. Bottom line

The correct protection model is not simply "hide everything".

The correct model is:

> Keep safety and compatibility transparent. Protect proprietary policy assets, model weights, and commercial entitlements.

This is especially important in robotics because the skill package controls physical behavior in the real world.
