# Marketplace Commercial Policy

## Purpose

This document defines a commercial and safety policy for an ETD skill marketplace. It is designed for a robot skill store where packages can be open-source, free, paid, or enterprise-private.

---

## 1. Marketplace principles

1. A skill may be free or paid, but every executable skill must be validated.
2. A package may be open-source or closed-source, but every executable package must be signed.
3. Commercial protection must never weaken safety controls.
4. The marketplace must distinguish between distribution rights and execution rights.
5. A factory may allow a package to be installed but not activated in a specific station.

---

## 2. Package states

```text
submitted
  -> schema_validated
  -> capability_validated
  -> compatibility_validated
  -> commercially_reviewed
  -> signed
  -> listed
  -> installed
  -> entitled
  -> station_approved
  -> active
```

A package is not runnable until it reaches `station_approved`.

---

## 3. License models

| licenseModel | Description | Source visibility | Typical use |
|---|---|---|---|
| open_source | Source code is published | Full or substantial | Research, education, reference |
| source_available | Source visible under restrictions | Visible but restricted | Evaluation, enterprise review |
| free_binary | Free package, source hidden | Binary/model only | OEM demo, free official skill |
| commercial | Paid package | Usually binary/model only | Industrial skill product |
| enterprise_private | Private customer package | Contract-defined | Factory-specific workflows |
| dataset_license | Data/model asset | Dataset/model only | Training and evaluation |

---

## 4. Pricing models

| pricingModel | Meaning |
|---|---|
| free | No payment required |
| developer_reward | Developer may receive reward, not direct marketplace sale |
| per_robot | One license per robot |
| per_site | One license per site/factory |
| subscription | Time-limited recurring license |
| per_execution | Metered execution |
| enterprise_contract | Negotiated enterprise agreement |

---

## 5. Source availability

| sourceAvailability | Meaning |
|---|---|
| full_source | Code and metadata are visible |
| partial_source | Some source visible, models/binaries hidden |
| binary_only | Executable artifact only |
| model_only | Model weights only |
| dataset_only | Dataset only |
| private_source | Source visible only under NDA or escrow |

---

## 6. Entitlement policy

A commercial or enterprise-private package should require entitlement before activation.

Entitlement may be:

- account-based;
- robot-serial-bound;
- site-bound;
- time-bound;
- station-bound;
- execution-count-bound.

Example:

```json
{
  "skillId": "etd.assembly.precision",
  "licenseId": "lic_assembly_site_a_001",
  "allowedRobots": ["robot-07", "robot-08"],
  "allowedStations": ["assembly_station_a"],
  "expiresAt": "2027-05-11T00:00:00Z",
  "maxExecutions": null
}
```

---

## 7. IP protection controls

Recommended controls:

- package signing;
- encrypted model payloads;
- obfuscated proprietary policy modules if needed;
- immutable release hashes;
- source escrow for enterprise customers;
- watermarking of generated trajectories or model files;
- license tokens;
- revocation list;
- audit logging.

The marketplace should not rely on obfuscation alone.

---

## 8. Safety controls for commercial packages

Even commercial packages must be blocked if they request:

- servo torque write access;
- joint limit override;
- balance core override;
- collision disable;
- emergency stop override;
- human protective stop override.

A paid package that requests forbidden control must be rejected.

---

## 9. Store listing metadata

Every marketplace listing should display:

- skill name;
- publisher;
- version;
- family;
- robot class;
- risk level;
- certification state;
- license model;
- pricing model;
- source availability;
- support level;
- compatible stations;
- required services;
- last validation date.

---

## 10. Commercial policy recommendation for ETD v0.1

For the current prototype:

- all example packages are reference packages;
- examples should be treated as open-source/source-available templates;
- no real payment is implemented;
- commercial logic should be simulated through metadata only;
- execution is allowed only if validation and station checks pass.

For v0.2:

- add signed package metadata;
- add fake entitlement checks;
- add per-robot and per-site simulated license examples;
- add private enterprise package examples.

