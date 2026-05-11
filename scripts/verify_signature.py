"""Verify the Ed25519 signature of an ETD skill package.

Usage:
    python scripts/verify_signature.py examples/etd.pickplace.basic \\
        [--pub-key keys/etd_verify_key.hex]

Returns exit code 0 on success, 1 on failure or missing signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


_SIGN_INCLUDE = [
    'manifest.yaml', 'skill.json', 'chs_profiles.json',
    'capabilities.json', 'execution_contract.json',
    'telemetry/events.json', 'tests/acceptance_tests.yaml',
]


def _package_digest(pkg: Path, files: list[str]) -> bytes:
    h = hashlib.sha256()
    for rel in sorted(files):
        f = pkg / rel
        if f.exists():
            h.update(rel.encode())
            h.update(b'\x00')
            h.update(f.read_bytes())
            h.update(b'\x00')
    return h.digest()


def verify_package(pkg_path: Path, pub_key_path: Path | None = None) -> bool:
    sig_path = pkg_path / 'package.sig'
    if not sig_path.exists():
        print(f'ERROR: no package.sig found in {pkg_path}')
        return False

    sig_doc = json.loads(sig_path.read_text())

    if pub_key_path and pub_key_path.exists():
        verify_hex = pub_key_path.read_text().strip()
    else:
        verify_hex = sig_doc.get('verify_key', '')

    if not verify_hex:
        print('ERROR: no public key available for verification')
        return False

    verify_key = VerifyKey(bytes.fromhex(verify_hex))
    signed_files = sig_doc.get('signed_files', _SIGN_INCLUDE)
    digest       = _package_digest(pkg_path, signed_files)
    signature    = bytes.fromhex(sig_doc['signature'])

    try:
        verify_key.verify(digest, signature)
        print(f'OK: signature valid for {pkg_path.name}')
        return True
    except BadSignatureError:
        print(f'FAIL: signature INVALID for {pkg_path.name}')
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description='Verify ETD skill package signature')
    ap.add_argument('package', help='Path to the skill package directory')
    ap.add_argument('--pub-key', default=None,
                    help='Path to hex public key (default: embedded in package.sig)')
    args = ap.parse_args()
    ok = verify_package(Path(args.package), Path(args.pub_key) if args.pub_key else None)
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
