"""ETD Operator Notes System.

Free-text annotations that operators can attach to any subject key
(skill ID, node ID, station ID, etc.).  Each note carries a category
(info / warning / issue / runbook), an author, and timestamps.

Usage::

    from marketplace.operator_notes import NoteStore
    from pathlib import Path

    store = NoteStore(Path('notes'))
    store.add_note('etd.hyundai.wia_welding', 'Torch calibration due Q3',
                   category='runbook', author='ops-team')
    store.add_note('robot-01', 'Wrist joint shows intermittent slip',
                   category='issue', author='field-eng')

    issues = store.list_notes(category='issue')
    skill_notes = store.list_notes(subject='etd.hyundai.wia_welding')
"""
from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_CATEGORIES = {'info', 'warning', 'issue', 'runbook'}


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


# ── OperatorNote ──────────────────────────────────────────────────────────────

@dataclass
class OperatorNote:
    """One operator note attached to a subject."""
    note_id: str
    subject: str          # skill_id, node_id, or any free-form key
    text: str
    category: str = 'info'        # info | warning | issue | runbook
    author: str = 'anonymous'
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'note_id': self.note_id,
            'subject': self.subject,
            'text': self.text,
            'category': self.category,
            'author': self.author,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'OperatorNote':
        return cls(
            note_id=d['note_id'],
            subject=d['subject'],
            text=d['text'],
            category=d.get('category', 'info'),
            author=d.get('author', 'anonymous'),
            created_at=d.get('created_at', _utcnow()),
            updated_at=d.get('updated_at', _utcnow()),
        )


# ── NoteStore ─────────────────────────────────────────────────────────────────

class NoteStore:
    """JSON-backed store for operator notes.

    Storage: ``notes.json`` — flat dict keyed by ``note_id``.
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._notes: Dict[str, OperatorNote] = {}
        if (self._dir / 'notes.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'notes.json').read_text(encoding='utf-8')
            )
            self._notes = {k: OperatorNote.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._notes = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'notes.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._notes.items()}, indent=2),
            encoding='utf-8',
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_note(
        self,
        subject: str,
        text: str,
        category: str = 'info',
        author: str = 'anonymous',
    ) -> OperatorNote:
        """Add a note. Raises ``ValueError`` for unknown category."""
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f'Unknown category {category!r}. Valid: {sorted(VALID_CATEGORIES)}'
            )
        note = OperatorNote(
            note_id=str(uuid.uuid4()),
            subject=subject,
            text=text,
            category=category,
            author=author,
        )
        self._notes[note.note_id] = note
        self._flush()
        return note

    def get_note(self, note_id: str) -> Optional[OperatorNote]:
        return self._notes.get(note_id)

    def update_note(
        self,
        note_id: str,
        text: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[OperatorNote]:
        """Update text and/or category. Returns ``None`` if note not found."""
        note = self._notes.get(note_id)
        if note is None:
            return None
        if category is not None:
            if category not in VALID_CATEGORIES:
                raise ValueError(
                    f'Unknown category {category!r}. Valid: {sorted(VALID_CATEGORIES)}'
                )
            note.category = category
        if text is not None:
            note.text = text
        note.updated_at = _utcnow()
        self._flush()
        return note

    def remove_note(self, note_id: str) -> bool:
        """Remove a note. Returns ``False`` if not found."""
        if note_id not in self._notes:
            return False
        del self._notes[note_id]
        self._flush()
        return True

    def list_notes(
        self,
        subject: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[OperatorNote]:
        """Return notes, optionally filtered by subject and/or category."""
        results = list(self._notes.values())
        if subject is not None:
            results = [n for n in results if n.subject == subject]
        if category is not None:
            results = [n for n in results if n.category == category]
        return results

    def subjects(self) -> List[str]:
        """Return a sorted list of distinct subjects that have notes."""
        return sorted({n.subject for n in self._notes.values()})

    @property
    def note_count(self) -> int:
        return len(self._notes)
