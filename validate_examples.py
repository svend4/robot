"""Validate all ETD example skill packages.

Each package may declare a preferred runtime context via a
`runtime_context` key in its skill.json (optional). Falls back to
the root runtime_context.json, then runtime_context_atlas.json for
humanoid-only packages.
"""
from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, load_runtime_context, RuntimeContext

_CTX_MAP = {}  # skill_id -> RuntimeContext override


def _load_contexts(root: Path) -> dict:
    base_ctx = load_runtime_context(root / 'runtime_context.json')
    atlas_ctx = (load_runtime_context(root / 'runtime_context_atlas.json')
                 if (root / 'runtime_context_atlas.json').exists() else base_ctx)
    wia_ctx = (load_runtime_context(root / 'runtime_context_wia.json')
               if (root / 'runtime_context_wia.json').exists() else base_ctx)
    mobed_ctx = (load_runtime_context(root / 'runtime_context_mobed.json')
                 if (root / 'runtime_context_mobed.json').exists() else base_ctx)
    exo_ctx = (load_runtime_context(root / 'runtime_context_exo.json')
               if (root / 'runtime_context_exo.json').exists() else base_ctx)
    return {'base': base_ctx, 'atlas': atlas_ctx, 'wia': wia_ctx, 'mobed': mobed_ctx, 'exo': exo_ctx}


def _pick_context(pkg_name: str, contexts: dict) -> RuntimeContext:
    if 'atlas' in pkg_name or 'humanoid' in pkg_name:
        return contexts['atlas']
    if 'wia_welding' in pkg_name or 'wia_weld' in pkg_name:
        return contexts['wia']
    if 'mobed' in pkg_name or 'transport' in pkg_name:
        return contexts['mobed']
    if 'vest' in pkg_name or 'exoskeleton' in pkg_name:
        return contexts['exo']
    return contexts['base']


def main():
    root = Path(__file__).resolve().parent
    contexts = _load_contexts(root)
    failed = []
    for pkg in sorted((root / 'examples').iterdir()):
        if not pkg.is_dir() or not (pkg / 'manifest.yaml').exists():
            continue
        ctx = _pick_context(pkg.name, contexts)
        validator = ETDReferenceValidator(ctx)
        report = validator.validate_package(pkg)
        level = report.compatibility['level']
        score = report.compatibility['score']
        print(f'{pkg.name}: valid={report.valid}, level={level}, score={score}')
        if report.errors:
            for e in report.errors[:3]:
                print(f'  ! {e}')
        if not report.valid:
            failed.append(pkg.name)
    if failed:
        raise SystemExit('failed examples: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
