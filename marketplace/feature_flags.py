"""ETD Skill Feature Flag System.

Boolean feature toggles for skill behaviour, resolvable at three levels:

    node-specific  >  skill-wide  >  global ('*')

Usage::

    from marketplace.feature_flags import FeatureFlagStore
    from pathlib import Path

    store = FeatureFlagStore(Path('flags'))

    # Global default — every skill gets this unless overridden
    store.set_flag('*', 'enable_force_feedback', enabled=False)

    # Override for one skill
    store.set_flag('etd.pickplace.basic', 'enable_force_feedback', enabled=True)

    # Further override for one node
    store.set_flag('etd.pickplace.basic', 'enable_force_feedback',
                   enabled=False, node_id='robot-maintenance-01')

    store.is_enabled('etd.pickplace.basic', 'enable_force_feedback')
    # → True  (skill-wide wins over global)

    store.is_enabled('etd.pickplace.basic', 'enable_force_feedback',
                     node_id='robot-maintenance-01')
    # → False  (node-specific wins)
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


# ── FlagEntry ─────────────────────────────────────────────────────────────────

@dataclass
class FlagEntry:
    """One feature flag assignment."""
    skill_id: str             # '*' for global
    flag_key: str
    enabled: bool
    node_id: Optional[str] = None   # None = all nodes for this skill
    description: str = ''
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'flag_key': self.flag_key,
            'enabled': self.enabled,
            'node_id': self.node_id,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'FlagEntry':
        return cls(
            skill_id=d['skill_id'],
            flag_key=d['flag_key'],
            enabled=d['enabled'],
            node_id=d.get('node_id'),
            description=d.get('description', ''),
            created_at=d.get('created_at', _utcnow()),
            updated_at=d.get('updated_at', _utcnow()),
        )


# ── FeatureFlagStore ──────────────────────────────────────────────────────────

def _make_key(skill_id: str, flag_key: str, node_id: Optional[str]) -> str:
    return f'{skill_id}::{flag_key}::{node_id or ""}'


class FeatureFlagStore:
    """JSON-backed store for feature flags.

    Storage layout (``feature_flags.json``)::

        {
          "<skill_id>::<flag_key>::<node_id|''>": { ...FlagEntry... },
          ...
        }

    Resolution order for :py:meth:`is_enabled`:

    1. ``(skill_id, flag_key, node_id)`` — node-specific for the skill
    2. ``(skill_id, flag_key, None)``    — skill-wide default
    3. ``('*', flag_key, None)``         — global default
    4. ``False``                         — absent flag defaults to disabled
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._flags: Dict[str, FlagEntry] = {}
        if (self._dir / 'feature_flags.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'feature_flags.json').read_text(encoding='utf-8')
            )
            self._flags = {k: FlagEntry.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._flags = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'feature_flags.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._flags.items()}, indent=2),
            encoding='utf-8',
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def set_flag(
        self,
        skill_id: str,
        flag_key: str,
        enabled: bool,
        node_id: Optional[str] = None,
        description: str = '',
    ) -> tuple[FlagEntry, bool]:
        """Create or update a flag.

        Returns ``(entry, created)`` where *created* is ``True`` if the flag
        did not previously exist.
        """
        key = _make_key(skill_id, flag_key, node_id)
        existing = self._flags.get(key)
        if existing is None:
            entry = FlagEntry(skill_id=skill_id, flag_key=flag_key,
                              enabled=enabled, node_id=node_id,
                              description=description)
            self._flags[key] = entry
            self._flush()
            return entry, True
        existing.enabled = enabled
        if description:
            existing.description = description
        existing.updated_at = _utcnow()
        self._flush()
        return existing, False

    def get_flag(
        self,
        skill_id: str,
        flag_key: str,
        node_id: Optional[str] = None,
    ) -> Optional[FlagEntry]:
        """Exact lookup — no resolution cascade."""
        return self._flags.get(_make_key(skill_id, flag_key, node_id))

    def remove_flag(
        self,
        skill_id: str,
        flag_key: str,
        node_id: Optional[str] = None,
    ) -> bool:
        """Remove an exact flag entry. Returns ``False`` if not found."""
        key = _make_key(skill_id, flag_key, node_id)
        if key not in self._flags:
            return False
        del self._flags[key]
        self._flush()
        return True

    def list_flags(self, skill_id: Optional[str] = None) -> List[FlagEntry]:
        """List all flags, optionally filtered by skill_id."""
        entries = list(self._flags.values())
        if skill_id is not None:
            entries = [e for e in entries if e.skill_id == skill_id]
        return entries

    @property
    def flag_count(self) -> int:
        return len(self._flags)

    # ── Resolution ────────────────────────────────────────────────────────────

    def is_enabled(
        self,
        skill_id: str,
        flag_key: str,
        node_id: Optional[str] = None,
    ) -> bool:
        """Resolve flag with cascade: node → skill → global → False."""
        if node_id is not None:
            entry = self.get_flag(skill_id, flag_key, node_id)
            if entry is not None:
                return entry.enabled
        entry = self.get_flag(skill_id, flag_key, None)
        if entry is not None:
            return entry.enabled
        entry = self.get_flag('*', flag_key, None)
        if entry is not None:
            return entry.enabled
        return False

    def resolve_source(
        self,
        skill_id: str,
        flag_key: str,
        node_id: Optional[str] = None,
    ) -> str:
        """Return which level resolved the flag: 'node', 'skill', 'global', or 'default'."""
        if node_id is not None and self.get_flag(skill_id, flag_key, node_id) is not None:
            return 'node'
        if self.get_flag(skill_id, flag_key, None) is not None:
            return 'skill'
        if self.get_flag('*', flag_key, None) is not None:
            return 'global'
        return 'default'
