# Commercialization and Protection Notes for ETD Skill Packages

## 1. Commercialization thesis

Robot skills can become software products.

The analogy is not perfect, but useful:

- smartphone apps extend phones;
- browser extensions extend browsers;
- ROS packages extend robotics stacks;
- ETD skill packages extend robot application behavior.

For industrial robots, the value is not only the code. The value includes:

- validated task behavior;
- compatibility metadata;
- station integration;
- safety constraints;
- telemetry;
- support;
- updates;
- certification evidence.

Therefore, an ETD skill package can be sold not merely as “a script”, but as a **validated operational module**.

---

## 2. What can be monetized?

A commercial ETD package can monetize several layers:

1. **Skill logic**
   - task routing;
   - primitive sequencing;
   - CHS profile selection;
   - fallback logic.

2. **Motion templates**
   - approach paths;
   - contact strategies;
   - assembly insertion patterns;
   - inspection passes.

3. **Trained policies or models**
   - learned grasp selector;
   - vision classifier;
   - anomaly detector;
   - force-control policy.

4. **Station integration**
   - MES connector;
   - WMS connector;
   - QA capture integration;
   - workcell-specific station profiles.

5. **Validation artifacts**
   - simulation tests;
   - acceptance tests;
   - benchmark results;
   - safety review report.

6. **Support and updates**
   - maintenance;
   - bug fixes;
   - compatibility updates;
   - runtime migration support.

---

## 3. Pricing models

## 3.1 Free/open reference model

Use for:

- base examples;
- academic dissemination;
- developer onboarding;
- community packages.

Revenue: none directly.

Strategic value:

- ecosystem growth;
- trust;
- standard adoption.

---

## 3.2 Paid per package

The customer pays once for a skill package.

Good for:

- simple skills;
- small teams;
- non-critical tooling.

Weakness:

- poor fit for ongoing support;
- unclear liability for industrial use.

---

## 3.3 Subscription per robot

The customer pays per robot per month/year.

Good for:

- fleet deployments;
- support-heavy packages;
- continuously updated skills;
- commercial marketplaces.

Example:

```json
{
  "pricingModel": "per_robot_subscription",
  "priceTier": "enterprise",
  "billingPeriod": "annual",
  "licenseScope": "robot"
}
```

---

## 3.4 Site license

The customer pays for all robots at one factory or worksite.

Good for:

- automotive plants;
- warehouses;
- large enterprise deployments;
- private station-specific skills.

---

## 3.5 Fleet license

The customer pays for all robots in an organization.

Good for:

- multi-site enterprise rollout;
- OEM-level partnership;
- large industrial integrators.

---

## 3.6 Usage-based pricing

Payment is based on runtime usage.

Possible metrics:

- cycles executed;
- successful picks;
- inspected parts;
- machine-tending events;
- hours of operation.

Risk:

- metering complexity;
- privacy concerns;
- customer resistance in production environments.

---

## 4. Protection stack

A commercial ETD package should not rely on obscurity only.

Recommended protection stack:

```text
Marketplace Listing
  -> Publisher Identity
  -> Package Signature
  -> License Entitlement
  -> Compatibility Validation
  -> Capability Sandbox
  -> Runtime Execution Boundary
  -> Telemetry and Audit Logs
  -> Revocation / Rollback
```

---

## 5. Intellectual property protection

## 5.1 Protecting source code

Options:

- keep source closed;
- ship compiled Python extensions or bytecode only;
- package policy models separately;
- encrypt proprietary payloads;
- expose only metadata and contract.

However, core safety metadata must remain readable.

The runtime must be able to inspect:

- required services;
- capabilities;
- forbidden capability declarations;
- constraints;
- telemetry events;
- safety fallback;
- compatibility metadata.

---

## 5.2 Protecting trained models

Trained policies and ML models may be the most valuable part.

Protection options:

- encrypted model weights;
- hardware-bound license;
- secure runtime loading;
- model watermarking;
- online entitlement check;
- offline license grace period.

---

## 5.3 Protecting station know-how

Station profiles can encode sensitive factory process knowledge.

Protection options:

- private packages;
- customer-specific encryption;
- site-scoped licenses;
- no public marketplace listing;
- separate customer NDA.

---

## 6. Security model

Commercial packages must be treated as potentially risky third-party software.

Runtime must enforce:

- no servo-level write access;
- no safety override;
- no arbitrary network access unless declared;
- no hidden file-system access;
- no unbounded execution;
- no unreviewed dynamic code loading;
- explicit capability declarations.

Suggested future capability categories:

```text
read.state.*
read.perception.*
read.workflow.*
write.skill_intent
write.telemetry
network.license_check
network.enterprise_webhook
storage.package_cache
```

---

## 7. Liability model

Industrial robot skill marketplaces need a clear liability split.

Suggested split:

- OEM robot core: low-level certified safety and control;
- ETD runtime: package validation, sandbox, execution boundary;
- package publisher: skill behavior and declared constraints;
- customer/integrator: station setup and deployment environment;
- marketplace operator: listing policy and revocation.

This is why ETD packages should remain application-layer only.

---

## 8. Open-source vs commercial recommendation

For ETD v0.1:

| Package type | Recommended license model |
|---|---|
| `etd.pickplace.basic` | open-source reference |
| `etd.assembly.precision` | dual-license or commercial |
| `etd.inspect.vision` | commercial if ML models included |
| `etd.cobot.safeassist` | OEM-certified / enterprise only |
| adapters | dual-license |
| schemas | open standard |
| validator | open-source reference implementation |
| marketplace policy | open standard + commercial operator rules |

Recommended project strategy:

1. open-source schemas and validator;
2. open-source basic example packages;
3. keep advanced industrial packages commercial;
4. keep customer station profiles private;
5. use enterprise certification for cobot/human-aware packages.

---

## 9. Marketplace governance

A serious ETD marketplace should have review levels.

### Low risk

Examples:

- demo motion;
- inspection-only package;
- no physical contact;
- read-only telemetry package.

Review:

- automated schema validation;
- capability check;
- simple simulation.

### Medium risk

Examples:

- pick-and-place;
- precision assembly;
- machine tending;
- non-human-contact manipulation.

Review:

- schema validation;
- capability check;
- station profile check;
- scenario simulation;
- failure scenarios;
- manual review optional.

### High risk

Examples:

- cobot human handover;
- high-force manipulation;
- tool use;
- cutting/welding/drilling;
- mobility near humans.

Review:

- manual safety review;
- OEM/platform review;
- simulator certification;
- production pilot;
- telemetry gates;
- staged rollout.

---

## 10. Why this matters

A robot skill store without protection and validation is risky.

A robot skill store with only entertainment skills is limited.

A robot skill store with ETD-style validation can support industrial use:

- safe install;
- skill compatibility;
- station awareness;
- commercial licensing;
- auditability;
- rollback;
- enterprise deployment.

That is the strongest version of the ETD marketplace concept.
