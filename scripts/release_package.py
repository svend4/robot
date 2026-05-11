"""Release an ETD skill package: validate → sign → zip.

Usage:
    python scripts/release_package.py examples/etd.pickplace.basic \\
        [--key keys/etd_signing_key.pem] [--out release_out/] [--skip-sign]
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import ETDReferenceValidator, load_runtime_context


def _zip_dir(src: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.rglob('*')):
            if f.is_file() and '__pycache__' not in f.parts and not f.name.endswith('.pyc'):
                z.write(f, f.relative_to(src.parent))


def main() -> None:
    ap = argparse.ArgumentParser(description='Validate, sign, and package an ETD skill')
    ap.add_argument('package', help='Path to the skill package directory')
    ap.add_argument('--runtime-context', default=None,
                    help='Path to runtime context JSON (auto-detected if not set)')
    ap.add_argument('--key', default='keys/etd_signing_key.pem',
                    help='Path to PEM private key for signing')
    ap.add_argument('--out', default='release_out', help='Output directory')
    ap.add_argument('--skip-sign', action='store_true',
                    help='Skip signing (not recommended for production)')
    args = ap.parse_args()

    pkg = Path(args.package)
    if not pkg.is_absolute():
        pkg = ROOT / pkg

    # ── Step 1: validate ─────────────────────────────────────────────────────
    print(f'[1/3] Validating {pkg.name} ...')
    if args.runtime_context:
        ctx_path = ROOT / args.runtime_context
    elif any(kw in pkg.name for kw in ('atlas', 'humanoid')):
        atlas_ctx = ROOT / 'runtime_context_atlas.json'
        ctx_path = atlas_ctx if atlas_ctx.exists() else ROOT / 'runtime_context.json'
    else:
        ctx_path = ROOT / 'runtime_context.json'
    ctx = load_runtime_context(ctx_path)
    rep = ETDReferenceValidator(ctx).validate_package(pkg)
    if not rep.valid:
        print('Validation FAILED:')
        print(rep.to_json())
        raise SystemExit(1)
    print(f'      valid=True, level={rep.compatibility["level"]}, score={rep.compatibility["score"]}')

    # ── Step 2: sign ─────────────────────────────────────────────────────────
    key_path = ROOT / args.key
    if args.skip_sign:
        print('[2/3] Signing SKIPPED (--skip-sign)')
    elif not key_path.exists():
        print(f'[2/3] Signing SKIPPED — key not found at {key_path}')
        print('      Run: python scripts/generate_keypair.py  to create a keypair')
    else:
        print(f'[2/3] Signing with key {key_path} ...')
        from scripts.sign_package import sign_package
        sign_package(pkg, key_path)

    # ── Step 3: package ───────────────────────────────────────────────────────
    out_dir = ROOT / args.out
    out_dir.mkdir(exist_ok=True)

    skill_id = pkg.name
    version = '0.1.0'
    try:
        import yaml
        manifest = yaml.safe_load((pkg / 'manifest.yaml').read_text(encoding='utf-8'))
        version = manifest.get('metadata', {}).get('version', version)
    except Exception:
        pass

    dest = out_dir / f'{skill_id}-{version}.zip'
    print(f'[3/3] Packaging -> {dest} ...')
    _zip_dir(pkg, dest)

    size_kb = dest.stat().st_size / 1024
    print(f'      Done. {dest.name}  ({size_kb:.1f} KB)')

    summary = {
        'skillId': skill_id,
        'version': version,
        'validationLevel': rep.compatibility['level'],
        'signed': not args.skip_sign and key_path.exists(),
        'artifact': str(dest),
    }
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
