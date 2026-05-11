from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, load_runtime_context

def main():
    root = Path(__file__).resolve().parent
    ctx = load_runtime_context(root/'runtime_context.json')
    pkg = root/'examples'/'etd.pickplace.basic'
    report = ETDReferenceValidator(ctx).validate_package(pkg)
    print(report.to_json())
    raise SystemExit(0 if report.valid else 1)
if __name__ == '__main__': main()
