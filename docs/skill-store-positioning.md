# ETD Skill Store Positioning

## One-line positioning

ETD is an application-layer standard for packaging, validating, simulating, and deploying robot skills safely across industrial humanoid workcells.

## Store model

An ETD Skill Store should distribute signed skill packages, not raw low-level controller code. Each skill must include metadata, CHS profiles, capability policy, execution contract, telemetry, and tests.

## Required store checks

- schema validation;
- capability safety;
- runtime compatibility;
- station compatibility;
- simulation smoke test;
- failure scenario test;
- release signature;
- rollback metadata.

## Marketplace categories

- Pick & Place
- Precision Assembly
- Vision Inspection
- Cobot Safe Assist
- Machine Tending
- Factory Logistics

## Why this matters

The arrival of humanoid app stores makes a safe industrial standard more urgent. A downloadable skill for a walking machine is not equivalent to a phone app: it has physical safety, liability, and station-context constraints.
