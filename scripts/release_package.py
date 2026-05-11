import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import argparse, zipfile
from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, load_runtime_context

def zip_dir(src: Path, dest: Path):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in src.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts and not f.name.endswith('.pyc'):
                z.write(f, f.relative_to(src.parent))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('package')
    ap.add_argument('--runtime-context', default='runtime_context.json')
    ap.add_argument('--out', default='release_out')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    pkg = Path(args.package)
    if not pkg.is_absolute(): pkg = root/pkg
    ctx = load_runtime_context(root/args.runtime_context)
    rep = ETDReferenceValidator(ctx).validate_package(pkg)
    if not rep.valid:
        print(rep.to_json()); raise SystemExit(1)
    out = root/args.out; out.mkdir(exist_ok=True)
    dest = out/f'{pkg.name}-0.1.0.zip'
    zip_dir(pkg, dest)
    print(dest)
if __name__ == '__main__': main()
