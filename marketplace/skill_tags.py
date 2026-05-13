"""ETD Skill Tag System.

Provides user-defined tags that can be applied to skill IDs, enabling
grouping, filtering, and querying by arbitrary labels.

Architecture
------------
::

    TagEntry  ──▶  TagStore  ──▶  TagEntry
                       │          skill → [tag_ids]
                  tags.json        tag  → [skill_ids]
                  (JSON-backed)

Usage::

    from marketplace.skill_tags import TagStore
    from pathlib import Path

    store = TagStore(Path('tags'))
    store.create_tag('safety-critical', color='red',
                     description='Requires human oversight')
    store.create_tag('maintenance', color='yellow')

    store.tag_skill('etd.pickplace.basic', 'safety-critical')
    store.tag_skill('etd.weld.spot', 'safety-critical')
    store.tag_skill('etd.calibrate.arm', 'maintenance')

    critical = store.get_skills_by_tag('safety-critical')
    # → ['etd.pickplace.basic', 'etd.weld.spot']
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


# ── TagEntry ──────────────────────────────────────────────────────────────────

@dataclass
class TagEntry:
    """Metadata for one tag."""
    tag_id: str
    color: Optional[str] = None        # optional display color hint
    description: str = ''
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tag_id': self.tag_id,
            'color': self.color,
            'description': self.description,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'TagEntry':
        return cls(
            tag_id=d['tag_id'],
            color=d.get('color'),
            description=d.get('description', ''),
            created_at=d.get('created_at', _utcnow()),
        )


# ── TagStore ──────────────────────────────────────────────────────────────────

class TagStore:
    """JSON-backed store for tag definitions and skill↔tag mappings.

    Internal layout of ``tags.json``::

        {
          "tags": { "<tag_id>": { ... TagEntry ... } },
          "mappings": { "<skill_id>": ["<tag_id>", ...] }
        }
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._tags: Dict[str, TagEntry] = {}
        self._mappings: Dict[str, Set[str]] = {}  # skill_id → set of tag_ids
        if (self._dir / 'tags.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'tags.json').read_text(encoding='utf-8')
            )
            self._tags = {
                k: TagEntry.from_dict(v)
                for k, v in raw.get('tags', {}).items()
            }
            self._mappings = {
                k: set(v)
                for k, v in raw.get('mappings', {}).items()
            }
        except Exception:
            self._tags = {}
            self._mappings = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'tags.json').write_text(
            json.dumps({
                'tags': {k: v.to_dict() for k, v in self._tags.items()},
                'mappings': {k: sorted(v)
                             for k, v in self._mappings.items() if v},
            }, indent=2),
            encoding='utf-8',
        )

    # ── tag CRUD ──────────────────────────────────────────────────────────────

    def create_tag(
        self,
        tag_id: str,
        color: Optional[str] = None,
        description: str = '',
    ) -> TagEntry:
        """Create a new tag. Returns the existing entry if already present."""
        if tag_id in self._tags:
            return self._tags[tag_id]
        entry = TagEntry(tag_id=tag_id, color=color, description=description)
        self._tags[tag_id] = entry
        self._flush()
        return entry

    def update_tag(
        self,
        tag_id: str,
        color: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[TagEntry]:
        """Update an existing tag's color/description. Returns None if unknown."""
        entry = self._tags.get(tag_id)
        if entry is None:
            return None
        if color is not None:
            entry.color = color
        if description is not None:
            entry.description = description
        self._flush()
        return entry

    def get_tag(self, tag_id: str) -> Optional[TagEntry]:
        return self._tags.get(tag_id)

    def delete_tag(self, tag_id: str) -> bool:
        """Delete a tag and remove it from all skill mappings."""
        if tag_id not in self._tags:
            return False
        del self._tags[tag_id]
        for tags in self._mappings.values():
            tags.discard(tag_id)
        self._flush()
        return True

    def list_tags(self) -> List[TagEntry]:
        return list(self._tags.values())

    @property
    def tag_count(self) -> int:
        return len(self._tags)

    # ── skill ↔ tag mappings ──────────────────────────────────────────────────

    def tag_skill(self, skill_id: str, tag_id: str) -> bool:
        """Apply *tag_id* to *skill_id*.

        Returns ``True`` if newly added, ``False`` if already present.
        Raises ``KeyError`` if the tag does not exist.
        """
        if tag_id not in self._tags:
            raise KeyError(f'Unknown tag: {tag_id!r}')
        tags = self._mappings.setdefault(skill_id, set())
        if tag_id in tags:
            return False
        tags.add(tag_id)
        self._flush()
        return True

    def untag_skill(self, skill_id: str, tag_id: str) -> bool:
        """Remove *tag_id* from *skill_id*.

        Returns ``True`` if removed, ``False`` if the mapping did not exist.
        """
        tags = self._mappings.get(skill_id)
        if not tags or tag_id not in tags:
            return False
        tags.discard(tag_id)
        self._flush()
        return True

    def get_skill_tags(self, skill_id: str) -> List[str]:
        """Return tag IDs applied to *skill_id* (sorted)."""
        return sorted(self._mappings.get(skill_id, set()))

    def get_skills_by_tag(self, tag_id: str) -> List[str]:
        """Return skill IDs that have *tag_id* applied (sorted)."""
        return sorted(
            skill_id
            for skill_id, tags in self._mappings.items()
            if tag_id in tags
        )

    def list_skill_tags(self) -> Dict[str, List[str]]:
        """Return a dict of {skill_id: [tag_ids]} for all mapped skills."""
        return {
            skill_id: sorted(tags)
            for skill_id, tags in self._mappings.items()
            if tags
        }

    def tagged_skill_count(self) -> int:
        """Number of distinct skill IDs that have at least one tag."""
        return sum(1 for tags in self._mappings.values() if tags)
