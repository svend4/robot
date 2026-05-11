# Skill Package IP, Licensing, and Protection Model

## Purpose

Robot skill packages can contain commercially sensitive content:

- task-specific policies;
- motion parameters;
- training data references;
- learned model weights;
- station-specific optimizations;
- industrial process know-how.

This document explains how ETD skill packages can be protected while preserving safety, validation, and auditability.

## What needs protection

A robot skill package may include several kinds of intellectual property.

### 1. Source code

Examples:

- `policies/chs_adapter.py`
- primitive selectors;
- scoring functions;
- station-specific logic.

### 2. Motion data

Examples:

- demonstrations;
- trajectory templates;
- gait fragments;
- manipulation sequences.

### 3. Model weights

Examples:

- imitation learning policies;
- reinforcement learning policies;
- VLA / WMA adapters;
- task classifiers.

### 4. Industrial process knowledge

Examples:

- insertion force windows;
- station tolerances;
- part handling strategy;
- recovery behavior;
- takt-time optimization.

## Protection layers

### 1. License metadata

Every package should declare license information.

```json
{
  "licenseClass": "enterprise_private",
  "license": "ETD-Enterprise-Private-1.0",
  "sourceAvailable": false,
  "redistributionAllowed": false,
  "commercialUseAllowed": true
}
```

### 2. Signed packages

Each package archive should be signed.

Purpose:

- prove publisher identity;
- detect tampering;
- prevent unauthorized modification;
- support enterprise audit trails.

Recommended artifacts:

```text
etd.skill.name-1.0.0.zip
etd.skill.name-1.0.0.zip.sig
publisher_certificate.json
checksums.json
```

### 3. Checksum validation

Each file should have a cryptographic hash.

```json
{
  "files": {
    "manifest.yaml": "sha256:...",
    "skill.json": "sha256:...",
    "policies/chs_adapter.py": "sha256:..."
  }
}
```

### 4. License activation

Commercial packages can require license activation before execution.

Activation modes:

- offline license file;
- online license server;
- robot-bound license;
- site-bound license;
- fleet subscription token.

Example:

```json
{
  "licenseActivation": {
    "mode": "robot_bound",
    "robotId": "robot-07",
    "expiresAt": "2027-01-01T00:00:00Z",
    "features": ["execute", "telemetry", "updates"]
  }
}
```

### 5. Runtime sandboxing

Commercial protection must not reduce safety. The runtime should sandbox packages regardless of license.

The package should only access declared capabilities:

- read robot state;
- read perception objects;
- write high-level skill intent;
- emit telemetry.

It must not access:

- servo torque commands;
- emergency stop override;
- collision disable;
- balance core override.

### 6. Encrypted payloads

A package may include encrypted model weights or encrypted motion data.

Recommended rule:

- metadata and safety manifest must stay readable;
- capability policy must stay readable;
- execution contract must stay readable;
- protected payload may be encrypted.

This allows validation before decryption.

### 7. Watermarking

Commercial motion data or model weights can be watermarked.

Purpose:

- trace leaks;
- identify unauthorized redistribution;
- support marketplace enforcement.

### 8. Audit logs

The runtime should log:

- package install;
- validation result;
- license check;
- activation;
- execution start/end;
- fallback events;
- safety events;
- package version used.

## Open-source package protection

Open-source packages still need protection from tampering.

Even if source is public, the installed package should be signed or at least checksum-validated. Otherwise an attacker can modify a public package and distribute a dangerous copy.

## Paid package protection

A paid package should include:

- license metadata;
- signed archive;
- publisher identity;
- activation token;
- robot/site/fleet limits;
- update policy;
- support policy;
- telemetry policy;
- refund/disable policy;
- revocation policy.

## Enterprise package protection

For enterprise customers, packages should be private and site-scoped.

Recommended rules:

- private registry only;
- no public listing;
- installation allowed only for authorized robots;
- station profile restrictions;
- audit log retention;
- package export disabled unless admin-approved.

## Suggested ETD package extension

```json
{
  "ipProtection": {
    "sourceAvailable": false,
    "protectedAssets": ["model_weights", "motion_templates"],
    "signatureRequired": true,
    "checksumRequired": true,
    "licenseActivationRequired": true,
    "watermarking": "recommended",
    "auditLogging": "required"
  }
}
```

## Critical safety rule

A protected or encrypted package must not hide safety-critical requirements from the validator.

The following must remain visible:

- required services;
- requested capabilities;
- forbidden capabilities;
- safety boundaries;
- fallback behavior;
- execution contract;
- package identity;
- version;
- publisher.

## Practical recommendation

For ETD v0.1:

- Keep framework code open.
- Keep example packages open.
- Add metadata for commercial models.
- Do not implement real DRM yet.
- Do implement checksums, signatures, and license fields as schema extensions.
- Keep all validation rules transparent.
