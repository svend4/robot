"""Generate a validation and release report for all ETD example packages."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from etd_reference_validator import ETDReferenceValidator, load_runtime_context, RuntimeContext


def _pick_context(pkg_name: str, ctxs: dict):
    if 'atlas' in pkg_name or 'humanoid' in pkg_name:
        return ctxs['atlas']
    if 'wia_welding' in pkg_name or 'wia_weld' in pkg_name:
        return ctxs['wia']
    if 'mobed' in pkg_name or 'transport' in pkg_name:
        return ctxs['mobed']
    if 'vest' in pkg_name or 'exoskeleton' in pkg_name:
        return ctxs['exo']
    return ctxs['base']


def main():
    root = ROOT
    base_ctx = load_runtime_context(root / 'runtime_context.json')
    atlas_ctx = (load_runtime_context(root / 'runtime_context_atlas.json')
                 if (root / 'runtime_context_atlas.json').exists() else base_ctx)
    wia_ctx = (load_runtime_context(root / 'runtime_context_wia.json')
               if (root / 'runtime_context_wia.json').exists() else base_ctx)
    mobed_ctx = (load_runtime_context(root / 'runtime_context_mobed.json')
                 if (root / 'runtime_context_mobed.json').exists() else base_ctx)
    exo_ctx = (load_runtime_context(root / 'runtime_context_exo.json')
               if (root / 'runtime_context_exo.json').exists() else base_ctx)
    ctxs = {'base': base_ctx, 'atlas': atlas_ctx, 'wia': wia_ctx, 'mobed': mobed_ctx, 'exo': exo_ctx}

    validation = []
    for pkg in sorted((root / 'examples').iterdir()):
        if not pkg.is_dir() or not (pkg / 'manifest.yaml').exists():
            continue
        ctx = _pick_context(pkg.name, ctxs)
        rep = ETDReferenceValidator(ctx).validate_package(pkg)
        validation.append({
            'package': pkg.name,
            'valid': rep.valid,
            'level': rep.compatibility['level'],
            'score': rep.compatibility['score'],
        })

    # Intentional failure test: missing services → must be level D
    missing_ctx = RuntimeContext(
        runtime_version='0.1.0', robot_class='humanoid',
        available_services=['perception.object_pose'],
    )
    fail_rep = ETDReferenceValidator(missing_ctx).validate_package(root / 'examples/etd.pickplace.basic')

    release_files = sorted(x.name for x in (root / 'release_out').glob('*.zip')) if (root / 'release_out').exists() else []

    summary = {
        'overall_pass': all(x['valid'] for x in validation) and fail_rep.compatibility['level'] == 'D',
        'validation_summary': validation,
        'failure_summary': {'missing_service_level': fail_rep.compatibility['level']},
        'release_summary': release_files,
    }

    out = root / 'reports'
    out.mkdir(exist_ok=True)
    (out / 'report_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

    md = '# ETD Prototype Report\n\nOverall pass: **%s**\n\n' % summary['overall_pass']
    for row in validation:
        md += f"- {row['package']}: valid={row['valid']}, level={row['level']}, score={row['score']}\n"
    (out / 'report_summary.md').write_text(md, encoding='utf-8')

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    raise SystemExit(0 if summary['overall_pass'] else 1)


if __name__ == '__main__':
    main()
