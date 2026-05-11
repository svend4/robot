from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, load_runtime_context

def main():
    root = Path(__file__).resolve().parent
    ctx = load_runtime_context(root/'runtime_context.json')
    validator = ETDReferenceValidator(ctx)
    failed = []
    for pkg in sorted((root/'examples').iterdir()):
        if not pkg.is_dir(): continue
        report = validator.validate_package(pkg)
        print(f'{pkg.name}: valid={report.valid}, level={report.compatibility["level"]}, score={report.compatibility["score"]}')
        if not report.valid: failed.append(pkg.name)
    if failed:
        raise SystemExit('failed examples: '+', '.join(failed))
if __name__ == '__main__': main()
