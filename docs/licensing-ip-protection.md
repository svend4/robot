# ETD Skill Licensing and IP Protection

## Purpose

This document explains how ETD skill packages can be released as open-source, free closed-source, paid commercial, or enterprise-licensed packages.

It also describes how commercial robot skills can be protected while still allowing safe runtime validation and installation.

---

## 1. Key distinction: package metadata vs protected payload

A robot skill package should separate visible metadata from protected implementation.

Visible and auditable:

- `manifest.yaml`
- `skill.json`
- `chs_profiles.json`
- `capabilities.json`
- `execution_contract.json`
- safety declarations
- package risk level
- validation evidence
- supported robot classes and stations

Potentially protected:

- policy implementation;
- trained model weights;
- trajectory optimization logic;
- proprietary task heuristics;
- station-specific tuning;
- commercial datasets;
- vendor-specific adapters.

This split allows the marketplace and runtime to validate the package without exposing every commercial secret.

---

## 2. License categories

## 2.1 Open-source package

```text
Source: visible
Modification: allowed by license
Distribution: allowed by license
Runtime validation: required
Commercial use: depends on license
```

Suitable licenses:

- MIT
- Apache-2.0
- BSD-3-Clause
- GPL / AGPL for copyleft use cases

Use cases:

- education;
- academic research;
- reference skills;
- marketplace examples;
- community skills.

## 2.2 Source-available package

```text
Source: visible to customers
Modification: restricted
Redistribution: restricted
Commercial use: contract-defined
```

Useful for enterprise customers who need auditability but not redistribution rights.

## 2.3 Free proprietary package

```text
Source: hidden
Price: free
Redistribution: restricted
Support: limited
```

Useful for demos and vendor ecosystem growth.

## 2.4 Paid proprietary package

```text
Source: hidden
Price: paid
License: per robot / station / site / fleet
Support: contract-defined
```

Useful for high-value industrial skills.

## 2.5 Enterprise certified package

```text
Source: hidden or source-available
Validation: stricter
Deployment: station- and robot-specific
Support: SLA-backed
```

Useful for automotive and other safety-critical industrial deployments.

---

## 3. Protection layers

No software protection is perfect, especially when code runs on a customer-controlled machine. A realistic commercial system uses multiple layers.

## 3.1 Package signing

Every released package should be signed.

Runtime behavior:

```text
Download package
→ verify publisher signature
→ verify package hash
→ verify manifest hash
→ verify license token
→ validate capabilities
→ allow install
```

Benefits:

- prevents tampering;
- supports publisher accountability;
- enables safe rollback;
- enables marketplace trust.

## 3.2 License token

A commercial package can require a license token.

Token fields:

```json
{
  "licenseId": "LIC-2026-0001",
  "skillId": "etd.assembly.precision.pro",
  "licensee": "Factory Customer A",
  "licenseModel": "per_robot_per_year",
  "allowedRobotIds": ["robot-001", "robot-002"],
  "allowedStations": ["assembly_station_a"],
  "expiresAt": "2027-05-11T00:00:00Z",
  "features": ["precision_insert", "force_bounded_retry"],
  "signature": "..."
}
```

## 3.3 Hardware binding

A license can be bound to:

- robot serial number;
- controller ID;
- site ID;
- station ID;
- fleet ID;
- secure hardware identity if available.

This reduces unauthorized copying, but should be used carefully because robots may be replaced during maintenance.

## 3.4 Encrypted implementation payload

The package can expose metadata but encrypt protected implementation files.

Example:

```text
manifest.yaml                  visible
skill.json                     visible
capabilities.json              visible
policies/policy_runner.bin     encrypted or compiled
models/policy_weights.etdenc   encrypted
```

The runtime decrypts only after:

1. signature verification;
2. license check;
3. station compatibility check;
4. safety policy validation.

## 3.5 Compiled / obfuscated policy module

For Python prototypes, source is easy to inspect. Commercial releases may use:

- compiled extensions;
- packaged binaries;
- model-only packages;
- obfuscated scripts;
- containerized execution;
- remote policy services.

Important caveat: obfuscation is not strong protection. It only raises the effort required to copy the implementation.

## 3.6 Cloud-mediated execution

The strongest commercial protection is often not local DRM, but a service model:

```text
Robot runtime sends high-level state summary
→ cloud service returns bounded high-level skill intent
→ local runtime validates the intent again
→ OEM middleware executes only safe commands
```

This protects proprietary logic better, but it creates new issues:

- latency;
- factory network dependency;
- data privacy;
- availability;
- cybersecurity;
- customer reluctance to send production data externally.

For automotive factories, on-prem deployment is often more acceptable than public cloud.

## 3.7 On-prem license server

A practical industrial compromise:

```text
Factory-local license server
→ validates packages
→ distributes tokens
→ keeps logs
→ works offline from public internet
```

This is often better for enterprise customers than pure cloud DRM.

---

## 4. Runtime enforcement

The runtime should enforce:

- package signature;
- license validity;
- robot/station authorization;
- expiry date;
- allowed capabilities;
- runtime compatibility;
- maximum risk level;
- rollback availability.

A commercial skill should not be allowed to execute if any of these checks fail.

---

## 5. Marketplace listing and source visibility

Every skill listing should declare source visibility:

```json
{
  "sourceVisibility": "open_source | source_available | closed_source | encrypted_payload",
  "licenseModel": "free | paid | subscription | enterprise | certified",
  "redistribution": "allowed | restricted | prohibited",
  "modification": "allowed | restricted | prohibited",
  "auditability": "metadata_only | source_review | binary_attestation | full_audit"
}
```

---

## 6. How to protect ETD packages specifically

Recommended package layout for a commercial ETD skill:

```text
etd.assembly.precision.pro/
├── manifest.yaml                 # public
├── skill.json                     # public
├── chs_profiles.json             # public or partially public
├── capabilities.json              # public
├── execution_contract.json        # public
├── license_requirements.json      # public
├── signature.json                 # public
├── policies/
│   └── policy_runner.bin          # protected
├── models/
│   └── assembly_policy.etdenc     # protected
├── telemetry/
│   └── events.json                # public
└── tests/
    └── acceptance_tests.yaml      # public or marketplace-visible
```

---

## 7. What should remain open

Even for commercial packages, some parts should remain visible so customers can trust the package:

- requested capabilities;
- forbidden capabilities;
- risk level;
- supported robot classes;
- supported station profiles;
- fallback behavior;
- telemetry events;
- safety boundaries;
- validation report;
- publisher identity;
- package signature status.

For industrial robotics, hiding all details is not desirable. Customers need enough visibility to perform safety and technical due diligence.

---

## 8. What can remain closed

Commercial publishers can reasonably keep these closed:

- optimized policy logic;
- proprietary trajectory selection;
- learned model weights;
- tuning heuristics;
- commercial datasets;
- station-specific calibration details;
- proprietary integration code.

---

## 9. Security model

A paid robot skill should be protected by:

1. signed package;
2. signed license token;
3. hardware or station binding;
4. capability sandbox;
5. runtime validation;
6. encrypted or compiled payload;
7. audit logging;
8. revocation mechanism;
9. rollback mechanism;
10. legal license agreement.

---

## 10. Practical limitation

A robot skill package cannot be protected perfectly if the customer controls the machine, filesystem, and runtime environment. Protection is a risk-reduction strategy, not an absolute guarantee.

The strongest protection comes from combining:

- technical controls;
- commercial contracts;
- support value;
- updates;
- certification;
- trust and reputation.

---

## 11. Recommended ETD policy

For the ETD prototype, the best strategy is:

1. keep reference packages open-source;
2. make schema and validator open-source;
3. allow commercial packages later;
4. require all packages, open or closed, to expose safety metadata;
5. require signed releases for marketplace distribution;
6. support enterprise on-prem licensing for industrial customers.

This allows ecosystem growth without compromising industrial safety.
