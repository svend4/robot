"""ETD Signed Entitlement Token — Ed25519-signed install authorisation.

Replaces the ``entitlement_checked: true`` flag with a cryptographically
signed token that binds ``skill_id + station_id + expiry + operator_org``.
Uses the same Ed25519 / PyNaCl infrastructure as package signing.

Token wire format::

    <base64url(payload_json)>.<base64url(signature)>

Where payload_json is canonical (sorted keys)::

    {
      "expiry":       "2027-01-01T00:00:00Z",
      "issued_at":    "2026-05-12T10:00:00Z",
      "operator_org": "Hyundai Motor Manufacturing",
      "skill_id":     "etd.hyundai.wia_welding",
      "station_id":   "workcell-01"
    }

``station_id`` may be ``"*"`` to grant access to any station.

Usage::

    from marketplace.entitlement_token import issue_token, verify_token
    from nacl.signing import SigningKey

    # Issue
    key = SigningKey(bytes.fromhex(Path('keys/etd_signing_key.hex').read_text().strip()))
    token_str = issue_token(
        skill_id='etd.hyundai.wia_welding',
        station_id='workcell-01',
        operator_org='Hyundai Motor Manufacturing',
        signing_key=key,
        ttl_days=365,
    )

    # Verify
    valid, reason, token = verify_token(
        token_str,
        verify_key=key.verify_key,
        skill_id='etd.hyundai.wia_welding',
        station_id='workcell-01',
    )
"""
from __future__ import annotations

import base64
import datetime
import json
from dataclasses import dataclass, asdict
from typing import Optional, Tuple


@dataclass
class EntitlementToken:
    skill_id: str
    station_id: str     # use "*" to authorise any station
    expiry: str         # ISO 8601 UTC, e.g. "2027-01-01T00:00:00Z"
    operator_org: str
    issued_at: str

    def to_payload(self) -> bytes:
        """Canonical JSON payload for signing (sorted keys, UTF-8)."""
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()

    def is_expired(self) -> bool:
        try:
            expiry_dt = datetime.datetime.fromisoformat(
                self.expiry.replace('Z', '+00:00')
            )
            return datetime.datetime.now(datetime.timezone.utc) > expiry_dt
        except Exception:
            return True

    def covers(self, skill_id: str, station_id: str) -> bool:
        """Return True if this token authorises *skill_id* at *station_id*."""
        skill_ok = self.skill_id == skill_id
        station_ok = self.station_id in ('*', station_id)
        return skill_ok and station_ok and not self.is_expired()


def issue_token(
    skill_id: str,
    station_id: str,
    operator_org: str,
    signing_key,        # nacl.signing.SigningKey
    ttl_days: int = 365,
) -> str:
    """Sign and return an entitlement token for *skill_id* @ *station_id*.

    Parameters
    ----------
    skill_id:     ETD skill identifier
    station_id:   Station ID, or ``"*"`` for any station
    operator_org: Operator organisation name (included in token payload)
    signing_key:  ``nacl.signing.SigningKey`` instance
    ttl_days:     Token validity in days from now

    Returns
    -------
    str
        Opaque token string: ``<base64url(payload)>.<base64url(signature)>``
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    expiry = now + datetime.timedelta(days=ttl_days)
    token = EntitlementToken(
        skill_id=skill_id,
        station_id=station_id,
        expiry=expiry.strftime('%Y-%m-%dT%H:%M:%SZ'),
        operator_org=operator_org,
        issued_at=now.strftime('%Y-%m-%dT%H:%M:%SZ'),
    )
    payload = token.to_payload()
    signed = signing_key.sign(payload)
    signature = signed.signature  # first 64 bytes

    payload_b64 = _b64(payload)
    sig_b64 = _b64(signature)
    return f'{payload_b64}.{sig_b64}'


def verify_token(
    token_str: str,
    verify_key,                  # nacl.signing.VerifyKey
    skill_id: str,
    station_id: str = '*',
) -> Tuple[bool, str, Optional[EntitlementToken]]:
    """Verify a signed entitlement token.

    Parameters
    ----------
    token_str:   Token string returned by ``issue_token``
    verify_key:  ``nacl.signing.VerifyKey`` paired with the issuing key
    skill_id:    Expected skill ID
    station_id:  Station ID to check coverage for (``"*"`` matches all)

    Returns
    -------
    (valid, reason, token)
        *valid*  — True if signature good, not expired, and covers skill/station
        *reason* — short snake_case string (``"token_valid"``, ``"token_expired"``, …)
        *token*  — parsed ``EntitlementToken`` or None on parse/decode failure
    """
    try:
        payload_b64, sig_b64 = token_str.rsplit('.', 1)
    except ValueError:
        return False, 'malformed_token', None

    try:
        payload = _b64decode(payload_b64)
        signature = _b64decode(sig_b64)
    except Exception:
        return False, 'decode_error', None

    try:
        verify_key.verify(payload, signature)
    except Exception:
        return False, 'signature_invalid', None

    try:
        data = json.loads(payload)
        token = EntitlementToken(**data)
    except Exception:
        return False, 'payload_parse_error', None

    if token.is_expired():
        return False, 'token_expired', token

    if not token.covers(skill_id, station_id):
        return False, 'token_skill_station_mismatch', token

    return True, 'token_valid', token


# ── Helpers ───────────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64decode(s: str) -> bytes:
    # Restore padding
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)
