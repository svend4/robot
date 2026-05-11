"""Station profile loader and skill-compatibility checker.

A station profile describes the physical capabilities of a robot cell:
which skill families are allowed, available OEM services, payload limit,
and human-aware requirements.

Usage:
    from adapters.station_profile_loader import StationProfile, load_station_profile, check_skill_compatible

    profile = load_station_profile('station_profiles/assembly_station_a.json')
    result = check_skill_compatible(profile, skill_manifest, skill_family)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class StationCompatibilityResult:
    station_id: str
    skill_id: str
    compatible: bool
    reason: str
    missing_services: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class StationProfile:
    station_id: str
    allowed_skill_families: List[str]
    max_payload_kg: float
    requires_human_aware: bool
    available_services: List[str] = field(default_factory=list)
    platform: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'StationProfile':
        return cls(
            station_id=d['station_id'],
            allowed_skill_families=d.get('allowed_skill_families', []),
            max_payload_kg=float(d.get('max_payload_kg', 0)),
            requires_human_aware=bool(d.get('requires_human_aware', False)),
            available_services=d.get('available_services', []),
            platform=d.get('platform'),
            notes=d.get('notes'),
        )

    def allows_family(self, family: str) -> bool:
        return family in self.allowed_skill_families

    def to_dict(self) -> Dict[str, Any]:
        return {
            'station_id': self.station_id,
            'allowed_skill_families': self.allowed_skill_families,
            'max_payload_kg': self.max_payload_kg,
            'requires_human_aware': self.requires_human_aware,
            'available_services': self.available_services,
            'platform': self.platform,
            'notes': self.notes,
        }


def load_station_profile(path: str | Path) -> StationProfile:
    return StationProfile.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


def load_all_profiles(station_profiles_dir: str | Path) -> Dict[str, StationProfile]:
    profiles: Dict[str, StationProfile] = {}
    for f in sorted(Path(station_profiles_dir).glob('*.json')):
        p = load_station_profile(f)
        profiles[p.station_id] = p
    return profiles


def check_skill_compatible(
    profile: StationProfile,
    skill_family: str,
    payload_kg: float,
    requires_human_aware: bool,
    required_services: List[str],
    skill_id: str = '',
) -> StationCompatibilityResult:
    """Check whether a skill is compatible with a station profile.

    Checks:
    1. Family is in station's allowed list
    2. Payload is within station max
    3. If skill requires human-aware mode, station must support it
    4. All required services are available at the station
    """
    warnings: List[str] = []
    missing_services: List[str] = []

    if not profile.allows_family(skill_family):
        return StationCompatibilityResult(
            station_id=profile.station_id, skill_id=skill_id,
            compatible=False,
            reason=f'family_{skill_family}_not_allowed_at_station',
        )

    if payload_kg > profile.max_payload_kg:
        return StationCompatibilityResult(
            station_id=profile.station_id, skill_id=skill_id,
            compatible=False,
            reason=f'payload_exceeds_station_limit_{profile.max_payload_kg}kg',
        )

    if requires_human_aware and not profile.requires_human_aware:
        warnings.append('skill_requires_human_aware_but_station_does_not_enforce_it')

    if profile.available_services:
        station_svcs = set(profile.available_services)
        missing_services = [s for s in required_services if s not in station_svcs]
        if missing_services:
            return StationCompatibilityResult(
                station_id=profile.station_id, skill_id=skill_id,
                compatible=False,
                reason='missing_services_at_station',
                missing_services=missing_services,
            )

    return StationCompatibilityResult(
        station_id=profile.station_id, skill_id=skill_id,
        compatible=True, reason='station_compatible',
        warnings=warnings,
    )


# Legacy helpers kept for backward compatibility
def is_skill_allowed(profile: dict | StationProfile, family: str) -> bool:
    if isinstance(profile, dict):
        return family in profile.get('allowed_skill_families', [])
    return profile.allows_family(family)
