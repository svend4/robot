# Marketplace Protection Model

## Purpose

This document defines a concrete protection model for ETD skill packages in a marketplace environment.

The goal is not to make reverse engineering impossible. The goal is to make unauthorized modification, unsafe execution, unlicensed deployment, and untrusted publication difficult enough that the marketplace can support professional and enterprise use.

---

## Threat model

### Threat 1: Tampered package

Someone modifies a package after publication.

Controls:

- package hash
- manifest hash
- publisher signature
- runtime signature verification
- immutable release versions

### Threat 2: Unsafe package

A package requests dangerous robot capabilities.

Controls:

- capability policy validation
- forbidden capability list
- execution contract validation
- runtime sandbox
- station profile compatibility check

### Threat 3: Unlicensed package execution

A paid skill is copied to another robot or another customer site.

Controls:

- activation token
- robot ID binding
- station ID binding
- account binding
- offline grace period
- audit logging

### Threat 4: IP theft

A commercial skill is reverse engineered.

Controls:

- compiled policy modules
- encrypted model weights
- source escrow instead of source distribution
- remote policy components where latency allows
- legal license terms

### Threat 5: Malicious marketplace publisher

A third party uploads a skill that passes superficial checks but behaves dangerously.

Controls:

- publisher identity verification
- risk-tiered review
- simulation tests
- failure scenario tests
- staged rollout
- telemetry anomaly detection
- kill switch / package revocation

---

## Protection stack

```text
Marketplace layer
  - publisher verification
  - skill listing metadata
  - license metadata
  - package hash
  - package signature

Runtime layer
  - schema validation
  - semantic validation
  - compatibility validation
  - capability sandbox
  - station profile check
  - license token check

Execution layer
  - bounded high-level commands only
  - no servo torque writes
  - no collision disable
  - no emergency stop override
  - timeout and fallback

Fleet layer
  - staged rollout
  - telemetry monitoring
  - rollback
  - revocation
  - audit logs
```

---

## Package signing flow

1. Publisher builds a package.
2. Validator confirms schema and semantic correctness.
3. Release script computes package hash.
4. Publisher signs the package hash.
5. Marketplace stores package metadata and signature.
6. Runtime verifies hash and signature before install.
7. Runtime re-validates package before activation.

Suggested metadata:

```json
{
  "signature": {
    "algorithm": "ed25519",
    "publisherKeyId": "publisher-etd-lab-001",
    "packageHash": "sha256:...",
    "signatureValue": "..."
  }
}
```

---

## License token flow

1. Customer buys or receives license.
2. Marketplace issues license entitlement.
3. Robot runtime requests activation.
4. License service returns signed token.
5. Runtime stores token locally.
6. Package executes only if token is valid.

Suggested token claims:

```json
{
  "skillId": "etd.assembly.precision",
  "version": "0.1.0",
  "customerId": "customer-a",
  "robotIds": ["robot-07", "robot-08"],
  "stationProfiles": ["assembly_station_a"],
  "expiresAt": "2027-01-01T00:00:00Z",
  "offlineGracePeriodHours": 72
}
```

---

## Runtime enforcement rules

A package must be rejected if:

- signature is invalid;
- package hash does not match marketplace index;
- required services are missing;
- robot class is incompatible;
- package requests forbidden capability;
- execution contract requests unsafe command type;
- station profile does not allow the skill family;
- license token is missing or expired;
- package has been revoked.

---

## Commercial protection limits

Important limitations:

- Python code can be copied if fully distributed in source form.
- Obfuscation is not a security boundary.
- Encrypted model weights must be decrypted for execution somewhere.
- Remote policy execution may create latency, reliability, and data-security concerns.
- A determined attacker with hardware access may still extract artifacts.

Therefore, protection should be a combination of:

- technical controls;
- marketplace controls;
- licensing contracts;
- customer audit logs;
- support value;
- regular updates;
- certification value.

---

## Best model for ETD

Recommended:

- Open-source ETD runtime, schemas, validator, and examples.
- Commercial license for advanced industrial skill packages.
- Enterprise private packages for customer-specific workflows.
- Optional source escrow for large customers.
- Signed packages and validated release artifacts for every paid skill.

This creates ecosystem trust while preserving monetizable IP.
