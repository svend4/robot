"""ETD Skill Rating System.

Operators submit 1–5 star ratings (with optional comment) for skill packages.
Aggregate statistics (mean, count, distribution) are computed on demand.

Usage::

    from marketplace.skill_ratings import RatingStore
    from pathlib import Path

    store = RatingStore(Path('ratings'))
    store.add_rating('etd.pickplace.basic', 5, comment='Solid, reliable')
    store.add_rating('etd.pickplace.basic', 4, operator_id='ops-team')
    stats = store.get_stats('etd.pickplace.basic')
    # stats.mean → 4.5, stats.count → 2
"""
from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


# ── RatingEntry ───────────────────────────────────────────────────────────────

@dataclass
class RatingEntry:
    """One operator rating for a skill."""
    rating_id: str
    skill_id: str
    rating: int                  # 1–5 inclusive
    comment: str = ''
    operator_id: str = 'anonymous'
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rating_id': self.rating_id,
            'skill_id': self.skill_id,
            'rating': self.rating,
            'comment': self.comment,
            'operator_id': self.operator_id,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'RatingEntry':
        return cls(
            rating_id=d['rating_id'],
            skill_id=d['skill_id'],
            rating=d['rating'],
            comment=d.get('comment', ''),
            operator_id=d.get('operator_id', 'anonymous'),
            created_at=d.get('created_at', _utcnow()),
        )


# ── RatingStats ───────────────────────────────────────────────────────────────

@dataclass
class RatingStats:
    """Aggregate rating statistics for one skill."""
    skill_id: str
    count: int
    mean: float           # rounded to 2 d.p.
    distribution: Dict[int, int]   # {1: n, 2: n, 3: n, 4: n, 5: n}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'count': self.count,
            'mean': self.mean,
            'distribution': self.distribution,
        }


# ── RatingStore ───────────────────────────────────────────────────────────────

class RatingStore:
    """JSON-backed store for skill ratings.

    Storage layout (``ratings.json``)::

        {
          "<rating_id>": { ...RatingEntry... },
          ...
        }
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._ratings: Dict[str, RatingEntry] = {}
        if (self._dir / 'ratings.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'ratings.json').read_text(encoding='utf-8')
            )
            self._ratings = {k: RatingEntry.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._ratings = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'ratings.json').write_text(
            json.dumps(
                {k: v.to_dict() for k, v in self._ratings.items()},
                indent=2,
            ),
            encoding='utf-8',
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_rating(
        self,
        skill_id: str,
        rating: int,
        comment: str = '',
        operator_id: str = 'anonymous',
    ) -> RatingEntry:
        """Add a rating. Raises ``ValueError`` if rating is not 1–5."""
        if not 1 <= rating <= 5:
            raise ValueError(f'Rating must be 1–5, got {rating!r}')
        entry = RatingEntry(
            rating_id=str(uuid.uuid4()),
            skill_id=skill_id,
            rating=rating,
            comment=comment,
            operator_id=operator_id,
        )
        self._ratings[entry.rating_id] = entry
        self._flush()
        return entry

    def get_rating(self, rating_id: str) -> Optional[RatingEntry]:
        return self._ratings.get(rating_id)

    def list_ratings(self, skill_id: Optional[str] = None) -> List[RatingEntry]:
        """Return all ratings, optionally filtered to one skill."""
        entries = list(self._ratings.values())
        if skill_id is not None:
            entries = [e for e in entries if e.skill_id == skill_id]
        return entries

    def remove_rating(self, rating_id: str) -> bool:
        """Delete a rating. Returns ``False`` if not found."""
        if rating_id not in self._ratings:
            return False
        del self._ratings[rating_id]
        self._flush()
        return True

    def get_stats(self, skill_id: str) -> Optional[RatingStats]:
        """Compute aggregate stats for a skill. Returns ``None`` if no ratings."""
        entries = self.list_ratings(skill_id)
        if not entries:
            return None
        dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for e in entries:
            dist[e.rating] += 1
        mean = round(sum(e.rating for e in entries) / len(entries), 2)
        return RatingStats(
            skill_id=skill_id,
            count=len(entries),
            mean=mean,
            distribution=dist,
        )

    @property
    def rating_count(self) -> int:
        return len(self._ratings)

    def rated_skills(self) -> List[str]:
        """Return sorted list of skill IDs that have at least one rating."""
        return sorted({e.skill_id for e in self._ratings.values()})
