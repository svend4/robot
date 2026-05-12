"""ETD audit log — structured JSON Lines event sink.

Every install check, revocation block, and validation failure is written as a
single JSON object on its own line to `logs/etd_audit.jsonl` (or a custom path).

Fields written for every event:
    event_type      : install_check | install_allowed | install_blocked
    skill_id        : str
    timestamp       : ISO-8601 UTC string
    result          : allowed | blocked
    reason          : install_allowed | skill_revoked | validation_failed |
                      entitlement_required | signature_invalid | skill_not_found
    validation_level: A | B | C | D | n/a
    station_id      : str or null
    operator_id     : str or null
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional


class AuditLog:
    """Append-only JSON Lines audit log."""

    def __init__(self, log_path: Optional[Path] = None):
        self._path = log_path
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        skill_id: str,
        result: str,
        reason: str,
        validation_level: str = 'n/a',
        station_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> None:
        if self._path is None:
            return
        entry = {
            'event_type': 'install_check',
            'skill_id': skill_id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'result': result,
            'reason': reason,
            'validation_level': validation_level,
            'station_id': station_id,
            'operator_id': operator_id,
        }
        with self._path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def read_entries(self) -> list[dict]:
        if self._path is None or not self._path.exists():
            return []
        entries = []
        for line in self._path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries
