# Unitree Skill Store — Open vs Commercial Analysis

## Summary

Public reporting around Unitree's humanoid robot app store indicates that the platform is intended for uploading, sharing, downloading, and running robot actions, routines, and training datasets. It is described as an Action Library / Developer Platform / Applet Library workflow.

However, public information does not clearly establish whether all skills are free, paid, open-source, closed-source, or protected by DRM. The safest conclusion is that Unitree is building a distribution ecosystem, while the final commercial terms for third-party skills may vary or remain under beta-stage evolution.

## What appears publicly confirmed

1. Unitree has presented a humanoid robot app store / developer platform.
2. The platform centers on actions, robot routines, and training data.
3. Developers/users can upload and share actions or datasets.
4. Users can download/get actions and sync them into a robot/mobile app workflow.
5. The platform is linked conceptually to Unitree's G1 humanoid ecosystem.
6. Unitree separately maintains open-source resources, SDKs, datasets, and model/framework projects.

## What is not clearly confirmed publicly

1. Final pricing for third-party skills.
2. Marketplace commission rate.
3. Whether all actions are free or some are paid.
4. Whether paid commercial skills are already active in broad public distribution.
5. DRM/copy-protection details.
6. Whether source code for uploaded actions is exposed.
7. Whether commercial packages are robot-bound, account-bound, or cloud-bound.
8. Whether industrial certification or safety review is part of the public store.

## Likely categories in practice

A robot skill ecosystem usually needs several content categories:

### Free demo skills

Examples:

- dance routines;
- entertainment motions;
- simple gestures;
- public beta demos.

### Community-shared skills

Examples:

- user-created movements;
- training datasets;
- experimental routines.

### Open-source developer resources

Examples:

- SDKs;
- ROS packages;
- simulation assets;
- datasets;
- training frameworks.

### Paid commercial skills

Examples:

- specialized manipulation skills;
- professional performance routines;
- industrial templates;
- simulation-trained policies.

### Private enterprise skills

Examples:

- customer-specific manufacturing tasks;
- workcell-specific workflows;
- proprietary process know-how.

## Why this matters for ETD

ETD should not assume a single monetization model. The framework should support:

- free packages;
- open-source packages;
- free proprietary packages;
- paid packages;
- enterprise private packages;
- OEM-certified packages.

This makes ETD more flexible than a consumer-only app store.

## Consumer store vs industrial marketplace

Unitree's public examples appear to emphasize motion/action downloads and community sharing. ETD's industrial direction should emphasize validation, compatibility, policy control, and auditability.

| Dimension | Consumer-style robot app store | ETD industrial skill marketplace |
|---|---|---|
| Primary value | fun, demonstrations, rapid sharing | safe task deployment, factory integration |
| Main artifact | action/routine/dataset | validated skill package |
| Install flow | one-click app/mobile sync | validate, authorize, bind, deploy |
| Safety model | OEM/app constraints | explicit capability and station policy |
| Business model | free/share/reward/possibly paid | open/free/paid/private/certified |
| Target user | robot owner/developer | integrator, factory, OEM, robotics team |

## Recommended ETD position

ETD should be described as:

> A safety-conscious, industrial-oriented skill package and marketplace architecture inspired by the same macro trend as robot app stores, but focused on validation, permissions, station compatibility, and enterprise deployment.

## Documentation implication

When writing public documentation, do not claim that Unitree already has a mature paid marketplace unless directly verified. Instead write:

- Unitree has publicly shown a robot app-store direction.
- Public reports emphasize sharing/downloading robot actions and datasets.
- Unitree also has separate open-source resources.
- Pricing and commercial protection details are not clearly established publicly.
- ETD therefore defines a more explicit commercial/licensing/protection architecture.
