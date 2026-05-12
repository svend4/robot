# Unitree Skill Marketplace Analysis

Unitree's humanoid robot app-store announcement is an external validation signal for the ETD
direction: robot value is moving from hardware-only performance to downloadable, reusable, and
community-extensible capabilities.

---

## Key distinction

Unitree's public direction is consumer/developer-first: Action Library, Datasets, mobile app
sync, and community uploads. The developer guide describes requirements for action identifiers
and metadata; downloads sync into the robot's **Applet Library** after a user acquires them.
Separately, Unitree maintains open-source resources (G1 dexterity datasets, imitation-learning
frameworks, G1 gripper and Z1 dual-arm datasets).

ETD is positioned as an industrial-grade equivalent:

- validated skill packages with signed release artifacts;
- explicit capability policies;
- station compatibility checking;
- failure-scenario testing before publish;
- enterprise and workflow-layer integration;
- strict application-layer boundaries that never touch OEM safety or motion-control subsystems.

---

## Unitree G1-D: broader platform context

The G1-D platform is Unitree's end-to-end pipeline for embodied-AI deployment:
data acquisition → model training/inference → simulation → one-click deployment.
This moves the Unitree ecosystem beyond "action downloads" toward trained models and policies
as distributable artifacts — the same trajectory ETD addresses with validated skill packages.

---

## Monetization: what is and is not confirmed

Public reporting (TechRadar, 3DNews, robohorizon.com) confirms:

- developers/users can upload and download actions and datasets;
- Unitree mentions "rewards" for high-quality contributors;
- Unitree has significant open-source elements (SDKs, datasets, imitation-learning framework).

What is **not** publicly confirmed for the Unitree store:

- a mature paid marketplace with pricing, revenue share, and DRM;
- industrial certification or safety review of uploaded actions;
- robot-binding or entitlement enforcement on distributed packages.

The safest characterization: Unitree is building a community/developer distribution platform.
The final commercial and protection model may evolve.

---

## Security case: why robot skill stores need stricter governance

In early 2026, security researchers disclosed **UniPwn** — a worm-class vulnerability affecting
Unitree Go2, B2, G1, and H1 robots that could turn them into a botnet. The disclosure
illustrates a structural gap: a consumer app-store security model is insufficient for a platform
that delivers executable behavior to physical machines operating near people.

A robot skill store that lacks:

- package signing and signature verification at install time,
- capability sandboxing preventing a skill from touching safety cores,
- revocation infrastructure to pull compromised packages across a deployed fleet,
- an audit log recording which skill ran on which robot and when,

…inherits the same attack surface at the application layer.

ETD enforces all four controls. Every package in the ETD store is Ed25519-signed and
verified before install. Capabilities that touch `emergency_stop`, `collision_core`, or
`locomotion_balance_core` are blocked at the policy level — no skill package can request them.
The `manifest.yaml` `fallbackSkill` field ensures a safe-stop path exists before a skill is
listed. And the revocation and audit-log infrastructure is part of the v0.6.0 roadmap.

---

## The safety-metadata principle

The critical governance rule derived from both the UniPwn case and the commercial licensing
discussion:

> A commercial skill package may protect its intellectual property — source code,
> trained model weights, process recipes — but it **cannot** hide its safety declarations.

Concretely, a skill package may ship as a binary or encrypted payload, but the following
must remain readable by the ETD runtime and any station install checker:

| Always-readable field | Why |
|---|---|
| `capabilities.json` write list | runtime must verify no forbidden capability is requested |
| `manifest.yaml` fallbackSkill / fallbackMode | platform must confirm a safe-stop path exists |
| `execution_contract.json` safety constraints | station operator must see payload, force, speed limits |
| `manifest.yaml` skillId, version, publisher | accountability and revocation |
| `telemetry/events.json` event list | station log system must know what events to expect |

The proprietary payload — the `chs_adapter.py` logic, trained policies, welding recipes,
inspection models — may be encrypted or binary-only. The safety envelope must not be.

---

## ETD licensing model

Based on the Unitree comparison, the recommended ETD licensing model is hybrid:

| Package type | Code | Price | Use case |
|---|---|---|---|
| Open-source reference | open | free | standard, education, demos |
| Free proprietary | closed | free | OEM demo packages |
| Commercial skill | closed / partial source | paid per site | industrial workflows |
| Enterprise-certified | closed / NDA | contract | automotive, warehouse, assembly line |
| Private OEM / factory | private | internal | specific workcell or factory line |

The ETD core runtime, JSON schemas, reference validator, and reference example packages
(`etd.pickplace.basic`, `etd.assembly.precision`, `etd.inspect.vision`, `etd.cobot.safeassist`)
are kept open-source. Industrial Hyundai and Atlas skill packages target the commercial and
enterprise-certified tiers.

**Formula**: ETD Core — open-source. ETD Reference Skills — free/open. ETD Industrial Skills —
commercial or enterprise-certified. ETD Safety Metadata — always readable. ETD Proprietary
Payload — may be protected.

---

## Implication for ETD

The Unitree store validates the direction. The ETD response is a more explicit governance
architecture: not just "download a skill" but "validate → authorize → bind to station →
verify safety envelope → deploy → audit." The UniPwn disclosure is a concrete reminder that
physical-safety governance must be built into the distribution layer, not assumed from the
OEM runtime alone.
