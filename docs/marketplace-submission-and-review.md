# Marketplace Submission and Review Guide

## Purpose

This guide defines how a developer should submit an ETD skill package to a robot skill marketplace, and how the marketplace should review it before publication.

The same process can support open-source, free, paid and private enterprise skill packages.

---

## 1. Submission package

A submission must include:

```text
etd.<family>.<name>/
├── manifest.yaml
├── skill.json
├── chs_profiles.json
├── capabilities.json
├── execution_contract.json
├── telemetry/events.json
├── tests/acceptance_tests.yaml
├── policies/
├── README.md
└── LICENSE or license_policy.json
```

Commercial packages should also include:

```text
commercial/
├── license_policy.json
├── support_terms.md
├── publisher_profile.json
├── release_notes.md
└── checksums.json
```

---

## 2. Review stages

## Stage 1 — Identity and publisher review

Checks:

- publisher identity;
- contact details;
- license rights;
- whether the publisher owns the submitted assets;
- whether the package includes third-party code or datasets.

Outcome:

- accepted;
- rejected;
- additional evidence required.

---

## Stage 2 — Schema validation

Checks:

- manifest schema;
- skill schema;
- CHS profiles;
- capabilities;
- execution contract;
- telemetry events;
- tests.

Tool:

```bash
python etd_reference_validator.py examples/etd.pickplace.basic --runtime-context runtime_context.json
```

Outcome:

- valid;
- valid with warnings;
- invalid.

---

## Stage 3 — Capability and safety boundary review

Checks:

- no servo-level write access;
- no collision disable;
- no emergency stop override;
- no balance core override;
- no human-protective-stop override;
- fallback skill exists;
- timeout defined;
- station compatibility declared.

Outcome:

- low risk;
- medium risk;
- high risk;
- rejected.

---

## Stage 4 — Simulation review

Checks:

- successful scenario execution;
- failure scenario behavior;
- human-too-close handling;
- missing-service handling;
- station-incompatible handling;
- payload-out-of-range handling.

Recommended command:

```bash
python sim/scenario_runner.py
python sim/failure_scenarios.py
python sim/report_runner.py
```

Outcome:

- simulation pass;
- simulation pass with warnings;
- simulation fail.

---

## Stage 5 — Commercial review

Only for paid or private packages.

Checks:

- license model;
- price model;
- entitlement scope;
- support tier;
- refund/revocation rules;
- redistribution rules;
- source availability.

Possible license models:

- open_source;
- free_proprietary;
- commercial_per_robot;
- commercial_per_site;
- commercial_subscription;
- enterprise_private;
- evaluation_only.

---

## Stage 6 — Security and IP review

Checks:

- package signing;
- checksums;
- SBOM if required;
- model/dataset provenance;
- encrypted assets if commercial;
- no hidden forbidden capabilities;
- no network calls unless declared;
- no undocumented telemetry export.

Outcome:

- approved;
- approved with restrictions;
- rejected.

---

## Stage 7 — Publication

A package can be published only if:

- schema validation passes;
- compatibility level is A or B;
- capability policy is safe;
- failure scenarios are acceptable;
- license model is declared;
- publisher identity is approved;
- package is signed.

---

## 3. Marketplace risk levels

## Low risk

Examples:

- non-contact inspection;
- educational demo;
- visualization;
- telemetry dashboard.

Requirements:

- schema validation;
- basic compatibility check;
- signed package.

## Medium risk

Examples:

- pick-and-place;
- light assembly;
- cobot assistance with no heavy payload;
- guided inspection with movement.

Requirements:

- simulation review;
- station profile check;
- human-aware behavior;
- fallback policy.

## High risk

Examples:

- forceful manipulation;
- welding;
- cutting;
- heavy payload;
- close human collaboration;
- locomotion through shared space.

Requirements:

- site-specific review;
- industrial safety assessment;
- restricted distribution;
- human supervisor approval;
- site acceptance testing;
- rollback and telemetry monitoring.

---

## 4. Publication metadata

Marketplace listing should include:

```json
{
  "skillId": "etd.assembly.precision",
  "version": "0.1.0",
  "publisher": "etd-lab",
  "licenseModel": "commercial_per_robot",
  "riskLevel": "medium",
  "sourceAvailable": false,
  "robotClass": ["humanoid", "fixed_manipulator"],
  "compatibilityLevel": "A",
  "supportTier": "standard",
  "requiresSiteReview": true,
  "redistributionAllowed": false
}
```

---

## 5. Review decision matrix

| Result | Meaning | Marketplace action |
|---|---|---|
| Approved | Safe enough for declared use | Publish |
| Approved with restrictions | Needs limited robot/site scope | Publish to restricted audience |
| Needs revision | Issues can be fixed | Return to developer |
| Rejected | Unsafe, incompatible or legally unclear | Do not publish |
| Enterprise-only | Too site-specific for public store | Publish privately |

---

## 6. Recommended ETD marketplace policy

1. Open examples may be public and free.
2. Industrial skills should require validation and station compatibility.
3. Paid packages should require publisher verification and signed releases.
4. High-risk skills should not be publicly installable without site review.
5. Runtime must enforce capability policy regardless of marketplace approval.
6. Marketplace approval must not override OEM safety core.
7. Commercial entitlement must be checked at activation time, not only at download time.

---

## 7. Practical conclusion

A robot skill marketplace is not just a file store. It is a controlled distribution system for physical behavior.

For smartphones, a bad app can crash a screen. For humanoid robots, a bad skill can move mass through physical space. Therefore the marketplace must combine:

- documentation;
- validation;
- safety boundary enforcement;
- licensing;
- signing;
- simulation;
- station review;
- telemetry;
- rollback.
