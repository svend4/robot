"""ETD Skill Maintenance Window Scheduler.

Named time-bounded windows during which skill executions should be blocked.
Windows can target a specific skill ID (or ``'*'`` for all skills) and
optionally a specific node.

Usage::

    from marketplace.maintenance import MaintenanceStore
    from pathlib import Path

    store = MaintenanceStore(Path('maintenance'))

    store.add_window(
        'etd.hyundai.wia_welding',
        start_at='2026-06-01T02:00:00+00:00',
        end_at='2026-06-01T04:00:00+00:00',
        reason='Firmware upgrade',
    )

    store.is_in_maintenance('etd.hyundai.wia_welding')
    # → True if called during the window, False otherwise
"""
from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _utcnow_str() -> str:
    return _utcnow().isoformat(timespec='seconds')


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts)


# ── MaintenanceWindow ─────────────────────────────────────────────────────────

@dataclass
class MaintenanceWindow:
    """One scheduled maintenance window."""
    window_id: str
    skill_id: str             # '*' = all skills
    start_at: str             # ISO 8601
    end_at: str               # ISO 8601; must be > start_at
    reason: str = ''
    node_id: Optional[str] = None   # None = all nodes
    created_by: str = 'system'
    created_at: str = field(default_factory=_utcnow_str)

    def is_active(self, now: Optional[datetime.datetime] = None) -> bool:
        """Return True if *now* falls within [start_at, end_at)."""
        t = now or _utcnow()
        return _parse(self.start_at) <= t < _parse(self.end_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'window_id': self.window_id,
            'skill_id': self.skill_id,
            'start_at': self.start_at,
            'end_at': self.end_at,
            'reason': self.reason,
            'node_id': self.node_id,
            'created_by': self.created_by,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'MaintenanceWindow':
        return cls(
            window_id=d['window_id'],
            skill_id=d['skill_id'],
            start_at=d['start_at'],
            end_at=d['end_at'],
            reason=d.get('reason', ''),
            node_id=d.get('node_id'),
            created_by=d.get('created_by', 'system'),
            created_at=d.get('created_at', _utcnow_str()),
        )


# ── MaintenanceStore ──────────────────────────────────────────────────────────

class MaintenanceStore:
    """JSON-backed store for maintenance windows.

    Storage: ``maintenance.json`` — flat dict keyed by ``window_id``.
    """

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._windows: Dict[str, MaintenanceWindow] = {}
        if (self._dir / 'maintenance.json').exists():
            self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(
                (self._dir / 'maintenance.json').read_text(encoding='utf-8')
            )
            self._windows = {k: MaintenanceWindow.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._windows = {}

    def _flush(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / 'maintenance.json').write_text(
            json.dumps({k: v.to_dict() for k, v in self._windows.items()}, indent=2),
            encoding='utf-8',
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_window(
        self,
        skill_id: str,
        start_at: str,
        end_at: str,
        reason: str = '',
        node_id: Optional[str] = None,
        created_by: str = 'system',
    ) -> MaintenanceWindow:
        """Schedule a maintenance window.

        Raises ``ValueError`` if ``end_at`` is not after ``start_at``.
        """
        if _parse(end_at) <= _parse(start_at):
            raise ValueError(f'end_at must be after start_at: {end_at!r} <= {start_at!r}')
        window = MaintenanceWindow(
            window_id=str(uuid.uuid4()),
            skill_id=skill_id,
            start_at=start_at,
            end_at=end_at,
            reason=reason,
            node_id=node_id,
            created_by=created_by,
        )
        self._windows[window.window_id] = window
        self._flush()
        return window

    def get_window(self, window_id: str) -> Optional[MaintenanceWindow]:
        return self._windows.get(window_id)

    def remove_window(self, window_id: str) -> bool:
        if window_id not in self._windows:
            return False
        del self._windows[window_id]
        self._flush()
        return True

    def list_windows(
        self,
        skill_id: Optional[str] = None,
        active_only: bool = False,
        _now: Optional[datetime.datetime] = None,
    ) -> List[MaintenanceWindow]:
        """List windows, optionally filtered by skill_id and/or active state."""
        results = list(self._windows.values())
        if skill_id is not None:
            results = [w for w in results if w.skill_id == skill_id]
        if active_only:
            results = [w for w in results if w.is_active(_now)]
        return results

    def active_windows(
        self,
        _now: Optional[datetime.datetime] = None,
    ) -> List[MaintenanceWindow]:
        """Return all currently active windows."""
        return self.list_windows(active_only=True, _now=_now)

    @property
    def window_count(self) -> int:
        return len(self._windows)

    # ── Maintenance check ────────────────────────────────────────────────────

    def is_in_maintenance(
        self,
        skill_id: str,
        node_id: Optional[str] = None,
        _now: Optional[datetime.datetime] = None,
    ) -> bool:
        """Return True if *skill_id* (on optional *node_id*) is currently in maintenance.

        Matching rules (all must hold for a window to match):
        - ``window.skill_id == skill_id`` OR ``window.skill_id == '*'``
        - ``window.node_id is None`` OR ``window.node_id == node_id``
        - window is currently active (start_at ≤ now < end_at)
        """
        now = _now or _utcnow()
        for w in self._windows.values():
            if not w.is_active(now):
                continue
            skill_match = (w.skill_id == '*' or w.skill_id == skill_id)
            node_match = (w.node_id is None or w.node_id == node_id)
            if skill_match and node_match:
                return True
        return False
