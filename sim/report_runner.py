import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import json
from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, load_runtime_context, RuntimeContext

def main():
    root = Path(__file__).resolve().parents[1]
    ctx = load_runtime_context(root/'runtime_context.json')
    v = ETDReferenceValidator(ctx)
    validation = []
    for pkg in sorted((root/'examples').iterdir()):
        rep = v.validate_package(pkg)
        validation.append({'package':pkg.name,'valid':rep.valid,'level':rep.compatibility['level']})
    missing_ctx = RuntimeContext(runtime_version='0.1.0', robot_class='humanoid', available_services=['perception.object_pose'])
    fail_rep = ETDReferenceValidator(missing_ctx).validate_package(root/'examples/etd.pickplace.basic')
    release_files = sorted(x.name for x in (root/'release_out').glob('*.zip')) if (root/'release_out').exists() else []
    summary = {'overall_pass': all(x['valid'] for x in validation) and fail_rep.compatibility['level']=='D', 'validation_summary': validation, 'failure_summary': {'missing_service_level': fail_rep.compatibility['level']}, 'release_summary': release_files}
    out = root/'reports'; out.mkdir(exist_ok=True)
    (out/'report_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    md = '# ETD Prototype Report\n\nOverall pass: **%s**\n\n' % summary['overall_pass']
    for row in validation: md += f"- {row['package']}: valid={row['valid']}, level={row['level']}\n"
    (out/'report_summary.md').write_text(md, encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    raise SystemExit(0 if summary['overall_pass'] else 1)
if __name__ == '__main__': main()
