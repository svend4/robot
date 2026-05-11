# Unitree Skill Store: Open vs Commercial Notes

## Purpose

This note summarizes what is publicly visible about Unitree's humanoid robot app-store / developer-platform direction and compares it with the ETD marketplace model.

This is not legal advice and not an official Unitree policy interpretation. It is a product and architecture analysis based on public reporting and official Unitree open-source / platform pages.

---

## 1. What public reporting says

Public reports describe Unitree's humanoid robot app-store / developer platform as a place where users and developers can:

- access robot functions through a smartphone;
- download action sequences or motion routines;
- upload and share datasets;
- upload and share action sequences;
- use example routines such as Bruce Lee, Twist Dance, and Funny Actions;
- synchronize downloaded actions to an applet/action library.

Some reports describe it as public beta or early-stage.

---

## 2. Is it open-source?

The answer appears mixed.

Unitree maintains official open-source resources, including SDKs, simulation tools, datasets, and embodied-AI/model training resources. Unitree's official open-source page lists projects and resources such as:

- SDKs;
- ROS-related tools;
- simulation tools;
- manipulation datasets;
- imitation-learning resources;
- VLA / WMA model-related resources.

However, this does not automatically mean every app-store action, routine, model, or marketplace skill is open-source.

A likely distinction is:

```text
Unitree open-source ecosystem: SDKs, datasets, models, frameworks, examples
Unitree app-store content: downloadable skills/actions/datasets, possibly mixed visibility
```

In other words: some components are open-source, but the store itself should not be assumed to be entirely open-source.

---

## 3. Are the skills paid?

Based on the public information reviewed for this prototype, there is no clearly documented mature paid-skill marketplace model for the Unitree humanoid app store.

Public reports mention:

- upload/share/download behavior;
- developer participation;
- developer rewards for exceptional contributors;
- unclear or not-yet-defined monetization.

Therefore, the safest conclusion is:

> At the current public-information level, Unitree's store looks more like an early community/developer sharing platform with possible rewards, not yet a fully documented commercial paid marketplace like Apple's App Store.

This may change as the platform matures.

---

## 4. Possible future Unitree commercial directions

Unitree or similar platforms could later add:

- paid skills;
- subscriptions;
- premium datasets;
- paid training models;
- developer revenue share;
- enterprise packages;
- robot-specific skill licenses;
- paid certification;
- cloud-hosted skill execution.

But this should be treated as a plausible evolution, not as confirmed present fact unless official marketplace terms state it.

---

## 5. How ETD differs

ETD should not copy only the consumer-style “download a motion routine” model.

ETD should focus on industrial-grade skill distribution:

```text
Unitree-style early marketplace:
  share / download actions and datasets
  consumer and developer friendly
  examples include entertainment and martial arts routines

ETD-style industrial marketplace:
  signed skill packages
  schema validation
  capability validation
  station compatibility
  runtime compatibility
  failure scenarios
  rollback
  telemetry
  licensing
  enterprise deployment
```

---

## 6. Commercial ETD marketplace recommendation

The ETD marketplace should support all of these visibility and monetization modes:

| Mode | Source visibility | Price | Best for |
|---|---|---|---|
| Community open | open-source | free | education, research, demos |
| Free proprietary | closed | free | vendor demos |
| Paid skill | closed or source-available | paid | specialized skills |
| Enterprise skill | closed/source-available | contract | factory deployment |
| Certified skill | closed/source-available | premium | higher-trust industrial use |

---

## 7. Protection strategy for commercial ETD skills

If ETD skills are sold commercially, protection should not rely only on hiding code. A serious marketplace should combine:

- signed packages;
- license tokens;
- hardware/station binding;
- encrypted payloads;
- source-visible safety metadata;
- capability sandboxing;
- audit logs;
- marketplace revocation;
- staged rollout;
- support contracts.

This is especially important because robot skills affect physical machines and may create safety or property-damage risk.

---

## 8. Product implication

Unitree's move validates the direction: robot capabilities are becoming downloadable and ecosystem-driven.

ETD's opportunity is to define the stricter industrial version:

> a robot skill store where every skill is a validated, signed, constrained, station-aware package rather than only a downloadable movement routine.

---

## 9. References

Public sources used when drafting this note include:

- Unitree official open-source page: https://www.unitree.com/opensource
- Unitree G1-D platform page: https://www.unitree.com/G1-D
- SCMP report on Unitree humanoid app-store platform: https://www.scmp.com/tech/big-tech/article/3336380/chinas-unitree-teases-platform-allowing-users-control-robots-through-smartphones
- TechRadar report on Unitree robot app store and unclear monetization: https://www.techradar.com/ai-platforms-assistants/now-theres-a-robot-app-store-because-we-all-want-our-bots-to-kick-like-bruce-lee
- RoboHorizon report on Unitree developer platform and developer rewards: https://robohorizon.com/en-us/news/2025/12/unitree-launches-first-app-store-for-humanoid-robots/
