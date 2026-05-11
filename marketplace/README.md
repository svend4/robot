# ETD Marketplace Layer

This directory contains marketplace-level metadata for ETD skill packages.

## Files

- `skill_store_index.json` — catalog of available skill packages.
- `marketplace_policy.json` — installation, review, licensing, and protection rules.
- `license_profiles.json` — allowed commercial/open-source package models.

## License model

The marketplace supports both open and commercial packages:

- `open_source`
- `community_free`
- `commercial_closed_source`
- `commercial_source_available`
- `enterprise_private`

The v0.1 examples are reference/open packages. Future commercial packages should add signing, entitlement checks, and optional encrypted proprietary payloads.
