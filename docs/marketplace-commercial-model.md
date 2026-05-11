# ETD Skill Marketplace Commercial Model

## Purpose

This document defines a practical commercial model for an ETD-style robot skill marketplace.

The marketplace should support both open and commercial skills, but every skill must pass safety, capability, compatibility, and packaging validation before it can be installed on a robot platform.

---

## 1. Context: why a robot skill marketplace matters

The robotics market is moving from a hardware-only model toward a software-and-skills ecosystem. A humanoid or mobile manipulator becomes more valuable when its capabilities can be expanded through validated skill packages.

A robot skill marketplace is not simply an app store clone. It distributes software that controls physical behavior, so it needs stricter rules than a normal mobile app store:

- safety validation;
- robot-class compatibility;
- payload and workspace limits;
- station compatibility;
- fallback behavior;
- audit logs;
- version rollback;
- publisher accountability.

---

## 2. Public Unitree reference point

Public reporting describes the Unitree Robotics Developer Platform as a place where users and developers can upload, share, and download skills, actions, datasets, and remote-control functions for Unitree humanoids. Reported examples include action routines such as Bruce Lee, Twist Dance, and Funny Actions.

Public reporting also says that Unitree has encouraged co-development and developer participation. Some reports mention rewards for exceptional developers, but as of the current public information reviewed for this prototype, a clear paid-app monetization scheme is not firmly documented.

Important distinction:

- Unitree has official open-source projects, models, SDKs, datasets, and training tools.
- The public information around the humanoid app store emphasizes sharing, downloading, datasets, action sequences, and developer rewards.
- A mature paid marketplace model may appear later, but it should not be assumed unless confirmed by official marketplace terms.

---

## 3. ETD marketplace positioning

ETD should position itself as a more industrial and validation-heavy marketplace model.

Unitree-style model:

```text
User / developer uploads action or routine
→ app platform displays it
→ user downloads to robot / applet library
→ robot executes supported routine
```

ETD industrial model:

```text
Publisher submits skill package
→ schema validation
→ capability validation
→ station compatibility check
→ simulation / failure-scenario check
→ license verification
→ signed package release
→ staged deployment
→ telemetry and rollback
```

This is the key product distinction: ETD is not only a place to download robot motions; it is a controlled distribution and validation layer for robot skills.

---

## 4. Marketplace product categories

## 4.1 Free open-source skill

Characteristics:

- source code available;
- free to download;
- community support;
- permissive or copyleft license;
- suitable for education, research, demos, and public examples.

Example:

```text
etd.pickplace.basic
License: Apache-2.0 / MIT / BSD-style
Price: free
Support: community
Risk level: low
```

## 4.2 Free closed-source skill

Characteristics:

- free to use;
- source not visible;
- may be distributed as compiled package or signed bundle;
- often used as a promotional package.

Example:

```text
etd.inspect.demo
License: free proprietary
Price: free
Support: limited
```

## 4.3 Paid skill package

Characteristics:

- one-time purchase or subscription;
- source may be closed;
- package signing and license enforcement;
- updates included for a defined period.

Example:

```text
etd.assembly.precision.pro
Price: per robot / per year
License: commercial
Support: standard support
```

## 4.4 Enterprise site license

Characteristics:

- sold to a factory, site, or production line;
- includes integration and support;
- may include station-specific tuning;
- strong audit, telemetry, and rollback requirements.

Example:

```text
etd.machine_tend.automotive.enterprise
Price: per site / per line / per fleet
License: enterprise commercial
Support: SLA-backed
```

## 4.5 Certified / validated skill

Characteristics:

- has passed stricter validation;
- includes simulator evidence;
- includes acceptance tests;
- includes failure-scenario results;
- may be approved only for specific robot/station combinations.

Example:

```text
etd.cobot.safeassist.certified
Scope: RobotClass=humanoid, Station=cobot_zone_a
Validation: Level A + safety-case review
```

---

## 5. Pricing models

Potential pricing models:

| Model | Description | Best for |
|---|---|---|
| Free | No charge | education, demos, open ecosystem |
| Paid download | One-time package purchase | simple skills |
| Subscription | recurring access and updates | maintained skills |
| Per robot | license bound to robot ID | fleet deployment |
| Per station | license bound to workcell | factory tasks |
| Per site | site-wide license | enterprise customers |
| Per execution | usage-based pricing | cloud-mediated skill execution |
| Support contract | support sold separately | enterprise reliability |
| Certification fee | paid validation/certification | marketplace quality control |

For robotics, the most practical commercial models are usually:

1. per robot;
2. per station;
3. per site;
4. enterprise subscription with support.

Per-execution pricing can work, but it is harder in factories because customers often prefer predictable operational costs.

---

## 6. Publisher revenue model

A marketplace operator could use several revenue models:

1. **commission on paid skills** — marketplace takes a percentage;
2. **publisher subscription** — publishers pay to list commercial packages;
3. **certification fee** — publisher pays for validation;
4. **enterprise integration fee** — marketplace operator sells deployment services;
5. **support revenue share** — paid support split between platform and publisher;
6. **private marketplace** — enterprise customer runs an internal skill store.

---

## 7. Skill listing metadata

Every marketplace listing should include:

```json
{
  "skillId": "etd.assembly.precision",
  "version": "0.1.0",
  "publisher": "etd-lab",
  "licenseModel": "commercial_subscription",
  "priceModel": "per_robot_per_year",
  "sourceVisibility": "closed_source",
  "riskLevel": "medium",
  "validationLevel": "A",
  "supportedRobotClasses": ["humanoid", "fixed_manipulator"],
  "supportedStations": ["assembly_station_a"],
  "requiresServices": ["perception.part_alignment", "force_control.contact_feedback"],
  "supportLevel": "standard",
  "refundPolicy": "enterprise_contract",
  "rollbackSupported": true
}
```

---

## 8. Marketplace lifecycle

A commercial skill should pass through this lifecycle:

```text
Draft
→ Submitted
→ Schema validated
→ Security reviewed
→ Simulation tested
→ Station compatibility checked
→ Commercial terms approved
→ Signed release
→ Listed
→ Installed
→ Monitored
→ Updated / deprecated / rolled back
```

---

## 9. Enterprise procurement model

For industrial robots, customers will likely ask:

- Who is liable if the skill damages a part?
- Who supports the skill in production?
- Which robot models are certified?
- Which station profiles are supported?
- Can we run it offline?
- Does it transmit data to the cloud?
- Can we audit the package?
- Can we roll back immediately?
- What is the SLA?
- What evidence proves it is safe enough for this workcell?

The marketplace documentation should answer these questions before a serious pilot.

---

## 10. ETD recommendation

The recommended first commercial model for ETD is not a public consumer store. It is a **private industrial skill registry**:

```text
Internal factory skill catalog
→ validated packages
→ station-specific permissions
→ license + signature checks
→ staged rollout
→ telemetry and rollback
```

This is more credible for automotive and industrial scenarios than a public “download anything” app store.

---

## 11. References

Public sources used when drafting this document include:

- Unitree official open-source page: https://www.unitree.com/opensource
- Unitree G1-D platform page: https://www.unitree.com/G1-D
- SCMP report on Unitree humanoid app-store platform: https://www.scmp.com/tech/big-tech/article/3336380/chinas-unitree-teases-platform-allowing-users-control-robots-through-smartphones
- TechRadar report on Unitree robot app store and unclear monetization: https://www.techradar.com/ai-platforms-assistants/now-theres-a-robot-app-store-because-we-all-want-our-bots-to-kick-like-bruce-lee
