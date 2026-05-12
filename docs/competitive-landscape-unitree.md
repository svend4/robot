# Competitive Landscape: Humanoid Robot Ecosystems (2026)

ETD targets the application layer above OEM robot platforms. Understanding the broader
competitive landscape — who builds platforms, who distributes skills, and where ETD sits —
is essential for positioning the framework and planning future skill packages.

---

## 1. Unitree

**Platform family**: G1, H1, B2, Go2 (quadruped), Z1 (arm)
**Skill store status**: Action Library launched publicly in late 2025 / early 2026
**Ecosystem model**: community/developer-first — upload, share, download actions and datasets

### What Unitree is building

- **Action Library**: upload and download motion routines (dance, martial arts, gestures)
- **Datasets section**: community training data for imitation learning
- **Applet Library**: downloaded actions sync to mobile app, then to robot
- **G1-D platform**: end-to-end pipeline — data acquisition → training → simulation → deployment

Unitree maintains significant open-source presence: dexterity datasets, G1 gripper and Z1
dual-arm datasets, imitation-learning frameworks, SDKs.

### ETD positioning against Unitree

Unitree validates the "downloadable robot skills" direction. ETD differentiates as
industrial-grade: package signing, capability policy, station compatibility, failure-scenario
testing, and enterprise-layer integration that a consumer Action Library does not provide.

The **UniPwn** disclosure (worm affecting Go2, B2, G1, H1) is a concrete argument that
any robot skill distribution layer needs signing, sandboxing, revocation, and audit at the
platform level — not just at the robot OS level.

---

## 2. Boston Dynamics / Hyundai Motor Group

**Platform**: Atlas (humanoid, 56 DoF, 50 kg peak payload), Spot (quadruped), Stretch (warehouse)
**Orchestration**: Orbit — enterprise fleet orchestration, MES/WMS/ERP integration, webhooks
**Acquisition**: Hyundai acquired 80 % of Boston Dynamics in 2021; US robot factory with
capacity up to 30,000 units/year under construction

### What Boston Dynamics is building

- **Orbit**: enterprise fleet management above the OEM control stack; API/webhook integration
  into MES/WMS/ERP systems; skill fleet deployment (one skill learned → deployed to whole fleet)
- **Atlas autonomy stack**: layered — whole-body control / balance / locomotion core (OEM) →
  autonomy / perception / object recognition (BD) → application-layer skills (ETD)
- **HMGMA deployment**: Atlas planned for automotive sequencing at Hyundai Motor Group
  Manufacturing Alabama by 2028, expanding to assembly and other operations

### ETD positioning

ETD occupies the application layer between Orbit and the BD autonomy stack. The
`etd.atlas.humanoid_walkfetch` skill package is the reference implementation.
Orbit provides job context from MES; ETD emits `command.skill_intent`; BD converts intent
to joint-space commands. ETD never writes joint angles, torque setpoints, or balance commands.

---

## 3. Hyundai Robotics LAB (non-Atlas platforms)

**Platforms**: MobED (100 kg AMR), H-Motion cobot (welding), H-Motion AMR (1.5 t),
Parking Robot (3.4 t, 1.2 m/s), VEX/H-MEX exoskeleton, X-ble Shoulder, X-ble MEX,
ACR (EV charging robot), DAL-e / DAL-e Delivery, Safety Inspection robot
**Software**: Edge Brain — on-device AI inference, developed with DEEPX, announced January 2026

### What Hyundai Robotics LAB is building

- **Edge Brain**: proprietary on-device AI inference runtime for Hyundai robot platforms;
  targets low-latency embodied AI at the robot level (below ETD, above OEM servo control)
- **MobED Alliance**: March 2026 commercialization push for MobED into logistics and services
- **X-ble Shoulder**: first wearable robot in South Korea to receive KS certification (March 2026)

### ETD positioning

Three ETD skill packages are reference implementations for Hyundai platforms:
`etd.hyundai.wia_welding`, `etd.hyundai.mobed_transport`, `etd.hyundai.vest_exoskeleton`.
The full stack is: Orbit → ETD → Edge Brain → OEM control.

ETD sits above Edge Brain (on-device inference) and below Orbit (fleet orchestration). This
makes ETD the correct layer for task-context logic, safety policy enforcement, and primitive
sequencing — while Edge Brain handles perception inference and OEM controls hardware.

---

## 4. Agility Robotics (Digit)

**Platform**: Digit — bipedal humanoid, 135 kg payload, warehouse logistics focus
**Key partnership**: Amazon — Digit deployed in Amazon fulfillment centers for tote lifting
**Software**: Agility Arc — cloud platform for fleet management and skill deployment

### Landscape context

Agility/Amazon represents a vertically integrated model: one OEM, one customer, one use case
(tote movement in fulfillment). Agility Arc is not an open skill marketplace — it is a
managed fleet system for a specific workcell type.

ETD's differentiation: platform-neutral, multi-OEM, multi-task skill packaging standard,
not tied to a single operator or warehouse type.

---

## 5. Figure / OpenAI

**Platform**: Figure 01 and Figure 02 — bipedal humanoid
**Key partnership**: BMW manufacturing (assembly line pilot, 2024–2025)
**Software**: OpenAI integration for natural-language task direction

### Landscape context

Figure's approach uses large language models at the task-direction layer. The robot accepts
natural-language instructions and translates them into motion. This is compelling for
unstructured environments but raises auditability and certification questions for industrial
settings where task determinism and safety envelopes must be documented.

ETD's differentiation: explicit capability policy, station compatibility, and failure-scenario
testing are verifiable artifacts — not emergent from a language model. An ETD skill package
can be audited by a safety engineer; an LLM-driven task plan cannot.

---

## 6. 1X Technologies

**Platform**: Eve (wheeled humanoid, commercial production), NEO (bipedal humanoid, development)
**Model**: subscribed humanoid-as-a-service for security and light manufacturing tasks
**Data approach**: large-scale human teleoperation data for behavior learning

### Landscape context

1X focuses on using human teleop data to scale behavior learning. Their commercialization
model is subscription-based hardware deployment, not a skill marketplace. The skill-IP layer
is retained by 1X rather than distributed to operators.

ETD's differentiation: operators can own and customize their skill packages (with IP
protection for commercial packages), rather than subscribing to behaviors that the OEM controls.

---

## 7. Apptronik (Apollo)

**Platform**: Apollo — bipedal humanoid, 55 kg payload, automotive/manufacturing focus
**Key partnership**: Mercedes-Benz pilot announced 2024
**Software**: Apptronik cloud — skill deployment and fleet management

### Landscape context

Apptronik targets the same automotive manufacturing use case as Atlas/HMGMA. Apollo's
payload spec (55 kg) is comparable to Atlas (50 kg peak). Both are targeting sequencing and
material handling in automotive plants before expanding to assembly.

ETD's differentiation: ETD targets the application layer above any OEM stack, so the same
skill package (with an OEM-specific adapter) could target Atlas or Apollo, rather than being
locked to a single platform.

---

## 8. Tesla Optimus

**Platform**: Optimus Gen 2 — bipedal humanoid, designed for Tesla factory use first
**Software**: proprietary; trained end-to-end with Tesla's AI/data stack
**Model**: internal deployment first; third-party access unclear

### Landscape context

Tesla's stated strategy is to use Optimus internally to validate the system at scale, then
offer the robot commercially. The skill layer appears to be fully proprietary with no
announced marketplace or packaging standard.

ETD's differentiation: OEM-neutral, open standard for skill packaging. If Tesla eventually
opens an Optimus skill interface, ETD-format packages could target it via an adapter.

---

## 9. ROS 2 / Open-source ecosystem

**Platform**: ROS 2 — the de facto open-source robot middleware
**Skill sharing**: ROS packages (open-source, no validation or safety governance)
**Governance**: community PR process; no package signing, no capability policy

### Landscape context

ROS 2 packages can implement any behavior at any layer including direct hardware access.
The open-source community model provides flexibility but no safety guarantee. Industrial
deployments that rely on ROS 2 packages must add validation, signing, and station-compat
checking themselves.

ETD's differentiation: ETD is not a middleware replacement — it can run on top of ROS 2.
ETD adds the governance layer (signing, policy, failure simulation, release artifacts) that
ROS packages do not provide by default. The ETD ROS 2 bridge (`ros2_bridge/`) is the
integration point.

---

## Summary: ETD competitive position

| Competitor / ecosystem | Primary layer | Skill packaging | Safety governance | OEM-neutral |
|---|---|---|---|---|
| Unitree Action Library | consumer/developer | community upload | limited | Unitree-only |
| Boston Dynamics Orbit | enterprise fleet | OEM-managed | OEM safety core | BD/Hyundai |
| Agility Arc | fleet management | OEM-managed | OEM | Agility-only |
| Figure / OpenAI | LLM task direction | emergent | not auditable | Figure-only |
| 1X subscription | HaaS | OEM-retained | OEM | 1X-only |
| ROS 2 ecosystem | middleware | raw packages | none | multi-OEM |
| **ETD** | **application layer** | **validated, signed** | **explicit policy** | **multi-OEM** |

ETD's position is unique: it is the only framework that:

1. defines a signed, validated package format for robot skills;
2. enforces capability policy (forbidden capabilities blocked at install);
3. requires station compatibility verification before deployment;
4. mandates failure-scenario testing (human-zone abort, sensor loss, balance abort) before publish;
5. works above any OEM control stack without replacing it;
6. supports multiple platforms via OEM-specific adapters within the same package format.

The market gap ETD targets: between Orbit/MES (enterprise orchestration, task requests) and
OEM motion stacks (hardware control, safety kernel) — the application layer where task context,
skill logic, and safety policy enforcement live.

---

## Strategic conclusion

Unitree validates the direction. Boston Dynamics / Hyundai validates the platform. The gap
in the market is a neutral, multi-OEM, safety-enforced skill distribution standard that
industrial operators, OEMs, and system integrators can adopt above their proprietary stacks.

ETD should not compete as another entertainment action store, as a fleet orchestration layer,
or as a robot OS. It should compete — and currently has no direct competitor — as the
**safety-aware packaging, validation, and deployment layer for industrial humanoid skills**.
