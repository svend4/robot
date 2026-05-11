"""Sign an ETD skill package directory with Ed25519 (PyNaCl / libsodium).

Produces a `package.sig` file inside the package directory.
The signature covers a SHA-256 digest of the canonical file list.

Usage:
    python scripts/sign_package.py examples/etd.pickplace.basic \\
        --key keys/etd_signing_key.hex
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from nacl.signing import SigningKey


_SIGN_INCLUDE = [
    'manifest.yaml', 'skill.json', 'chs_profiles.json',
    'capabilities.json', 'execution_contract.json',
    'telemetry/events.json', 'tests/acceptance_tests.yaml',
]


def _package_digest(pkg: Path) -> bytes:
    h = hashlib.sha256()
    for rel in sorted(_SIGN_INCLUDE):
        f = pkg / rel
        if f.exists():
            h.update(rel.encode())
            h.update(b'\x00')
            h.update(f.read_bytes())
            h.update(b'\x00')
    return h.digest()


def sign_package(pkg_path: Path, key_path: Path) -> Path:
    signing_key = SigningKey(bytes.fromhex(key_path.read_text().strip()))
    verify_key  = signing_key.verify_key

    digest    = _package_digest(pkg_path)
    signed    = signing_key.sign(digest)
    signature = signed.signature  # first 64 bytes

    sig_doc = {
        'algorithm': 'ed25519',
        'digest_algorithm': 'sha256',
        'signed_files': _SIGN_INCLUDE,
        'signature': signature.hex(),
        'verify_key': verify_key.encode().hex(),
    }
    sig_path = pkg_path / 'package.sig'
    sig_path.write_text(json.dumps(sig_doc, indent=2))
    print(f'Signed: {pkg_path.name}  ->  {sig_path}')
    return sig_path


def main() -> None:
    ap = argparse.ArgumentParser(description='Sign an ETD skill package (Ed25519)')
    ap.add_argument('package', help='Path to the skill package directory')
    ap.add_argument('--key', default='keys/etd_signing_key.hex',
                    help='Path to hex private key (default: keys/etd_signing_key.hex)')
    args = ap.parse_args()
    sign_package(Path(args.package), Path(args.key))


if __name__ == '__main__':
    main()
