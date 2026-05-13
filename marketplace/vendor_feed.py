"""ETD Multi-vendor Index — aggregate skill packages from signed publisher feeds.

Each *vendor feed* is a signed JSON document published by a skill vendor. The
``VendorFeedManager`` collects multiple feeds, verifies their Ed25519 signatures,
deduplicates entries, and exposes a unified view of available skills — similar to
a Linux package repository aggregator.

Feed wire format::

    {
        "feedId":    "hyundai-official",
        "name":      "Hyundai Robotics Official Feed",
        "version":   "1.0.0",
        "entries":   [ ... skill index entries ... ],
        "signature": "<base64url-Ed25519-sig-over-canonical-entries-JSON>"
    }

The signature covers ``json.dumps(entries, sort_keys=True)``.

Usage::

    from marketplace.vendor_feed import (
        VendorFeed, VendorFeedManager, create_feed_payload, verify_feed_signature
    )
    from nacl.signing import SigningKey

    # Publisher side — create a signed feed
    key = SigningKey.generate()
    payload = create_feed_payload(
        feed_id='acme-skills',
        name='ACME Robotics Feed',
        entries=my_entries,
        signing_key=key,
    )

    # Consumer side — load and aggregate
    mgr = VendorFeedManager()
    mgr.register_feed(VendorFeed(
        feed_id='acme-skills',
        name='ACME Robotics Feed',
        public_key_hex=key.verify_key.encode().hex(),
    ))
    record = mgr.load_feed('acme-skills', payload)
    assert record.verified

    skill = mgr.find_skill('acme.pickplace.v2', runtime_version='0.5.0')
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from marketplace.skill_store import StoreEntry
from marketplace.version_negotiator import best_version, sort_versions


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class VendorFeed:
    """Registration record for a vendor feed (no data yet — just identity + key)."""
    feed_id: str
    name: str
    public_key_hex: str  # hex-encoded Ed25519 verify key


@dataclass
class FeedRecord:
    """Loaded + (optionally) verified data from a single vendor feed."""
    feed_id: str
    feed_name: str
    feed_version: str
    entries: List[StoreEntry]
    verified: bool
    error: str = ""

    @property
    def entry_count(self) -> int:
        return len(self.entries)


# ── Signature helpers ─────────────────────────────────────────────────────────

def create_feed_payload(
    feed_id: str,
    name: str,
    entries: List[Dict[str, Any]],
    signing_key: Any,  # nacl.signing.SigningKey
    feed_version: str = "1.0.0",
) -> Dict[str, Any]:
    """Create a signed feed payload ready to publish or persist as JSON.

    Parameters
    ----------
    signing_key:
        A ``nacl.signing.SigningKey`` instance.

    Returns
    -------
    dict with keys ``feedId``, ``name``, ``version``, ``entries``, ``signature``.
    """
    canonical = json.dumps(entries, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sig_bytes = signing_key.sign(canonical).signature
    sig_b64 = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()
    return {
        "feedId": feed_id,
        "name": name,
        "version": feed_version,
        "entries": entries,
        "signature": sig_b64,
    }


def verify_feed_signature(
    payload: Dict[str, Any], public_key_hex: str
) -> Tuple[bool, str]:
    """Verify the Ed25519 ``signature`` field in *payload*.

    Returns
    -------
    ``(True, "signature_valid")`` or ``(False, reason_string)``.

    Reasons: ``missing_signature``, ``signature_invalid``, ``key_error``,
    ``verification_error``, ``nacl_not_available`` (soft-pass when PyNaCl absent).
    """
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
    except ImportError:
        return True, "nacl_not_available"

    sig_b64 = payload.get("signature", "")
    if not sig_b64:
        return False, "missing_signature"

    entries = payload.get("entries", [])
    canonical = json.dumps(entries, sort_keys=True, ensure_ascii=False).encode("utf-8")

    try:
        padding = "=" * (-len(sig_b64) % 4)
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + padding)
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        vk.verify(canonical, sig_bytes)
        return True, "signature_valid"
    except BadSignatureError:
        return False, "signature_invalid"
    except ValueError as exc:
        return False, f"key_error: {exc}"
    except Exception as exc:
        return False, f"verification_error: {exc}"


# ── Feed manager ──────────────────────────────────────────────────────────────

class VendorFeedManager:
    """Aggregate skill entries from multiple signed vendor feeds.

    Workflow::

        mgr = VendorFeedManager()

        # 1. Register known publisher identities
        mgr.register_feed(VendorFeed('hyundai', 'Hyundai Robotics', pubkey_hex))

        # 2. Load feed data (from network/file/cache)
        record = mgr.load_feed('hyundai', hyundai_feed_payload)
        assert record.verified

        # 3. Query the aggregated index
        skill = mgr.find_skill('etd.hyundai.wia_welding', '0.5.0')
    """

    def __init__(self) -> None:
        self._feeds: Dict[str, VendorFeed] = {}
        self._records: Dict[str, FeedRecord] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register_feed(self, feed: VendorFeed) -> None:
        """Register a vendor feed identity (does not load data yet)."""
        self._feeds[feed.feed_id] = feed

    def unregister_feed(self, feed_id: str) -> None:
        """Remove a feed registration and any loaded data for it."""
        self._feeds.pop(feed_id, None)
        self._records.pop(feed_id, None)

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_feed(self, feed_id: str, payload: Dict[str, Any]) -> FeedRecord:
        """Load and verify a feed payload dict.

        Parameters
        ----------
        feed_id:
            Must match a previously registered feed.
        payload:
            The feed JSON document as a Python dict.

        Raises
        ------
        KeyError
            If *feed_id* was not registered.
        """
        if feed_id not in self._feeds:
            raise KeyError(f"feed {feed_id!r} is not registered; call register_feed() first")
        feed = self._feeds[feed_id]
        verified, reason = verify_feed_signature(payload, feed.public_key_hex)
        entries: List[StoreEntry] = []
        parse_errors: List[str] = []
        for raw in payload.get("entries", []):
            try:
                entries.append(StoreEntry.from_dict(raw))
            except Exception as exc:
                parse_errors.append(str(exc))
        record = FeedRecord(
            feed_id=feed_id,
            feed_name=payload.get("name", feed.name),
            feed_version=payload.get("version", "0.0.0"),
            entries=entries,
            verified=verified,
            error="" if verified else reason,
        )
        if parse_errors:
            record.error = (record.error + "; parse_errors: " + "; ".join(parse_errors)).lstrip("; ")
        self._records[feed_id] = record
        return record

    def load_feed_from_file(self, path: Path) -> FeedRecord:
        """Load a feed from a JSON file.

        The ``feedId`` field in the JSON must match a registered feed, or it is
        used as the feed_id automatically if that key is not yet registered.
        """
        p = path if isinstance(path, Path) else Path(path)
        payload = json.loads(p.read_text(encoding="utf-8"))
        feed_id = payload.get("feedId", p.stem)
        if feed_id not in self._feeds:
            raise KeyError(
                f"feed {feed_id!r} from file {p.name!r} is not registered; "
                "call register_feed() first"
            )
        return self.load_feed(feed_id, payload)

    # ── Queries ───────────────────────────────────────────────────────────────

    def aggregate(self) -> List[StoreEntry]:
        """Return all entries across all loaded feeds, deduplicating by (skillId, version).

        When the same (skillId, version) appears in multiple feeds, the entry
        from the *verified* feed takes precedence; ties are broken by feed_id
        alphabetical order.
        """
        seen: Dict[Tuple[str, str], StoreEntry] = {}
        # verified feeds first so they win deduplication
        ordered = sorted(
            self._records.values(),
            key=lambda r: (not r.verified, r.feed_id),
        )
        for record in ordered:
            for entry in record.entries:
                key = (entry.skillId, entry.version)
                if key not in seen:
                    seen[key] = entry
        return list(seen.values())

    def get_versions(self, skill_id: str) -> List[StoreEntry]:
        """Return all versions of *skill_id* across feeds, sorted highest-first."""
        return sort_versions([e for e in self.aggregate() if e.skillId == skill_id])

    def find_skill(
        self, skill_id: str, runtime_version: str = "0.0.0"
    ) -> Optional[StoreEntry]:
        """Return the best-version entry for *skill_id* compatible with *runtime_version*."""
        return best_version(self.get_versions(skill_id), runtime_version)

    def list_feeds(self) -> List[Dict[str, Any]]:
        """Return summary dicts for all loaded feeds."""
        return [
            {
                "feed_id": r.feed_id,
                "name": r.feed_name,
                "version": r.feed_version,
                "entry_count": r.entry_count,
                "verified": r.verified,
                "error": r.error,
            }
            for r in self._records.values()
        ]

    def list_skills(self) -> List[Dict[str, Any]]:
        """Return one dict per unique (skillId, version) across all feeds."""
        result = []
        for entry in sort_versions(self.aggregate()):
            result.append({
                "skillId": entry.skillId,
                "version": entry.version,
                "family": entry.family,
                "publisher": entry.publisher,
                "licenseModel": entry.licenseModel,
                "runtimeConstraint": entry.runtimeConstraint,
            })
        return result

    @property
    def feed_count(self) -> int:
        return len(self._records)

    @property
    def total_entries(self) -> int:
        return sum(r.entry_count for r in self._records.values())
