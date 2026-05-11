"""Generate an Ed25519 keypair for ETD package signing (uses PyNaCl / libsodium).

Usage:
    python scripts/generate_keypair.py [--out-dir keys/]

Produces:
    keys/etd_signing_key.hex   — private key hex (keep secret, never commit)
    keys/etd_verify_key.hex    — public key hex  (distribute freely)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from nacl.signing import SigningKey


def generate(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    priv_path = out_dir / 'etd_signing_key.hex'
    pub_path  = out_dir / 'etd_verify_key.hex'

    priv_path.write_text(signing_key.encode().hex())
    pub_path.write_text(verify_key.encode().hex())
    priv_path.chmod(0o600)

    print(f'Private key (Ed25519): {priv_path}  (keep secret, never commit)')
    print(f'Public  key (Ed25519): {pub_path}  (distribute freely)')


def main() -> None:
    ap = argparse.ArgumentParser(description='Generate ETD Ed25519 signing keypair')
    ap.add_argument('--out-dir', default='keys', help='Output directory (default: keys/)')
    args = ap.parse_args()
    generate(Path(args.out_dir))


if __name__ == '__main__':
    main()
