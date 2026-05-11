import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, load_runtime_context

def main():
    root = Path(__file__).resolve().parents[1]
    ctx = load_runtime_context(root/'runtime_context.json')
    v = ETDReferenceValidator(ctx)
    results = []
    for pkg in sorted((root/'examples').iterdir()):
        rep = v.validate_package(pkg)
        results.append({'package':pkg.name,'valid':rep.valid,'level':rep.compatibility['level']})
    print(results)
    raise SystemExit(0 if all(r['valid'] for r in results) else 1)
if __name__ == '__main__': main()
