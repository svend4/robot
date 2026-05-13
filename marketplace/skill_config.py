"""ETD Skill Configuration Store.

Provides per-skill runtime configuration with three scope levels:

``*``               — default (applies to all stations and nodes)
``station:<id>``    — overrides the default for one station
``node:<id>``       — overrides the default for one node

``get_effective()`` merges in priority order:
    node override  >  station override  >  default

Architecture
------------
::

    SkillConfigEntry  ──▶  ConfigStore  ──▶  SkillConfigEntry
                                │             effective dict
                          config_store.json
                          (JSON-backed)

Usage::

    from marketplace.skill_config import ConfigStore
    from pathlib import Path

    store = ConfigStore(Path('config'))
    store.set('etd.pickplace.basic', '*', {'speed_pct': 80, 'retries': 3})
    store.set('etd.pickplace.basic', 'station:alpha',
              {'speed_pct': 50})  # alpha station is slower

    effective = store.get_effective(
        'etd.pickplace.basic', station_id='alpha'
    )
    # → {'speed_pct': 50, 'retries': 3}
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _make_scope_key(skill_id: str, scope: str) -> str:
    return f'{skill_id}::{scope}'


# ── SkillConfigEntry ──────────────────────────────────────────────────────────

@dataclass
class SkillConfigEntry:
    """One configuration record: a skill + scope combination."""
    skill_id: str
    scope: str                  # '*' | 'station:<id>' | 'node:<id>'
    values: Dict[str, Any]
    version: int = 1
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'scope': self.scope,
            'values': self.values,
            'version': self.version,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SkillConfigEntry':
        return cls(
            skill_id=d['skill_id'],
            scope=d['scope'],
            values=dict(d.get('values', {})),
            version=int(d.get('version', 1)),
            created_at=d.get('created_at', _utcnow()),
            updated_at=d.get('updated_at', _utcnow()),
        )


# ── ConfigStore ───────────────────────────────────────────────────────────────

class ConfigStore:
    """JSON-backed store for skill configuration entries.

    Scope format
    ------------
    ``'*'``               — default applies everywhere
    ``'station:<id>'``    — station-specific override
    ``'node:<id>'``       — node-specific override
    """

    SCOPE_DEFAULT = '*'

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._entries: Dict[str, SkillConfigEntry] = {}
        path = self._dir / 'skill_config.json'
        if path.exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'skill_config.json').read_text(encoding='utf-8')
            )
            self._entries = {
                k: SkillConfigEntry.from_dict(v) for k, v in raw.items()
            }
        except Exception:
            self._entries = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'skill_config.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._entries.items()},
                       indent=2),
            encoding='utf-8',
        )

    # ── scope helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def station_scope(station_id: str) -> str:
        return f'station:{station_id}'

    @staticmethod
    def node_scope(node_id: str) -> str:
        return f'node:{node_id}'

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def set(
        self, skill_id: str, scope: str, values: Dict[str, Any],
    ) -> SkillConfigEntry:
        """Create or replace the config entry for (skill_id, scope).

        Increments the version on update.
        """
        key = _make_scope_key(skill_id, scope)
        existing = self._entries.get(key)
        if existing is None:
            entry = SkillConfigEntry(skill_id=skill_id, scope=scope,
                                     values=values)
        else:
            entry = SkillConfigEntry(
                skill_id=skill_id,
                scope=scope,
                values=values,
                version=existing.version + 1,
                created_at=existing.created_at,
            )
        self._entries[key] = entry
        self._flush()
        return entry

    def get(self, skill_id: str, scope: str) -> Optional[SkillConfigEntry]:
        """Return the entry for (skill_id, scope), or None."""
        return self._entries.get(_make_scope_key(skill_id, scope))

    def remove(self, skill_id: str, scope: str) -> bool:
        """Remove one (skill_id, scope) entry. Returns False if not found."""
        key = _make_scope_key(skill_id, scope)
        if key not in self._entries:
            return False
        del self._entries[key]
        self._flush()
        return True

    def remove_skill(self, skill_id: str) -> int:
        """Remove ALL entries for a skill. Returns the count removed."""
        keys = [k for k, v in self._entries.items()
                if v.skill_id == skill_id]
        for k in keys:
            del self._entries[k]
        if keys:
            self._flush()
        return len(keys)

    def list_entries(
        self, skill_id: Optional[str] = None,
    ) -> List[SkillConfigEntry]:
        """List all entries, optionally filtered by skill_id."""
        entries = list(self._entries.values())
        if skill_id:
            entries = [e for e in entries if e.skill_id == skill_id]
        return entries

    def list_skills(self) -> List[str]:
        """Return the distinct skill IDs that have at least one config entry."""
        return list({e.skill_id for e in self._entries.values()})

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    # ── effective config ──────────────────────────────────────────────────────

    def get_effective(
        self,
        skill_id: str,
        station_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the merged effective configuration.

        Merge order (later wins):
        1. Default (scope='*')
        2. Station override (scope='station:<station_id>')
        3. Node override (scope='node:<node_id>')
        """
        effective: Dict[str, Any] = {}

        default = self.get(skill_id, self.SCOPE_DEFAULT)
        if default:
            effective.update(default.values)

        if station_id:
            station = self.get(skill_id, self.station_scope(station_id))
            if station:
                effective.update(station.values)

        if node_id:
            node = self.get(skill_id, self.node_scope(node_id))
            if node:
                effective.update(node.values)

        return effective
