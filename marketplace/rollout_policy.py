"""ETD fleet rollout policy — staged deployment tracking for skill packages.

Rollout stages (in order):
    draft     — not yet cleared for any deployment
    canary    — approved for exactly 1 station (validation deployment)
    pilot     — approved for a defined set of N stations
    production — approved for unrestricted fleet deployment

State is stored in marketplace/rollout_state.json. Each entry records the
skill_id, version, stage, approved stations, and audit timestamps.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

STAGES = ('draft', 'canary', 'pilot', 'production')

_STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}


class RolloutPolicy:
    def __init__(self, state_path: Path):
        self._path = state_path
        self._state: dict = self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_stage(self, skill_id: str, version: str) -> str:
        """Return current rollout stage for a skill version (default: draft)."""
        return self._entry(skill_id, version).get('stage', 'draft')

    def set_stage(
        self,
        skill_id: str,
        version: str,
        stage: str,
        stations: Optional[list[str]] = None,
        operator_id: str = 'etd-cli',
    ) -> None:
        """Advance (or set) the rollout stage for a skill version.

        Raises ValueError if the requested stage would skip a stage or revert.
        For canary stage, exactly one station must be specified.
        For pilot stage, at least one station must be specified.
        """
        if stage not in STAGES:
            raise ValueError(f"Unknown stage '{stage}'. Valid: {STAGES}")

        current = self.get_stage(skill_id, version)
        current_idx = _STAGE_ORDER[current]
        new_idx = _STAGE_ORDER[stage]
        if new_idx < current_idx:
            raise ValueError(
                f"Cannot revert from '{current}' to '{stage}' for {skill_id}@{version}"
            )
        if new_idx > current_idx + 1:
            raise ValueError(
                f"Cannot skip from '{current}' to '{stage}' for {skill_id}@{version}. "
                f"Advance one stage at a time."
            )

        if stage == 'canary':
            if not stations or len(stations) != 1:
                raise ValueError("canary stage requires exactly 1 station")
        if stage == 'pilot':
            if not stations or len(stations) < 1:
                raise ValueError("pilot stage requires at least 1 station")

        key = f'{skill_id}@{version}'
        entry = self._entry(skill_id, version)
        entry.update({
            'skillId': skill_id,
            'version': version,
            'stage': stage,
            'approvedStations': stations or [],
            'updatedAt': _now(),
            'updatedBy': operator_id,
        })
        if 'createdAt' not in entry:
            entry['createdAt'] = _now()
        self._state['entries'][key] = entry
        self._save()

    def is_approved_for_station(self, skill_id: str, version: str, station_id: str) -> bool:
        """Return True if the skill/version is cleared to deploy to the given station."""
        entry = self._entry(skill_id, version)
        stage = entry.get('stage', 'draft')
        if stage == 'draft':
            return False
        if stage == 'production':
            return True
        return station_id in entry.get('approvedStations', [])

    def status(self, skill_id: Optional[str] = None) -> list[dict]:
        """Return all rollout entries, optionally filtered by skill_id."""
        entries = list(self._state.get('entries', {}).values())
        if skill_id:
            entries = [e for e in entries if e.get('skillId') == skill_id]
        return entries

    # ── Internal ──────────────────────────────────────────────────────────────

    def _entry(self, skill_id: str, version: str) -> dict:
        return self._state.setdefault('entries', {}).setdefault(
            f'{skill_id}@{version}', {}
        )

    def _load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text(encoding='utf-8'))
        return {'entries': {}}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False), encoding='utf-8'
        )


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
