#!/usr/bin/env python3
"""ETD CLI — command-line tool for managing ETD skill packages.

Usage:
    python etd_cli.py validate  <package-path> [--runtime-context FILE] [--station-profile FILE] [--json]
    python etd_cli.py publish   <package-path> [--key FILE] [--out DIR] [--skip-sign]
    python etd_cli.py verify    <package-path> [--pub-key FILE]
    python etd_cli.py install   <skill-id>     [--token TOKEN] [--robot-class CLASS] [--station-profile FILE]
    python etd_cli.py list      [--family FAM] [--free] [--json]
    python etd_cli.py info      <skill-id>
    python etd_cli.py stations  [--dir DIR] [--json]
    python etd_cli.py keygen    [--out-dir DIR]
    python etd_cli.py serve     [--host HOST] [--port PORT]
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import click

from etd_reference_validator import ETDReferenceValidator, RuntimeContext, load_runtime_context
from marketplace.skill_store import SkillStore, default_runtime_context
from adapters.station_profile_loader import load_station_profile, load_all_profiles, check_skill_compatible

_CTX_PATH = ROOT / 'runtime_context.json'
_STATION_PROFILES_DIR = ROOT / 'station_profiles'


def _load_ctx(runtime_context: str, robot_class: str | None, services: tuple) -> RuntimeContext:
    ctx_path = Path(runtime_context)
    if ctx_path.exists():
        ctx = load_runtime_context(ctx_path)
    else:
        ctx = default_runtime_context()
    if robot_class is not None:
        ctx.robot_class = robot_class
    if services:
        ctx.available_services = list(services)
    return ctx


def _print_report(report, as_json: bool) -> None:
    if as_json:
        click.echo(report.to_json())
    else:
        status = click.style('PASS', fg='green', bold=True) if report.valid else click.style('FAIL', fg='red', bold=True)
        click.echo(f'\nETD Validation: {status}')
        click.echo(f'  Package : {report.package_path}')
        click.echo(f'  Level   : {report.compatibility["level"]}  Score: {report.compatibility["score"]}')

        if report.errors:
            click.echo(click.style('\nErrors:', fg='red'))
            for e in report.errors:
                click.echo(f'  ✗ {e}')

        if report.warnings:
            click.echo(click.style('\nWarnings:', fg='yellow'))
            for w in report.warnings:
                click.echo(f'  ! {w}')

        if not report.errors:
            click.echo(click.style('\nAll checks passed.', fg='green'))


@click.group()
def cli():
    """ETD Skill Package CLI — validate, publish, sign, and manage robot skill packages."""


def _check_station(package_path: str, station_profile_path: str, as_json: bool) -> None:
    """Print station compatibility result for a validated package."""
    import yaml
    pkg = Path(package_path)
    manifest_path = pkg / 'manifest.yaml'
    skill_path = pkg / 'skill.json'
    if not manifest_path.exists() or not skill_path.exists():
        click.echo(click.style('  Station check skipped: manifest.yaml or skill.json not found', fg='yellow'))
        return
    manifest = yaml.safe_load(manifest_path.read_text())
    skill = json.loads(skill_path.read_text())
    family = skill.get('family', '')
    payload = skill.get('maxPayloadKg', 0.0)
    human_aware = manifest.get('safety', {}).get('humanAware', False)
    required_services = [s['name'] for s in skill.get('requiredServices', [])] if skill.get('requiredServices') else []
    profile = load_station_profile(station_profile_path)
    result = check_skill_compatible(profile, family, payload, human_aware, required_services,
                                    skill_id=manifest.get('skillId', ''))
    if as_json:
        from dataclasses import asdict as _asdict
        click.echo(json.dumps({'station_check': _asdict(result)}, indent=2))
    else:
        compat_str = click.style('COMPATIBLE', fg='green', bold=True) if result.compatible else click.style('INCOMPATIBLE', fg='red', bold=True)
        click.echo(f'\nStation {result.station_id}: {compat_str}  ({result.reason})')
        if result.missing_services:
            click.echo(click.style('  Missing services: ' + ', '.join(result.missing_services), fg='red'))
        for w in result.warnings:
            click.echo(click.style(f'  ! {w}', fg='yellow'))


def _check_station_entry(entry: dict | None, station_profile_path: str) -> None:
    """Print station compatibility for a store index entry."""
    if not entry:
        return
    profile = load_station_profile(station_profile_path)
    family = entry.get('family', '')
    result = check_skill_compatible(
        profile, family,
        payload_kg=entry.get('maxPayloadKg', 0.0),
        requires_human_aware=entry.get('requiresHumanAware', False),
        required_services=entry.get('requiredServices', []),
        skill_id=entry.get('skillId', ''),
    )
    compat_str = click.style('COMPATIBLE', fg='green', bold=True) if result.compatible else click.style('INCOMPATIBLE', fg='red', bold=True)
    click.echo(f'\nStation {result.station_id}: {compat_str}  ({result.reason})')
    if result.missing_services:
        click.echo(click.style('  Missing services: ' + ', '.join(result.missing_services), fg='red'))
    for w in result.warnings:
        click.echo(click.style(f'  ! {w}', fg='yellow'))


@cli.command()
@click.argument('package_path')
@click.option('--runtime-context', default=str(_CTX_PATH), show_default=True)
@click.option('--robot-class', default=None, help='Override robot class from context file')
@click.option('--service', 'services', multiple=True, metavar='SVC',
              help='Available service (repeat for each)')
@click.option('--station-profile', default=None, metavar='FILE',
              help='Path to station profile JSON; checks skill family/payload/service compatibility')
@click.option('--json', 'as_json', is_flag=True, help='Output raw JSON report')
def validate(package_path: str, runtime_context: str, robot_class: str | None, services: tuple,
             station_profile: str | None, as_json: bool):
    """Validate an ETD skill package directory."""
    ctx = _load_ctx(runtime_context, robot_class, services)
    report = ETDReferenceValidator(ctx).validate_package(package_path)
    _print_report(report, as_json)

    if station_profile:
        _check_station(package_path, station_profile, as_json)

    sys.exit(0 if report.valid else 1)


@cli.command()
@click.argument('package_path')
@click.option('--key', default='keys/etd_signing_key.hex', show_default=True)
@click.option('--out', default='release_out', show_default=True)
@click.option('--skip-sign', is_flag=True)
@click.option('--runtime-context', default=str(_CTX_PATH), show_default=True)
def publish(package_path: str, key: str, out: str, skip_sign: bool, runtime_context: str):
    """Validate, sign, and package a skill for distribution."""
    import subprocess
    cmd = [sys.executable, 'scripts/release_package.py', package_path,
           '--key', key, '--out', out, '--runtime-context', runtime_context]
    if skip_sign:
        cmd.append('--skip-sign')
    result = subprocess.run(cmd, cwd=ROOT)
    sys.exit(result.returncode)


@cli.command()
@click.argument('package_path')
@click.option('--pub-key', default=None, help='Path to hex public key')
def verify(package_path: str, pub_key: str | None):
    """Verify the Ed25519 signature of a skill package."""
    from scripts.verify_signature import verify_package
    ok = verify_package(Path(package_path), Path(pub_key) if pub_key else None)
    sys.exit(0 if ok else 1)


@cli.command('list')
@click.option('--family', default=None, help='Filter by skill family')
@click.option('--free', 'free_only', is_flag=True, help='Show only free skills')
@click.option('--json', 'as_json', is_flag=True, help='Output raw JSON')
def list_skills(family: str | None, free_only: bool, as_json: bool):
    """List skills available in the ETD Skill Store."""
    store = SkillStore(ROOT)
    entries = store.list_skills()
    if family:
        entries = [e for e in entries if e.get('family') == family]
    if free_only:
        entries = [e for e in entries if e.get('pricingModel') == 'free']

    if as_json:
        click.echo(json.dumps(entries, indent=2))
        return

    click.echo(f'\n{"SKILL ID":<35} {"FAMILY":<12} {"LICENSE":<18} {"PRICE":<15} {"LEVEL"}')
    click.echo('─' * 90)
    for e in entries:
        lvl_color = 'green' if e.get('riskLevel') == 'low' else 'yellow'
        click.echo(
            f'{e["skillId"]:<35} {e.get("family",""):<12} '
            f'{e.get("licenseModel",""):<18} {e.get("pricingModel",""):<15} '
            + click.style(e.get('riskLevel', ''), fg=lvl_color)
        )
    click.echo(f'\n{len(entries)} skill(s) found.')


@cli.command()
@click.argument('skill_id')
def info(skill_id: str):
    """Show full details for a skill from the store index."""
    store = SkillStore(ROOT)
    entry = store.find_skill(skill_id)
    if entry is None:
        click.echo(click.style(f'Skill not found: {skill_id}', fg='red'), err=True)
        sys.exit(1)
    click.echo(json.dumps(entry, indent=2))


@cli.command()
@click.option('--dir', 'profiles_dir', default=str(_STATION_PROFILES_DIR), show_default=True,
              help='Directory containing station profile JSON files')
@click.option('--json', 'as_json', is_flag=True, help='Output raw JSON')
def stations(profiles_dir: str, as_json: bool):
    """List all known station profiles."""
    profiles = load_all_profiles(profiles_dir)
    if as_json:
        click.echo(json.dumps([p.to_dict() for p in profiles.values()], indent=2))
        return
    click.echo(f'\n{"STATION ID":<30} {"PLATFORM":<30} {"FAMILIES":<30} {"PAYLOAD":>8}')
    click.echo('─' * 95)
    for p in profiles.values():
        families = ','.join(p.allowed_skill_families)
        platform = p.platform or '—'
        click.echo(f'{p.station_id:<30} {platform:<30} {families:<30} {p.max_payload_kg:>7.1f}kg')
    click.echo(f'\n{len(profiles)} station(s) found.')


@cli.command()
@click.argument('skill_id')
@click.option('--token', default=None, help='Entitlement token for commercial skills')
@click.option('--robot-class', default=None, help='Override robot class from context file')
@click.option('--runtime-context', default=str(_CTX_PATH), show_default=True)
@click.option('--station-profile', default=None, metavar='FILE',
              help='Path to station profile JSON; checks station compatibility before install')
def install(skill_id: str, token: str | None, robot_class: str | None, runtime_context: str,
            station_profile: str | None):
    """Check install eligibility for a skill (does not copy files)."""
    store = SkillStore(ROOT)
    ctx = _load_ctx(runtime_context, robot_class, ())
    decision = store.validate_for_install(skill_id, ctx, entitlement_token=token)
    if decision is None:
        click.echo(click.style(f'Skill not found: {skill_id}', fg='red'), err=True)
        sys.exit(1)

    d = asdict(decision)
    allowed_str = click.style('ALLOWED', fg='green', bold=True) if d['allowed'] else click.style('BLOCKED', fg='red', bold=True)
    click.echo(f'\nInstall decision for {skill_id}: {allowed_str}')
    for k, v in d.items():
        if k != 'skillId':
            click.echo(f'  {k:<25} {v}')

    if station_profile and decision.allowed:
        entry = store.find_skill(skill_id)
        _check_station_entry(entry, station_profile)

    sys.exit(0 if decision.allowed else 1)


@cli.group()
def rollout():
    """Manage staged fleet rollout of skill packages (draft→canary→pilot→production)."""


@rollout.command('set-stage')
@click.argument('skill_id')
@click.argument('stage', type=click.Choice(['draft', 'canary', 'pilot', 'production']))
@click.option('--version', default='0.5.0', show_default=True)
@click.option('--station', 'stations', multiple=True, metavar='STATION_ID',
              help='Approved station(s) for canary/pilot stage (repeat for each)')
@click.option('--operator', default='etd-cli', show_default=True)
def rollout_set_stage(skill_id: str, stage: str, version: str,
                      stations: tuple, operator: str):
    """Set the rollout stage for a skill package version."""
    from marketplace.rollout_policy import RolloutPolicy
    policy = RolloutPolicy(ROOT / 'marketplace' / 'rollout_state.json')
    try:
        policy.set_stage(skill_id, version, stage,
                         stations=list(stations) or None,
                         operator_id=operator)
        click.echo(click.style(f'{skill_id}@{version}  →  {stage}', fg='green', bold=True))
        if stations:
            for s in stations:
                click.echo(f'  approved station: {s}')
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'), err=True)
        sys.exit(1)


@rollout.command('status')
@click.option('--skill', default=None, help='Filter by skill_id')
@click.option('--json', 'as_json', is_flag=True)
def rollout_status(skill: str | None, as_json: bool):
    """Show current rollout stages for all (or a specific) skill."""
    from marketplace.rollout_policy import RolloutPolicy
    policy = RolloutPolicy(ROOT / 'marketplace' / 'rollout_state.json')
    entries = policy.status(skill_id=skill)
    if as_json:
        click.echo(json.dumps(entries, indent=2))
        return
    if not entries:
        click.echo('No rollout entries found.')
        return
    for e in entries:
        stage = e.get('stage', 'draft')
        colour = {'draft': 'white', 'canary': 'yellow', 'pilot': 'cyan',
                  'production': 'green'}.get(stage, 'white')
        stage_str = click.style(f'{stage:<12}', fg=colour, bold=(stage == 'production'))
        stations = ', '.join(e.get('approvedStations', [])) or '—'
        click.echo(f"{e.get('skillId','?'):<42} {e.get('version','?'):<10} {stage_str} {stations}")


@cli.command('validate-context')
@click.argument('context_path', default=str(_CTX_PATH))
@click.option('--json', 'as_json', is_flag=True, help='Output raw JSON report')
def validate_context(context_path: str, as_json: bool):
    """Validate a runtime_context.json file against the ETD context schema."""
    from etd_reference_validator import validate_runtime_context
    path = Path(context_path)
    if not path.exists():
        click.echo(click.style(f'File not found: {path}', fg='red'), err=True)
        sys.exit(1)
    valid, errors = validate_runtime_context(path)
    if as_json:
        click.echo(json.dumps({'file': str(path), 'valid': valid, 'errors': errors}, indent=2))
    elif valid:
        click.echo(click.style(f'Context valid: {path}', fg='green', bold=True))
    else:
        click.echo(click.style(f'Context INVALID: {path}', fg='red', bold=True))
        for e in errors:
            click.echo(f'  • {e}')
    sys.exit(0 if valid else 1)


@cli.command('audit-log')
@click.option('--n', 'last_n', default=20, show_default=True,
              help='Show last N entries')
@click.option('--skill', default=None, help='Filter by skill_id')
@click.option('--result', 'filter_result', default=None,
              type=click.Choice(['allowed', 'blocked']), help='Filter by result')
@click.option('--json', 'as_json', is_flag=True, help='Output raw JSON array')
def audit_log_cmd(last_n: int, skill: str | None, filter_result: str | None, as_json: bool):
    """Show recent entries from the ETD audit log."""
    log_path = ROOT / 'logs' / 'etd_audit.jsonl'
    if not log_path.exists():
        click.echo('No audit log found. Run install checks to populate it.')
        return
    from marketplace.audit_log import AuditLog
    entries = AuditLog(log_path).read_entries()
    if skill:
        entries = [e for e in entries if e.get('skill_id') == skill]
    if filter_result:
        entries = [e for e in entries if e.get('result') == filter_result]
    entries = entries[-last_n:]
    if as_json:
        click.echo(json.dumps(entries, indent=2))
        return
    if not entries:
        click.echo('No matching audit log entries.')
        return
    for e in entries:
        result_str = click.style('ALLOWED', fg='green') if e.get('result') == 'allowed' else click.style('BLOCKED', fg='red')
        click.echo(f"{e.get('timestamp','?')}  {e.get('skill_id','?'):<40}  {result_str}  {e.get('reason','?')}")


@cli.command()
@click.argument('skill_id')
@click.option('--reason', default='unspecified', show_default=True,
              help='Reason for revocation')
@click.option('--revoked-by', 'revoked_by', default='etd-cli', show_default=True,
              help='Who is revoking the skill')
@click.option('--out', default=None,
              help='Path to revoked.json (default: marketplace/revoked.json)')
def revoke(skill_id: str, reason: str, revoked_by: str, out: str | None):
    """Add a skill to the revocation blocklist.

    Revoked skills cannot be installed regardless of entitlement.
    """
    import datetime
    revocation_path = Path(out) if out else ROOT / 'marketplace' / 'revoked.json'
    if revocation_path.exists():
        data = json.loads(revocation_path.read_text(encoding='utf-8'))
    else:
        data = {'revoked': []}

    already = {e['skillId'] for e in data['revoked']}
    if skill_id in already:
        click.echo(click.style(f'{skill_id} is already in the revocation list.', fg='yellow'))
        sys.exit(0)

    data['revoked'].append({
        'skillId': skill_id,
        'reason': reason,
        'revokedAt': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'revokedBy': revoked_by,
    })
    revocation_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    click.echo(click.style(f'Revoked: {skill_id}', fg='red', bold=True))
    click.echo(f'  Reason   : {reason}')
    click.echo(f'  Revoked by: {revoked_by}')
    click.echo(f'  Written to: {revocation_path}')


@cli.command('review')
@click.argument('package_path')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.option('--station-profiles-dir', default=None, help='Custom station profiles directory')
def review_package(package_path: str, as_json: bool, station_profiles_dir):
    """Run the automated review pipeline on a skill package."""
    from marketplace.review_pipeline import ReviewPipeline
    station_dir = Path(station_profiles_dir) if station_profiles_dir else None
    pipeline = ReviewPipeline(station_profiles_dir=station_dir)
    result = pipeline.run(Path(package_path))
    if as_json:
        import json as _json
        click.echo(_json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        click.echo(result.summary())
    if result.human_review_required and not result.passed:
        click.echo(click.style('\nHuman review required before publication.', fg='yellow', bold=True))
    raise SystemExit(0 if result.passed else 1)


@cli.command('versions')
@click.argument('skill_id')
@click.option('--runtime', default='0.0.0', show_default=True, help='Runtime version for negotiation')
def versions_cmd(skill_id: str, runtime: str):
    """List available versions of a skill and show the best match for --runtime."""
    from marketplace.skill_store import SkillStore
    store = SkillStore(ROOT)
    all_versions = store.get_versions(skill_id)
    if not all_versions:
        click.echo(f'Skill not found: {skill_id}', err=True)
        raise SystemExit(1)
    best = store.get_entry(skill_id, runtime)
    click.echo(f'Skill: {skill_id}  (runtime constraint: {runtime})')
    for entry in all_versions:
        marker = ' ← best match' if best and entry.version == best.version else ''
        constraint = entry.runtimeConstraint or '(any)'
        click.echo(f'  {entry.version}  constraint={constraint}{marker}')


@cli.group()
def publisher():
    """Publisher portal: submit, review, approve, and reject skill packages."""


@publisher.command('submit')
@click.argument('package_path')
@click.option('--publisher', 'publisher_name', default='etd-cli', show_default=True,
              help='Publisher identifier')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def publisher_submit(package_path: str, publisher_name: str, as_json: bool):
    """Submit a skill package for automated review and publication."""
    from marketplace.publisher_portal import PublisherPortal
    import json as _json
    p = Path(package_path)
    if not p.exists():
        click.echo(f'Error: package path does not exist: {package_path}', err=True)
        raise SystemExit(1)
    portal = PublisherPortal(ROOT)
    rec = portal.submit(p, publisher_name)
    if as_json:
        click.echo(_json.dumps(rec.to_dict(), indent=2, ensure_ascii=False))
    else:
        mark = 'AUTO-APPROVED' if rec.status == 'approved' else rec.status.upper()
        click.echo(f'Submission: {rec.submission_id}')
        click.echo(f'  Skill   : {rec.skill_id}  v{rec.version}')
        click.echo(f'  Status  : {mark}')
        if rec.blocking_findings:
            click.echo('  Blocking findings:')
            for f_msg in rec.blocking_findings[:5]:
                click.echo(f'    ! {f_msg}')
    raise SystemExit(0 if rec.status == 'approved' else 2 if rec.status == 'in_review' else 1)


@publisher.command('list')
@click.option('--publisher', 'pub_filter', default=None, help='Filter by publisher')
@click.option('--status', 'status_filter', default=None,
              type=click.Choice(['submitted', 'in_review', 'approved', 'rejected', 'needs_revision']),
              help='Filter by status')
@click.option('--json', 'as_json', is_flag=True)
def publisher_list(pub_filter: str | None, status_filter: str | None, as_json: bool):
    """List all submissions (optionally filtered)."""
    from marketplace.publisher_portal import PublisherPortal
    import json as _json
    portal = PublisherPortal(ROOT)
    recs = portal.list_submissions(publisher=pub_filter, status=status_filter)
    if as_json:
        click.echo(_json.dumps([r.to_dict() for r in recs], indent=2, ensure_ascii=False))
    else:
        if not recs:
            click.echo('No submissions found.')
            return
        for rec in recs:
            click.echo(f'[{rec.status:<14}] {rec.submission_id[:8]}  {rec.skill_id}  v{rec.version}  ({rec.publisher})')


@publisher.command('approve')
@click.argument('submission_id')
@click.option('--reason', default='', help='Approval note')
@click.option('--by', 'decided_by', default='etd-cli', show_default=True)
def publisher_approve(submission_id: str, reason: str, decided_by: str):
    """Approve an in-review submission."""
    from marketplace.publisher_portal import PublisherPortal
    portal = PublisherPortal(ROOT)
    try:
        rec = portal.approve(submission_id, decided_by=decided_by, reason=reason)
        click.echo(f'Approved: {rec.submission_id[:8]}  {rec.skill_id}  v{rec.version}')
    except KeyError as exc:
        click.echo(f'Error: {exc}', err=True)
        raise SystemExit(1)
    except ValueError as exc:
        click.echo(f'Error: {exc}', err=True)
        raise SystemExit(1)


@publisher.command('reject')
@click.argument('submission_id')
@click.option('--reason', required=True, help='Rejection reason (required)')
@click.option('--by', 'decided_by', default='etd-cli', show_default=True)
def publisher_reject(submission_id: str, reason: str, decided_by: str):
    """Reject an in-review submission."""
    from marketplace.publisher_portal import PublisherPortal
    portal = PublisherPortal(ROOT)
    try:
        rec = portal.reject(submission_id, reason=reason, decided_by=decided_by)
        click.echo(f'Rejected: {rec.submission_id[:8]}  {rec.skill_id}  v{rec.version}')
    except (KeyError, ValueError) as exc:
        click.echo(f'Error: {exc}', err=True)
        raise SystemExit(1)


@publisher.command('revision')
@click.argument('submission_id')
@click.option('--reason', required=True, help='What needs to be fixed')
@click.option('--by', 'decided_by', default='etd-cli', show_default=True)
def publisher_revision(submission_id: str, reason: str, decided_by: str):
    """Request revision on an in-review submission."""
    from marketplace.publisher_portal import PublisherPortal
    portal = PublisherPortal(ROOT)
    try:
        rec = portal.request_revision(submission_id, reason=reason, decided_by=decided_by)
        click.echo(f'Revision requested: {rec.submission_id[:8]}  {rec.skill_id}')
    except (KeyError, ValueError) as exc:
        click.echo(f'Error: {exc}', err=True)
        raise SystemExit(1)


@cli.command('dashboard')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON instead of ASCII')
@click.option('--watch', 'watch_n', default=0, type=int, metavar='N',
              help='Refresh N times (0 = once, -1 = loop until Ctrl-C)')
@click.option('--interval', default=5.0, show_default=True, type=float,
              help='Seconds between refreshes in watch mode')
@click.option('--events', 'last_n_events', default=10, show_default=True,
              help='Number of recent audit events to show')
def dashboard_cmd(as_json: bool, watch_n: int, interval: float, last_n_events: int):
    """Show a real-time dashboard of skills, station health, and recent events."""
    from marketplace.dashboard import Dashboard
    import json as _json
    dash = Dashboard(ROOT)
    if watch_n == -1:
        dash.watch(interval_s=interval, refresh_count=None,
                   last_n_events=last_n_events, clear_screen=not as_json)
        return
    if watch_n > 1:
        dash.watch(interval_s=interval, refresh_count=watch_n,
                   last_n_events=last_n_events, clear_screen=not as_json)
        return
    snap = dash.snapshot(last_n_events=last_n_events)
    if as_json:
        click.echo(_json.dumps(snap.to_dict(), indent=2, ensure_ascii=False))
    else:
        click.echo(snap.render_ascii())


@cli.command('sandbox-check')
@click.argument('package_path')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def sandbox_check(package_path: str, as_json: bool):
    """Static sandbox analysis of a skill package (AST scan for forbidden imports/calls)."""
    from marketplace.sandbox import SandboxChecker
    import json as _json
    p = Path(package_path)
    if not p.exists():
        click.echo(f'Error: package path does not exist: {package_path}', err=True)
        raise SystemExit(1)
    report = SandboxChecker().check(p)
    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        click.echo(report.summary())
    raise SystemExit(0 if report.passed else 1)


@cli.group()
def feed():
    """Manage multi-vendor skill feeds (register, import, verify, list)."""


@feed.command('create')
@click.option('--id', 'feed_id', required=True, help='Feed ID (e.g. acme-robotics)')
@click.option('--name', required=True, help='Human-readable feed name')
@click.option('--index', 'index_path', default=str(ROOT / 'marketplace' / 'skill_store_index.json'),
              show_default=True, help='Source skill store index JSON')
@click.option('--key', 'key_path', default=str(ROOT / 'keys' / 'etd_signing_key.hex'), show_default=True)
@click.option('--out', 'out_path', default=None, help='Output file path (default: <feed_id>.feed.json)')
@click.option('--version', 'feed_version', default='1.0.0', show_default=True)
def feed_create(feed_id: str, name: str, index_path: str, key_path: str,
                out_path: str | None, feed_version: str):
    """Create a signed vendor feed from an existing skill store index."""
    from nacl.signing import SigningKey
    from marketplace.vendor_feed import create_feed_payload
    import json as _json
    key = SigningKey(bytes.fromhex(Path(key_path).read_text().strip()))
    index = _json.loads(Path(index_path).read_text(encoding='utf-8'))
    entries = index.get('entries', [])
    payload = create_feed_payload(
        feed_id=feed_id, name=name, entries=entries,
        signing_key=key, feed_version=feed_version,
    )
    dest = Path(out_path) if out_path else Path(f'{feed_id}.feed.json')
    dest.write_text(_json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    click.echo(f'Feed written to {dest}  ({len(entries)} entries, signed)')


@feed.command('verify')
@click.argument('feed_path')
@click.option('--pubkey', 'pubkey_path', default=str(ROOT / 'keys' / 'etd_verify_key.hex'), show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def feed_verify(feed_path: str, pubkey_path: str, as_json: bool):
    """Verify the signature on a vendor feed file."""
    from marketplace.vendor_feed import verify_feed_signature
    import json as _json
    p = Path(feed_path)
    if not p.exists():
        click.echo(f'Error: feed file not found: {feed_path}', err=True)
        raise SystemExit(1)
    payload = _json.loads(p.read_text(encoding='utf-8'))
    pubkey_hex = Path(pubkey_path).read_text().strip()
    ok, reason = verify_feed_signature(payload, pubkey_hex)
    if as_json:
        click.echo(_json.dumps({'feed_id': payload.get('feedId'), 'verified': ok, 'reason': reason}, indent=2))
    else:
        mark = 'OK' if ok else 'FAIL'
        click.echo(f'Signature: {mark}  ({reason})  — {payload.get("feedId", "?")} v{payload.get("version", "?")}')
    raise SystemExit(0 if ok else 1)


@feed.command('import')
@click.argument('feed_path')
@click.option('--pubkey', 'pubkey_path', default=str(ROOT / 'keys' / 'etd_verify_key.hex'), show_default=True)
@click.option('--json', 'as_json', is_flag=True)
@click.option('--runtime', default='0.0.0', show_default=True, help='Runtime version for best-version display')
def feed_import(feed_path: str, pubkey_path: str, as_json: bool, runtime: str):
    """Load a vendor feed file, verify it, and list its skills."""
    from marketplace.vendor_feed import VendorFeed, VendorFeedManager
    import json as _json
    p = Path(feed_path)
    if not p.exists():
        click.echo(f'Error: feed file not found: {feed_path}', err=True)
        raise SystemExit(1)
    payload = _json.loads(p.read_text(encoding='utf-8'))
    feed_id = payload.get('feedId', p.stem)
    pubkey_hex = Path(pubkey_path).read_text().strip()
    mgr = VendorFeedManager()
    mgr.register_feed(VendorFeed(feed_id=feed_id, name=payload.get('name', feed_id), public_key_hex=pubkey_hex))
    record = mgr.load_feed(feed_id, payload)
    if as_json:
        click.echo(_json.dumps({
            'feed_id': record.feed_id,
            'name': record.feed_name,
            'verified': record.verified,
            'error': record.error,
            'entry_count': record.entry_count,
            'skills': mgr.list_skills(),
        }, indent=2, ensure_ascii=False))
    else:
        mark = 'verified' if record.verified else f'UNVERIFIED ({record.error})'
        click.echo(f'Feed: {record.feed_name} ({record.feed_id}) — {mark}')
        click.echo(f'  {record.entry_count} entries')
        for sk in mgr.list_skills():
            best = mgr.find_skill(sk['skillId'], runtime)
            tag = ' [best]' if best and best.version == sk['version'] else ''
            click.echo(f"  {sk['skillId']}  v{sk['version']}{tag}  ({sk['licenseModel']})")
    raise SystemExit(0 if record.verified else 1)


@cli.group()
def token():
    """Issue and verify signed entitlement tokens (Ed25519)."""


@token.command('issue')
@click.argument('skill_id')
@click.option('--station', default='*', show_default=True, help='Station ID or * for any')
@click.option('--org', default='etd-operator', show_default=True, help='Operator organisation name')
@click.option('--ttl', default=365, show_default=True, type=int, help='Token validity in days')
@click.option('--key', 'key_path', default=str(ROOT / 'keys' / 'etd_signing_key.hex'), show_default=True)
@click.option('--json', 'as_json', is_flag=True, help='Print token as JSON envelope')
def token_issue(skill_id: str, station: str, org: str, ttl: int, key_path: str, as_json: bool):
    """Issue a signed entitlement token for SKILL_ID."""
    from nacl.signing import SigningKey
    from marketplace.entitlement_token import issue_token
    key = SigningKey(bytes.fromhex(Path(key_path).read_text().strip()))
    tok = issue_token(
        skill_id=skill_id,
        station_id=station,
        operator_org=org,
        signing_key=key,
        ttl_days=ttl,
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps({'token': tok, 'skill_id': skill_id, 'station_id': station,
                                'operator_org': org, 'ttl_days': ttl}, indent=2))
    else:
        click.echo(click.style('Issued entitlement token:', bold=True))
        click.echo(f'  Skill    : {skill_id}')
        click.echo(f'  Station  : {station}')
        click.echo(f'  Org      : {org}')
        click.echo(f'  Valid for: {ttl} days')
        click.echo(f'  Token    : {tok}')


@token.command('verify')
@click.argument('token_str')
@click.argument('skill_id')
@click.option('--station', default='*', show_default=True)
@click.option('--pubkey', 'pubkey_path', default=str(ROOT / 'keys' / 'etd_verify_key.hex'), show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def token_verify(token_str: str, skill_id: str, station: str, pubkey_path: str, as_json: bool):
    """Verify a signed entitlement TOKEN_STR for SKILL_ID."""
    from nacl.signing import VerifyKey
    from marketplace.entitlement_token import verify_token
    verify_key = VerifyKey(bytes.fromhex(Path(pubkey_path).read_text().strip()))
    valid, reason, tok = verify_token(token_str, verify_key, skill_id, station)
    if as_json:
        import json as _json
        payload = {'valid': valid, 'reason': reason}
        if tok:
            payload['token'] = {'skill_id': tok.skill_id, 'station_id': tok.station_id,
                                 'expiry': tok.expiry, 'operator_org': tok.operator_org,
                                 'issued_at': tok.issued_at}
        click.echo(_json.dumps(payload, indent=2))
    else:
        label = click.style('VALID', fg='green', bold=True) if valid else click.style('INVALID', fg='red', bold=True)
        click.echo(f'Token: {label}  ({reason})')
        if tok:
            click.echo(f'  Skill    : {tok.skill_id}')
            click.echo(f'  Station  : {tok.station_id}')
            click.echo(f'  Expiry   : {tok.expiry}')
            click.echo(f'  Org      : {tok.operator_org}')
    raise SystemExit(0 if valid else 1)


@cli.command()
@click.option('--out-dir', default='keys', show_default=True)
def keygen(out_dir: str):
    """Generate an Ed25519 keypair for signing skill packages."""
    from scripts.generate_keypair import generate
    generate(Path(out_dir))


@cli.command()
@click.option('--host', default='0.0.0.0', show_default=True)
@click.option('--port', default=8080, show_default=True)
@click.option('--reload', 'hot_reload', is_flag=True, help='Enable hot reload (dev mode)')
def serve(host: str, port: int, hot_reload: bool):
    """Start the ETD Skill Store REST API server."""
    import uvicorn
    click.echo(f'Starting ETD API server on http://{host}:{port}')
    click.echo(f'  Docs: http://{host}:{port}/docs')
    uvicorn.run('api.app:app', host=host, port=port, reload=hot_reload)


@cli.group()
def compose():
    """Validate and run composed multi-step skill manifests."""


@compose.command('validate')
@click.argument('package_path')
@click.option('--json', 'as_json', is_flag=True)
def compose_validate(package_path: str, as_json: bool):
    """Validate a composed skill package at PACKAGE_PATH."""
    import json as _json
    from marketplace.composer import SkillComposer, load_composed_skill
    from marketplace.skill_store import SkillStore
    p = Path(package_path)
    try:
        composed = load_composed_skill(p)
    except FileNotFoundError as exc:
        click.echo(click.style(f'Error: {exc}', fg='red'), err=True)
        raise SystemExit(1)
    store = SkillStore(ROOT)
    composer = SkillComposer(store)
    issues = composer.validate(composed)
    ok = len(issues) == 0
    if as_json:
        click.echo(_json.dumps({
            'skill_id': composed.skill_id,
            'version': composed.version,
            'valid': ok,
            'issues': issues,
            'step_count': len(composed.steps),
        }, indent=2))
    else:
        label = click.style('VALID', fg='green', bold=True) if ok else click.style('INVALID', fg='red', bold=True)
        click.echo(f'Composed skill: {label}  {composed.skill_id} v{composed.version}')
        click.echo(f'  Steps: {len(composed.steps)}')
        if issues:
            for iss in issues:
                click.echo(click.style(f'  ✗ {iss}', fg='red'))
        else:
            click.echo(click.style('  All checks passed.', fg='green'))
    raise SystemExit(0 if ok else 1)


@compose.command('run')
@click.argument('package_path')
@click.option('--json', 'as_json', is_flag=True)
def compose_run(package_path: str, as_json: bool):
    """Dry-run a composed skill package at PACKAGE_PATH (mock executor)."""
    import json as _json
    from marketplace.composer import SkillComposer, load_composed_skill
    p = Path(package_path)
    try:
        composed = load_composed_skill(p)
    except FileNotFoundError as exc:
        click.echo(click.style(f'Error: {exc}', fg='red'), err=True)
        raise SystemExit(1)
    composer = SkillComposer()
    result = composer.run(composed)
    if as_json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        click.echo(result.summary())
    raise SystemExit(0 if result.succeeded else 1)


@cli.group()
def platform():
    """Cross-platform humanoid compatibility checks (humanoid-first marketplace)."""


@platform.command('list')
@click.option('--json', 'as_json', is_flag=True)
def platform_list(as_json: bool):
    """List all registered robot platforms."""
    import json as _json
    from marketplace.cross_platform import HumanoidRegistry
    reg = HumanoidRegistry()
    platforms = reg.list_platforms()
    if as_json:
        click.echo(_json.dumps([p.to_dict() for p in platforms], indent=2))
    else:
        click.echo(f'{"ID":<20} {"Name":<38} {"Class":<14} {"Families"}')
        click.echo('─' * 90)
        for p in platforms:
            fam = ', '.join(sorted(p.families))
            click.echo(f'{p.platform_id:<20} {p.name:<38} {p.robot_class:<14} {fam}')
        click.echo(f'\n{len(platforms)} platform(s) registered.')


@platform.command('check')
@click.argument('package_path')
@click.option('--source', required=True, help='Source platform ID (skill was written for)')
@click.option('--target', required=True, help='Target platform ID to check portability to')
@click.option('--json', 'as_json', is_flag=True)
def platform_check(package_path: str, source: str, target: str, as_json: bool):
    """Check if a skill package is portable from SOURCE to TARGET platform."""
    import json as _json
    from marketplace.cross_platform import HumanoidRegistry, load_skill_info
    p = Path(package_path)
    try:
        skill_info = load_skill_info(p)
    except FileNotFoundError as exc:
        click.echo(click.style(f'Error: {exc}', fg='red'), err=True)
        raise SystemExit(1)
    reg = HumanoidRegistry()
    result = reg.check_compat(skill_info, source=source, target=target)
    if as_json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        label = (click.style('COMPATIBLE', fg='green', bold=True)
                 if result.compatible
                 else click.style('INCOMPATIBLE', fg='red', bold=True))
        click.echo(f'{label}  {result.skill_id}  {source} → {target}')
        if result.missing_primitives:
            click.echo(click.style(
                f'  Missing primitives: {", ".join(result.missing_primitives)}', fg='red'))
        if result.missing_capability_flags:
            click.echo(f'  Missing capabilities: {", ".join(result.missing_capability_flags)}')
        for t in result.topic_remappings.items():
            click.echo(f'  Remap: {t[0]} → {t[1]}')
        for w in result.warnings:
            click.echo(click.style(f'  ⚠  {w}', fg='yellow'))
        for n in result.adaptation_notes:
            click.echo(f'  ℹ  {n}')
    raise SystemExit(0 if result.compatible else 1)


@platform.command('matrix')
@click.option('--skill', 'package_path', default=None,
              help='Skill package path — if set, evaluate this skill across all pairs')
@click.option('--family', 'family_filter', default=None,
              help='Filter to platforms supporting this family')
@click.option('--json', 'as_json', is_flag=True)
def platform_matrix(package_path: Optional[str], family_filter: Optional[str], as_json: bool):
    """Show a cross-platform compatibility matrix."""
    import json as _json
    from marketplace.cross_platform import HumanoidRegistry, load_skill_info
    reg = HumanoidRegistry()
    skill_info = None
    if package_path:
        try:
            skill_info = load_skill_info(Path(package_path))
        except FileNotFoundError as exc:
            click.echo(click.style(f'Error: {exc}', fg='red'), err=True)
            raise SystemExit(1)
    families = {family_filter} if family_filter else None
    if as_json:
        rows = reg.compat_matrix(skill_info=skill_info, families=families)
        click.echo(_json.dumps(rows, indent=2))
    else:
        click.echo(reg.render_matrix_ascii(skill_info=skill_info, families=families))


_DEFAULT_CACHE_DIR = str(ROOT / 'robot_cache')


@cli.group()
def onrobot():
    """On-robot embedded skill store — offline cache and mesh sync."""


@onrobot.group('cache')
def onrobot_cache():
    """Manage the on-robot entitlement and manifest cache."""


@onrobot_cache.command('list')
@click.option('--cache-dir', default=_DEFAULT_CACHE_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def onrobot_cache_list(cache_dir: str, as_json: bool):
    """List skills available in the offline cache."""
    import json as _json
    from marketplace.onrobot_store import OnRobotStore
    store = OnRobotStore(cache_dir=Path(cache_dir))
    if as_json:
        click.echo(_json.dumps(store.to_dict(), indent=2))
    else:
        click.echo(store.summary())
        offline = store.get_offline_skills()
        if offline:
            click.echo('\n  Offline skills:')
            for sid in offline:
                click.echo(f'    • {sid}')
        else:
            click.echo('  (no skills fully available offline)')


@onrobot_cache.command('add')
@click.argument('skill_id')
@click.option('--token', 'token_str', required=True, help='Signed entitlement token string')
@click.option('--station', default='*', show_default=True)
@click.option('--org', 'operator_org', default='', help='Operator org (informational)')
@click.option('--expiry', required=True, help='Expiry datetime ISO 8601 UTC e.g. 2027-01-01T00:00:00Z')
@click.option('--cache-dir', default=_DEFAULT_CACHE_DIR, show_default=True)
def onrobot_cache_add(skill_id: str, token_str: str, station: str,
                      operator_org: str, expiry: str, cache_dir: str):
    """Cache an entitlement token for offline use."""
    from marketplace.onrobot_store import OnRobotStore
    store = OnRobotStore(cache_dir=Path(cache_dir))
    ok, reason = store.entitlement_cache.add(
        token_str=token_str,
        skill_id=skill_id,
        station_id=station,
        operator_org=operator_org,
        expiry=expiry,
    )
    if ok:
        click.echo(click.style(f'Cached: {skill_id} @ {station}', fg='green'))
    else:
        click.echo(click.style(f'Failed to cache: {reason}', fg='red'), err=True)
        raise SystemExit(1)


@onrobot_cache.command('evict')
@click.option('--cache-dir', default=_DEFAULT_CACHE_DIR, show_default=True)
def onrobot_cache_evict(cache_dir: str):
    """Evict expired entitlements from the local cache."""
    from marketplace.onrobot_store import OnRobotStore
    store = OnRobotStore(cache_dir=Path(cache_dir))
    removed = store.evict_expired_entitlements()
    click.echo(f'Evicted {removed} expired entitlement(s).')


@onrobot.group('sync')
def onrobot_sync():
    """Manage mesh sync between fleet peers."""


@onrobot_sync.command('status')
@click.option('--cache-dir', default=_DEFAULT_CACHE_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def onrobot_sync_status(cache_dir: str, as_json: bool):
    """Show mesh sync status for all registered peers."""
    import json as _json
    from marketplace.onrobot_store import OnRobotStore
    store = OnRobotStore(cache_dir=Path(cache_dir))
    rows = store.mesh.sync_status()
    if as_json:
        click.echo(_json.dumps(rows, indent=2))
    else:
        if not rows:
            click.echo('No mesh peers registered.')
        else:
            for r in rows:
                last = r.get('last_sync_at') or 'never'
                skills = ', '.join(r.get('synced_skill_ids', [])) or '—'
                click.echo(
                    f"  {r['peer_node_id']:<20}  last={last}  "
                    f"synced={r.get('sync_count', 0)}x  skills={skills}"
                )


_DEFAULT_FLEET_DIR = str(ROOT / 'fleet')


@cli.group()
def fleet():
    """Manage a fleet of robot nodes — register nodes, deploy skills, check health."""


@fleet.group('nodes')
def fleet_nodes():
    """Fleet node registry commands."""


@fleet_nodes.command('list')
@click.option('--fleet-dir', default=_DEFAULT_FLEET_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def fleet_nodes_list(fleet_dir: str, as_json: bool):
    """List all registered fleet nodes."""
    import json as _json
    from marketplace.fleet_manager import FleetManager
    fm = FleetManager(data_dir=Path(fleet_dir))
    nodes = fm.list_nodes()
    if as_json:
        click.echo(_json.dumps([n.to_dict() for n in nodes], indent=2))
    else:
        if not nodes:
            click.echo('No nodes registered.')
            return
        click.echo(f'{"NODE ID":<22} {"STATION":<18} {"PLATFORM":<18} {"STATUS":<10} SKILLS')
        click.echo('─' * 85)
        for n in nodes:
            skills = ', '.join(n.installed_skills) or '—'
            click.echo(f'{n.node_id:<22} {n.station_id:<18} {n.platform_id:<18} '
                       f'{n.status:<10} {skills}')
        click.echo(f'\n{len(nodes)} node(s) registered.')


@fleet_nodes.command('register')
@click.argument('node_id')
@click.option('--station', required=True, help='Station ID for this node')
@click.option('--platform', 'platform_id', required=True,
              help='Platform ID (e.g. atlas, unitree_g1)')
@click.option('--fleet-dir', default=_DEFAULT_FLEET_DIR, show_default=True)
def fleet_nodes_register(node_id: str, station: str, platform_id: str, fleet_dir: str):
    """Register a robot node in the fleet."""
    from marketplace.fleet_manager import FleetManager, RobotNode
    fm = FleetManager(data_dir=Path(fleet_dir))
    fm.register_node(RobotNode(node_id=node_id, station_id=station,
                                platform_id=platform_id))
    click.echo(click.style(f'Registered: {node_id} @ {station} [{platform_id}]', fg='green'))


@fleet_nodes.command('unregister')
@click.argument('node_id')
@click.option('--fleet-dir', default=_DEFAULT_FLEET_DIR, show_default=True)
def fleet_nodes_unregister(node_id: str, fleet_dir: str):
    """Unregister a robot node from the fleet."""
    from marketplace.fleet_manager import FleetManager
    fm = FleetManager(data_dir=Path(fleet_dir))
    removed = fm.unregister_node(node_id)
    if removed:
        click.echo(f'Unregistered: {node_id}')
    else:
        click.echo(click.style(f'Node not found: {node_id}', fg='yellow'))
        raise SystemExit(1)


@fleet.command('deploy')
@click.argument('skill_id')
@click.option('--version', default='0.1.0', show_default=True)
@click.option('--nodes', 'node_ids', default='',
              help='Comma-separated node IDs (empty = all nodes)')
@click.option('--fleet-dir', default=_DEFAULT_FLEET_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def fleet_deploy(skill_id: str, version: str, node_ids: str,
                 fleet_dir: str, as_json: bool):
    """Deploy a skill to fleet nodes."""
    import json as _json
    from marketplace.fleet_manager import FleetManager
    fm = FleetManager(data_dir=Path(fleet_dir))
    targets = [n.strip() for n in node_ids.split(',') if n.strip()] \
        if node_ids else [n.node_id for n in fm.list_nodes()]
    if not targets:
        click.echo(click.style('No target nodes available.', fg='yellow'))
        raise SystemExit(1)
    deployment = fm.deploy(skill_id=skill_id, version=version,
                           target_node_ids=targets)
    if as_json:
        click.echo(_json.dumps(deployment.to_dict(), indent=2))
    else:
        click.echo(deployment.summary())
    raise SystemExit(0 if deployment.status in ('completed', 'partial') else 1)


@fleet.command('status')
@click.option('--fleet-dir', default=_DEFAULT_FLEET_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def fleet_status(fleet_dir: str, as_json: bool):
    """Show fleet health snapshot."""
    import json as _json
    from marketplace.fleet_manager import FleetManager
    fm = FleetManager(data_dir=Path(fleet_dir))
    snap = fm.fleet_status()
    if as_json:
        click.echo(_json.dumps(snap.to_dict(), indent=2))
    else:
        click.echo(snap.render_ascii())


@fleet.command('deployments')
@click.option('--skill', 'skill_id', default=None)
@click.option('--status', 'status_filter', default=None)
@click.option('--fleet-dir', default=_DEFAULT_FLEET_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def fleet_deployments(skill_id: Optional[str], status_filter: Optional[str],
                      fleet_dir: str, as_json: bool):
    """List fleet deployments."""
    import json as _json
    from marketplace.fleet_manager import FleetManager
    fm = FleetManager(data_dir=Path(fleet_dir))
    deps = fm.list_deployments(skill_id=skill_id, status=status_filter)
    if as_json:
        click.echo(_json.dumps([d.to_dict() for d in deps], indent=2))
    else:
        if not deps:
            click.echo('No deployments found.')
            return
        for d in deps:
            click.echo(
                f'[{d.status:<11}] {d.deployment_id[:8]}  '
                f'{d.skill_id} v{d.version}  '
                f'{d.nodes_succeeded}✓/{d.nodes_failed}✗'
            )


# ── dependency resolver ───────────────────────────────────────────────────────

_DEFAULT_DEPS_DIR = str(Path(__file__).resolve().parent / 'deps')


@cli.group()
def deps():
    """Skill dependency resolver: register, inspect, and verify dependencies."""


@deps.command('register')
@click.argument('skill_id')
@click.option('--requires', 'requires', multiple=True,
              metavar='SKILL_ID[:VERSION_CONSTRAINT][:optional]',
              help='Dependency spec (repeat for multiple). Append :optional for optional deps.')
@click.option('--deps-dir', default=_DEFAULT_DEPS_DIR, show_default=True)
def deps_register(skill_id: str, requires: tuple, deps_dir: str):
    """Register dependency declarations for a skill.

    Example: --requires etd.pick:>=0.1.0  --requires etd.inspect::optional
    """
    from marketplace.dependency_resolver import DependencyStore, SkillDependency
    parsed = []
    for r in requires:
        parts = r.split(':')
        dep_id = parts[0]
        version_constraint = parts[1] if len(parts) > 1 else ''
        optional = (len(parts) > 2 and parts[2].lower() == 'optional')
        parsed.append(SkillDependency(skill_id=dep_id,
                                      version_constraint=version_constraint,
                                      optional=optional))
    DependencyStore(Path(deps_dir)).register(skill_id, parsed)
    click.echo(click.style(
        f'Registered {len(parsed)} dep(s) for {skill_id}', fg='green'))


@deps.command('list')
@click.option('--deps-dir', default=_DEFAULT_DEPS_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def deps_list(deps_dir: str, as_json: bool):
    """List all registered skill dependency declarations."""
    import json as _json
    from marketplace.dependency_resolver import DependencyStore
    store = DependencyStore(Path(deps_dir))
    skills = store.list_skills()
    if as_json:
        data = {s: [d.to_dict() for d in (store.get(s) or [])]
                for s in skills}
        click.echo(_json.dumps(data, indent=2))
    else:
        if not skills:
            click.echo('No dependency declarations registered.')
            return
        for s in skills:
            d_list = store.get(s) or []
            dep_str = ', '.join(
                f'{d.skill_id}{"?" if d.optional else ""}' for d in d_list
            ) or '(none)'
            click.echo(f'  {s:45s}  →  {dep_str}')


@deps.command('order')
@click.argument('skill_id')
@click.option('--deps-dir', default=_DEFAULT_DEPS_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def deps_order(skill_id: str, deps_dir: str, as_json: bool):
    """Print the topological install order for a skill."""
    import json as _json
    from marketplace.dependency_resolver import DependencyStore, CyclicDependencyError
    store = DependencyStore(Path(deps_dir))
    try:
        order = store.resolver().install_order(skill_id)
    except CyclicDependencyError as exc:
        click.echo(click.style(f'Cycle detected: {exc}', fg='red'))
        raise SystemExit(1)
    if as_json:
        click.echo(_json.dumps(order, indent=2))
    else:
        for i, s in enumerate(order, 1):
            marker = ' ← install target' if s == skill_id else ''
            click.echo(f'  {i:2d}. {s}{marker}')


@deps.command('tree')
@click.argument('skill_id')
@click.option('--deps-dir', default=_DEFAULT_DEPS_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def deps_tree(skill_id: str, deps_dir: str, as_json: bool):
    """Print the dependency tree for a skill."""
    import json as _json
    from marketplace.dependency_resolver import DependencyStore

    store = DependencyStore(Path(deps_dir))
    tree = store.resolver().dependency_tree(skill_id)

    if as_json:
        click.echo(_json.dumps(tree, indent=2))
    else:
        def _render(node: dict, indent: int = 0) -> None:
            prefix = '  ' * indent
            opt = ' [optional]' if node.get('optional') else ''
            cycle = ' [CYCLE]' if node.get('cycle') else ''
            click.echo(f'{prefix}{node["skill_id"]}{opt}{cycle}')
            for child in node.get('deps', []):
                _render(child, indent + 1)
        _render(tree)


@deps.command('check')
@click.argument('skill_id')
@click.option('--available', 'available', default='',
              help='Comma-separated list of available skill IDs')
@click.option('--deps-dir', default=_DEFAULT_DEPS_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def deps_check(skill_id: str, available: str, deps_dir: str, as_json: bool):
    """Check whether all required deps of a skill are available."""
    import json as _json
    from marketplace.dependency_resolver import DependencyStore
    avail_set = {s.strip() for s in available.split(',') if s.strip()}
    store = DependencyStore(Path(deps_dir))
    satisfied, missing = store.resolver().check_satisfied(skill_id, avail_set)
    if as_json:
        click.echo(_json.dumps({'satisfied': satisfied, 'missing': missing},
                               indent=2))
    else:
        if satisfied:
            click.echo(click.style('All dependencies satisfied.', fg='green'))
        else:
            click.echo(click.style(
                f'Missing {len(missing)} required dep(s): '
                + ', '.join(missing), fg='red'))
    raise SystemExit(0 if satisfied else 1)


@deps.command('cycles')
@click.option('--deps-dir', default=_DEFAULT_DEPS_DIR, show_default=True)
def deps_cycles(deps_dir: str):
    """Detect dependency cycles in the full graph."""
    from marketplace.dependency_resolver import DependencyStore
    store = DependencyStore(Path(deps_dir))
    cycles = store.resolver().cycles()
    if not cycles:
        click.echo(click.style('No cycles detected.', fg='green'))
    else:
        click.echo(click.style(f'{len(cycles)} cycle(s) detected:', fg='red'))
        for c in cycles:
            click.echo('  ' + ' → '.join(c))
        raise SystemExit(1)


# ── scheduler ────────────────────────────────────────────────────────────────

_DEFAULT_SCHED_DIR = str(Path(__file__).resolve().parent / 'scheduler')


@cli.group()
def schedule():
    """Skill execution scheduler: add, list, pause, and record jobs."""


@schedule.command('add')
@click.argument('skill_id')
@click.option('--node', 'node_id', required=True, help='Target robot node ID')
@click.option('--station', 'station_id', default='default', show_default=True)
@click.option('--type', 'schedule_type',
              type=click.Choice(['interval', 'once']), default='interval',
              show_default=True)
@click.option('--interval', 'interval_minutes', default=60, type=int,
              show_default=True, help='Interval in minutes (interval jobs)')
@click.option('--run-at', 'run_at', default=None,
              help='ISO 8601 datetime for one-shot jobs')
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def schedule_add(skill_id: str, node_id: str, station_id: str,
                 schedule_type: str, interval_minutes: int,
                 run_at: Optional[str], sched_dir: str, as_json: bool):
    """Schedule a skill execution on a node."""
    import json as _json
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    try:
        job = sched.add_job(
            skill_id=skill_id,
            node_id=node_id,
            station_id=station_id,
            schedule_type=schedule_type,
            interval_minutes=interval_minutes,
            run_at=run_at,
        )
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    if as_json:
        click.echo(_json.dumps(job.to_dict(), indent=2))
    else:
        info = (f'every {interval_minutes}m'
                if schedule_type == 'interval' else f'once at {run_at}')
        click.echo(click.style(
            f'Scheduled: {job.job_id[:8]}  {skill_id} → {node_id}  [{info}]',
            fg='green'))


@schedule.command('list')
@click.option('--status', 'status_filter',
              type=click.Choice(['active', 'paused', 'done']), default=None)
@click.option('--skill', 'skill_id', default=None)
@click.option('--node', 'node_id', default=None)
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def schedule_list(status_filter: Optional[str], skill_id: Optional[str],
                  node_id: Optional[str], sched_dir: str, as_json: bool):
    """List scheduled jobs."""
    import json as _json
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    jobs = sched.list_jobs(status=status_filter, skill_id=skill_id,
                           node_id=node_id)
    if as_json:
        click.echo(_json.dumps([j.to_dict() for j in jobs], indent=2))
    else:
        if not jobs:
            click.echo('No scheduled jobs found.')
            return
        for j in jobs:
            interval = (f'/{j.interval_minutes}m'
                        if j.schedule_type == 'interval' else '/once')
            click.echo(
                f'[{j.status:<7}] {j.job_id[:8]}  '
                f'{j.skill_id} → {j.node_id}{interval}  '
                f'runs={j.run_count}  next={j.next_run_at or "-"}'
            )


@schedule.command('remove')
@click.argument('job_id')
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
def schedule_remove(job_id: str, sched_dir: str):
    """Remove a scheduled job."""
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    removed = sched.remove_job(job_id)
    if removed:
        click.echo(f'Removed: {job_id}')
    else:
        click.echo(click.style(f'Job not found: {job_id}', fg='yellow'))
        raise SystemExit(1)


@schedule.command('pause')
@click.argument('job_id')
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
def schedule_pause(job_id: str, sched_dir: str):
    """Pause an active scheduled job."""
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    ok = sched.pause_job(job_id)
    if ok:
        click.echo(f'Paused: {job_id}')
    else:
        click.echo(click.style(f'Cannot pause job: {job_id}', fg='yellow'))
        raise SystemExit(1)


@schedule.command('resume')
@click.argument('job_id')
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
def schedule_resume(job_id: str, sched_dir: str):
    """Resume a paused scheduled job."""
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    ok = sched.resume_job(job_id)
    if ok:
        click.echo(f'Resumed: {job_id}')
    else:
        click.echo(click.style(f'Cannot resume job: {job_id}', fg='yellow'))
        raise SystemExit(1)


@schedule.command('due')
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def schedule_due(sched_dir: str, as_json: bool):
    """List jobs that are due to run right now."""
    import json as _json
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    jobs = sched.due_jobs()
    if as_json:
        click.echo(_json.dumps([j.to_dict() for j in jobs], indent=2))
    else:
        if not jobs:
            click.echo('No jobs due.')
            return
        for j in jobs:
            click.echo(f'{j.job_id[:8]}  {j.skill_id} → {j.node_id}')


@schedule.command('run')
@click.argument('job_id')
@click.option('--success/--failed', default=True)
@click.option('--duration-ms', 'duration_ms', default=0, type=int)
@click.option('--error', 'error', default='')
@click.option('--sched-dir', default=_DEFAULT_SCHED_DIR, show_default=True)
def schedule_run(job_id: str, success: bool, duration_ms: int,
                 error: str, sched_dir: str):
    """Record a completed run result for a scheduled job."""
    from marketplace.scheduler import SkillScheduler
    sched = SkillScheduler(Path(sched_dir))
    result = sched.record_run(job_id, success=success,
                              duration_ms=duration_ms, error=error)
    if result is None:
        click.echo(click.style(f'Job not found: {job_id}', fg='yellow'))
        raise SystemExit(1)
    status_str = 'success' if success else 'failed'
    click.echo(f'Recorded run: {job_id[:8]}  [{status_str}]  {duration_ms} ms')


# ── quota ─────────────────────────────────────────────────────────────────────

_DEFAULT_QUOTA_DIR = str(Path(__file__).resolve().parent / 'quota')


@cli.group()
def quota():
    """Execution quota & rate limiting: policies, checks, and usage."""


@quota.command('set')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--max-per-hour', 'max_per_hour', default=None, type=int)
@click.option('--max-per-day', 'max_per_day', default=None, type=int)
@click.option('--burst', 'burst_allowance', default=0, type=int, show_default=True)
@click.option('--disabled', is_flag=True, help='Create policy in disabled state')
@click.option('--quota-dir', default=_DEFAULT_QUOTA_DIR, show_default=True)
def quota_set(skill_id: str, node_id: str, max_per_hour: Optional[int],
              max_per_day: Optional[int], burst_allowance: int,
              disabled: bool, quota_dir: str):
    """Create or update a quota policy for a skill."""
    from marketplace.quota_manager import QuotaManager, QuotaPolicy
    mgr = QuotaManager(Path(quota_dir))
    policy = QuotaPolicy(
        skill_id=skill_id,
        node_id=node_id,
        max_per_hour=max_per_hour,
        max_per_day=max_per_day,
        burst_allowance=burst_allowance,
        enabled=not disabled,
    )
    mgr.set_policy(policy)
    parts = [f'skill={skill_id}', f'node={node_id}']
    if max_per_hour is not None:
        parts.append(f'max/h={max_per_hour}')
    if max_per_day is not None:
        parts.append(f'max/d={max_per_day}')
    if burst_allowance:
        parts.append(f'burst={burst_allowance}')
    click.echo(click.style('Policy set: ' + '  '.join(parts), fg='green'))


@quota.command('list')
@click.option('--quota-dir', default=_DEFAULT_QUOTA_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def quota_list(quota_dir: str, as_json: bool):
    """List all quota policies."""
    import json as _json
    from marketplace.quota_manager import QuotaManager
    mgr = QuotaManager(Path(quota_dir))
    policies = mgr.list_policies()
    if as_json:
        click.echo(_json.dumps([p.to_dict() for p in policies], indent=2))
    else:
        if not policies:
            click.echo('No policies defined.')
            return
        for p in policies:
            status = '' if p.enabled else ' [DISABLED]'
            parts = [f'{p.skill_id}  node={p.node_id}']
            if p.max_per_hour is not None:
                parts.append(f'max/h={p.max_per_hour}')
            if p.max_per_day is not None:
                parts.append(f'max/d={p.max_per_day}')
            if p.burst_allowance:
                parts.append(f'burst={p.burst_allowance}')
            click.echo('  '.join(parts) + status)


@quota.command('remove')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--quota-dir', default=_DEFAULT_QUOTA_DIR, show_default=True)
def quota_remove(skill_id: str, node_id: str, quota_dir: str):
    """Remove a quota policy."""
    from marketplace.quota_manager import QuotaManager
    mgr = QuotaManager(Path(quota_dir))
    removed = mgr.remove_policy(skill_id, node_id)
    if removed:
        click.echo(f'Removed policy: {skill_id}  node={node_id}')
    else:
        click.echo(click.style(f'No policy found: {skill_id}', fg='yellow'))
        raise SystemExit(1)


@quota.command('check')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--quota-dir', default=_DEFAULT_QUOTA_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def quota_check(skill_id: str, node_id: str, quota_dir: str, as_json: bool):
    """Check whether an execution is allowed under the current policy."""
    import json as _json
    from marketplace.quota_manager import QuotaManager
    mgr = QuotaManager(Path(quota_dir))
    result = mgr.check(skill_id, node_id)
    if as_json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        color = 'green' if result.allowed else 'red'
        click.echo(click.style(f'{"ALLOWED" if result.allowed else "BLOCKED"}  reason={result.reason}', fg=color))
        click.echo(f'  Used last hour: {result.used_last_hour}   '
                   f'remaining: {result.remaining_hour}')
        click.echo(f'  Used last day:  {result.used_last_day}   '
                   f'remaining: {result.remaining_day}')
    raise SystemExit(0 if result.allowed else 1)


@quota.command('usage')
@click.option('--skill', 'skill_id', default=None)
@click.option('--node', 'node_id', default=None)
@click.option('--quota-dir', default=_DEFAULT_QUOTA_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def quota_usage(skill_id: Optional[str], node_id: Optional[str],
                quota_dir: str, as_json: bool):
    """Show rolling-window execution usage."""
    import json as _json
    from marketplace.quota_manager import QuotaManager
    mgr = QuotaManager(Path(quota_dir))
    rows = mgr.usage(skill_id=skill_id, node_id=node_id)
    if as_json:
        click.echo(_json.dumps(rows, indent=2))
    else:
        if not rows:
            click.echo('No usage recorded.')
            return
        for r in rows:
            click.echo(
                f'{r["skill_id"]:40s}  node={r["node_id"]:12s}  '
                f'h={r["used_last_hour"]:4d}  d={r["used_last_day"]:4d}  '
                f'total={r["total_recorded"]}'
            )


# ── ab testing ───────────────────────────────────────────────────────────────

_DEFAULT_AB_STORE = str(Path(__file__).resolve().parent / 'ab' / 'experiments.json')


@cli.group()
def ab():
    """A/B testing: create, route, analyse, and conclude experiments."""


@ab.command('create')
@click.option('--name', required=True, help='Experiment name')
@click.option('--variant', 'variants', multiple=True, required=True,
              metavar='SKILL:VERSION:WEIGHT:LABEL',
              help='Variant spec (repeat for each arm)')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def ab_create(name: str, variants: tuple, store_path: str, as_json: bool):
    """Create a new A/B experiment.

    Each --variant is SKILL:VERSION:WEIGHT:LABEL,
    e.g. --variant etd.pick:0.1.0:0.5:control
    """
    import json as _json
    from marketplace.ab_testing import ABExperiment, ABVariant, ABExperimentStore
    parsed = []
    for v in variants:
        parts = v.split(':')
        if len(parts) < 2:
            click.echo(click.style(f'Bad variant spec: {v!r}', fg='red'))
            raise SystemExit(1)
        skill_id, version = parts[0], parts[1]
        weight = float(parts[2]) if len(parts) > 2 else 1.0
        label = parts[3] if len(parts) > 3 else ''
        parsed.append(ABVariant(skill_id=skill_id, version=version,
                                weight=weight, label=label))
    exp = ABExperiment.make(name=name, variants=parsed)
    ABExperimentStore(Path(store_path)).save(exp)
    if as_json:
        click.echo(_json.dumps(exp.to_dict(), indent=2))
    else:
        click.echo(click.style(f'Created: {exp.experiment_id}  "{exp.name}"', fg='green'))
        for v in exp.variants:
            click.echo(f'  [{v.label or "variant"}]  {v.skill_id} v{v.version}  w={v.weight}')


@ab.command('list')
@click.option('--status', 'status_filter', default=None,
              type=click.Choice(['active', 'paused', 'concluded']))
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def ab_list(status_filter: Optional[str], store_path: str, as_json: bool):
    """List A/B experiments."""
    import json as _json
    from marketplace.ab_testing import ABExperimentStore
    store = ABExperimentStore(Path(store_path))
    exps = store.list_experiments(status=status_filter)
    if as_json:
        click.echo(_json.dumps([e.to_dict() for e in exps], indent=2))
    else:
        if not exps:
            click.echo('No experiments found.')
            return
        for e in exps:
            click.echo(f'[{e.status:<10}] {e.experiment_id[:8]}  "{e.name}"  '
                       f'{len(e.variants)} variants')


@ab.command('status')
@click.argument('experiment_id')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def ab_status(experiment_id: str, store_path: str, as_json: bool):
    """Show details for one experiment."""
    import json as _json
    from marketplace.ab_testing import ABExperimentStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    if as_json:
        click.echo(_json.dumps(exp.to_dict(), indent=2))
    else:
        click.echo(f'{exp.name}  [{exp.status}]')
        click.echo(f'ID: {exp.experiment_id}')
        for v in exp.variants:
            click.echo(f'  [{v.label or "variant"}]  {v.skill_id} v{v.version}  w={v.weight}')
        if exp.winner_label:
            click.echo(f'Winner: {exp.winner_label}')


@ab.command('route')
@click.argument('experiment_id')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
def ab_route(experiment_id: str, store_path: str):
    """Print the chosen variant for one execution (weighted random)."""
    from marketplace.ab_testing import ABExperimentStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    try:
        v = exp.route()
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    click.echo(f'{v.skill_id}:{v.version}  [{v.label}]')


@ab.command('results')
@click.argument('experiment_id')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
@click.option('--telemetry', 'tel_path',
              default=str(Path(__file__).resolve().parent / 'telemetry' / 'executions.jsonl'),
              show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def ab_results(experiment_id: str, store_path: str, tel_path: str, as_json: bool):
    """Compare variant results from telemetry data."""
    import json as _json
    from marketplace.ab_testing import ABExperimentStore, ABAnalyzer
    from marketplace.telemetry_analytics import TelemetryStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    analyzer = ABAnalyzer(TelemetryStore(Path(tel_path)))
    cmp = analyzer.compare(exp)
    if as_json:
        click.echo(_json.dumps(cmp, indent=2))
    else:
        click.echo(f'{exp.name}  [{exp.status}]')
        for v in cmp['variants']:
            click.echo(
                f'  [{v["label"] or "variant":12}]  '
                f'{v["execution_count"]:4d} runs  '
                f'{v["success_rate"]:.0%} ok  '
                f'mean={v["mean_duration_ms"]:.0f} ms  '
                f'p95={v["p95_ms"]:.0f} ms'
            )


@ab.command('recommend')
@click.argument('experiment_id')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
@click.option('--telemetry', 'tel_path',
              default=str(Path(__file__).resolve().parent / 'telemetry' / 'executions.jsonl'),
              show_default=True)
def ab_recommend(experiment_id: str, store_path: str, tel_path: str):
    """Recommend a winner based on telemetry data."""
    from marketplace.ab_testing import ABExperimentStore, ABAnalyzer
    from marketplace.telemetry_analytics import TelemetryStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    winner = ABAnalyzer(TelemetryStore(Path(tel_path))).recommend_winner(exp)
    if winner:
        click.echo(click.style(f'Recommended winner: {winner}', fg='green'))
    else:
        click.echo('No telemetry data available to recommend a winner.')


@ab.command('conclude')
@click.argument('experiment_id')
@click.option('--winner', 'winner_label', default=None)
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
def ab_conclude(experiment_id: str, winner_label: Optional[str], store_path: str):
    """Conclude an experiment, optionally setting the winner."""
    from marketplace.ab_testing import ABExperimentStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    try:
        exp.conclude(winner_label=winner_label)
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    store.save(exp)
    click.echo(f'Concluded: {exp.experiment_id}'
               + (f'  winner={winner_label}' if winner_label else ''))


@ab.command('pause')
@click.argument('experiment_id')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
def ab_pause(experiment_id: str, store_path: str):
    """Pause an active experiment."""
    from marketplace.ab_testing import ABExperimentStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    try:
        exp.pause()
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    store.save(exp)
    click.echo(f'Paused: {exp.experiment_id}')


@ab.command('resume')
@click.argument('experiment_id')
@click.option('--store', 'store_path', default=_DEFAULT_AB_STORE, show_default=True)
def ab_resume(experiment_id: str, store_path: str):
    """Resume a paused experiment."""
    from marketplace.ab_testing import ABExperimentStore
    store = ABExperimentStore(Path(store_path))
    exp = store.get(experiment_id)
    if exp is None:
        click.echo(click.style(f'Not found: {experiment_id}', fg='yellow'))
        raise SystemExit(1)
    try:
        exp.resume()
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    store.save(exp)
    click.echo(f'Resumed: {exp.experiment_id}')


# ── telemetry ─────────────────────────────────────────────────────────────────

_DEFAULT_TELEMETRY_STORE = str(Path(__file__).resolve().parent / 'telemetry' / 'executions.jsonl')


@cli.group()
def telemetry():
    """Skill execution telemetry: record, stats, anomalies, report."""


@telemetry.command('record')
@click.option('--skill', 'skill_id', required=True, help='Skill ID')
@click.option('--node', 'node_id', required=True, help='Robot node ID')
@click.option('--station', 'station_id', default='default', show_default=True)
@click.option('--status', 'status', default='success',
              type=click.Choice(['success', 'failed', 'aborted']), show_default=True)
@click.option('--duration-ms', 'duration_ms', default=0, type=int, show_default=True)
@click.option('--failure-reason', 'failure_reason', default='')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE, show_default=True)
def telemetry_record(skill_id: str, node_id: str, station_id: str, status: str,
                     duration_ms: int, failure_reason: str, store_path: str):
    """Record one skill execution in the telemetry store."""
    from marketplace.telemetry_analytics import TelemetryStore, ExecutionRecord
    store = TelemetryStore(Path(store_path))
    rec = ExecutionRecord.make(
        skill_id=skill_id,
        node_id=node_id,
        station_id=station_id,
        status=status,
        total_duration_ms=duration_ms,
        failure_reason=failure_reason,
    )
    store.record(rec)
    click.echo(click.style(f'Recorded: {rec.execution_id}  [{status}]  {duration_ms} ms', fg='green'))


@telemetry.command('stats')
@click.argument('skill_id')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def telemetry_stats(skill_id: str, store_path: str, as_json: bool):
    """Show aggregated stats for a skill."""
    import json as _json
    from marketplace.telemetry_analytics import TelemetryStore, TelemetryAnalyzer
    store = TelemetryStore(Path(store_path))
    analyzer = TelemetryAnalyzer(store)
    stats = analyzer.skill_stats(skill_id)
    if stats is None:
        click.echo(click.style(f'No records found for skill: {skill_id}', fg='yellow'))
        raise SystemExit(1)
    if as_json:
        click.echo(_json.dumps(stats.to_dict(), indent=2))
    else:
        click.echo(stats.summary())


@telemetry.command('anomalies')
@click.option('--skill', 'skill_id', default=None, help='Filter by skill ID')
@click.option('--threshold', 'z_threshold', default=2.0, type=float, show_default=True,
              help='Z-score threshold for anomaly detection')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def telemetry_anomalies(skill_id: Optional[str], z_threshold: float,
                        store_path: str, as_json: bool):
    """Detect anomalous executions by duration z-score."""
    import json as _json
    from marketplace.telemetry_analytics import TelemetryStore, TelemetryAnalyzer
    store = TelemetryStore(Path(store_path))
    analyzer = TelemetryAnalyzer(store)
    anomalies = analyzer.anomalies(skill_id=skill_id, z_threshold=z_threshold)
    if as_json:
        click.echo(_json.dumps(
            [{'execution_id': r.execution_id, 'skill_id': r.skill_id,
              'duration_ms': r.total_duration_ms, 'z_score': z}
             for r, z in anomalies],
            indent=2,
        ))
    else:
        if not anomalies:
            click.echo('No anomalies detected.')
            return
        for rec, z in anomalies:
            click.echo(
                f'z={z:5.2f}  {rec.execution_id[:8]}  '
                f'{rec.skill_id}  {rec.total_duration_ms} ms  [{rec.status}]'
            )


@telemetry.command('report')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def telemetry_report(store_path: str, as_json: bool):
    """Print a full fleet telemetry report."""
    import json as _json
    from marketplace.telemetry_analytics import TelemetryStore, TelemetryAnalyzer
    store = TelemetryStore(Path(store_path))
    analyzer = TelemetryAnalyzer(store)
    rpt = analyzer.report()
    if as_json:
        click.echo(_json.dumps(rpt, indent=2))
    else:
        click.echo(f'Generated : {rpt["generated_at"]}')
        click.echo(f'Executions: {rpt["total_executions"]}  '
                   f'Skills: {rpt["skill_count"]}  '
                   f'Nodes: {rpt["node_count"]}')
        for s in rpt['skills']:
            click.echo(f'  {s["skill_id"]:40s}  '
                       f'{s["execution_count"]:4d} runs  '
                       f'{s["success_rate"]:.0%} ok  '
                       f'p95={s["p95_ms"]:.0f} ms')


# ── health ────────────────────────────────────────────────────────────────────

_DEFAULT_TELEMETRY_STORE_HM = str(
    Path(__file__).resolve().parent / 'telemetry' / 'executions.jsonl'
)
_DEFAULT_ALERT_DIR = str(Path(__file__).resolve().parent / 'health')


@cli.group()
def health():
    """Skill and node health monitoring: skills, nodes, fleet, alerts."""


@health.command('skills')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE_HM, show_default=True)
@click.option('--alert-dir', 'alert_dir', default=_DEFAULT_ALERT_DIR, show_default=True)
@click.option('--window', 'window_hours', default=1, type=int, show_default=True,
              help='Look-back window in hours')
@click.option('--json', 'as_json', is_flag=True)
def health_skills(store_path: str, alert_dir: str, window_hours: int, as_json: bool):
    """Show health report for all known skills."""
    import json as _json
    from marketplace.health_monitor import HealthMonitor
    from marketplace.telemetry_analytics import TelemetryStore
    store = TelemetryStore(Path(store_path))
    mon = HealthMonitor(store, alert_dir=Path(alert_dir))
    skill_ids = store.skill_ids()
    reports = [mon.check_skill(s, window_hours) for s in skill_ids]
    if as_json:
        click.echo(_json.dumps([r.to_dict() for r in reports], indent=2))
    else:
        if not reports:
            click.echo('No skills in telemetry store.')
            return
        for r in reports:
            colour = 'green' if r.status == 'healthy' else (
                'red' if r.status == 'critical' else 'yellow'
            )
            click.echo(
                click.style(f'[{r.status.upper():8s}]', fg=colour) +
                f'  {r.skill_id:40s}  {r.success_rate:.0%}  {r.execution_count} runs'
            )


@health.command('nodes')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE_HM, show_default=True)
@click.option('--alert-dir', 'alert_dir', default=_DEFAULT_ALERT_DIR, show_default=True)
@click.option('--window', 'window_hours', default=1, type=int, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def health_nodes(store_path: str, alert_dir: str, window_hours: int, as_json: bool):
    """Show health report for all known robot nodes."""
    import json as _json
    from marketplace.health_monitor import HealthMonitor
    from marketplace.telemetry_analytics import TelemetryStore
    store = TelemetryStore(Path(store_path))
    mon = HealthMonitor(store, alert_dir=Path(alert_dir))
    node_ids = store.node_ids()
    reports = [mon.check_node(n, window_hours) for n in node_ids]
    if as_json:
        click.echo(_json.dumps([r.to_dict() for r in reports], indent=2))
    else:
        if not reports:
            click.echo('No nodes in telemetry store.')
            return
        for r in reports:
            colour = 'green' if r.status == 'healthy' else (
                'red' if r.status == 'critical' else 'yellow'
            )
            click.echo(
                click.style(f'[{r.status.upper():8s}]', fg=colour) +
                f'  {r.node_id:30s}  {r.success_rate:.0%}  {r.execution_count} runs'
            )


@health.command('fleet')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE_HM, show_default=True)
@click.option('--alert-dir', 'alert_dir', default=_DEFAULT_ALERT_DIR, show_default=True)
@click.option('--window', 'window_hours', default=1, type=int, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def health_fleet(store_path: str, alert_dir: str, window_hours: int, as_json: bool):
    """Show fleet-wide health report."""
    import json as _json
    from marketplace.health_monitor import HealthMonitor
    from marketplace.telemetry_analytics import TelemetryStore
    store = TelemetryStore(Path(store_path))
    mon = HealthMonitor(store, alert_dir=Path(alert_dir))
    rpt = mon.check_fleet(window_hours)
    if as_json:
        click.echo(_json.dumps(rpt.to_dict(), indent=2))
    else:
        colour = 'green' if rpt.overall_status == 'healthy' else (
            'red' if rpt.overall_status == 'critical' else 'yellow'
        )
        click.echo(
            f'Fleet status : ' +
            click.style(rpt.overall_status.upper(), fg=colour)
        )
        click.echo(f'Generated    : {rpt.generated_at}')
        click.echo(f'Skills       : {len(rpt.skill_reports)}')
        click.echo(f'Nodes        : {len(rpt.node_reports)}')
        click.echo(f'Active alerts: {len(rpt.alerts)}')


@health.command('alerts')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE_HM, show_default=True)
@click.option('--alert-dir', 'alert_dir', default=_DEFAULT_ALERT_DIR, show_default=True)
@click.option('--all', 'show_all', is_flag=True, help='Include resolved alerts')
@click.option('--json', 'as_json', is_flag=True)
def health_alerts(store_path: str, alert_dir: str, show_all: bool, as_json: bool):
    """List health alerts."""
    import json as _json
    from marketplace.health_monitor import HealthMonitor
    from marketplace.telemetry_analytics import TelemetryStore
    store = TelemetryStore(Path(store_path))
    mon = HealthMonitor(store, alert_dir=Path(alert_dir))
    alerts = mon.all_alerts() if show_all else mon.active_alerts()
    if as_json:
        click.echo(_json.dumps([a.to_dict() for a in alerts], indent=2))
    else:
        if not alerts:
            click.echo('No active alerts.')
            return
        for a in alerts:
            colour = 'red' if a.level == 'critical' else 'yellow'
            tag = click.style(f'[{a.level.upper()}]', fg=colour)
            resolved = '  (resolved)' if a.resolved else ''
            click.echo(f'{tag}  {a.subject_type}/{a.subject_id}{resolved}')
            click.echo(f'      {a.message}')


@health.command('resolve')
@click.argument('alert_id')
@click.option('--store', 'store_path', default=_DEFAULT_TELEMETRY_STORE_HM, show_default=True)
@click.option('--alert-dir', 'alert_dir', default=_DEFAULT_ALERT_DIR, show_default=True)
def health_resolve(alert_id: str, store_path: str, alert_dir: str):
    """Resolve a health alert by ID."""
    from marketplace.health_monitor import HealthMonitor
    from marketplace.telemetry_analytics import TelemetryStore
    store = TelemetryStore(Path(store_path))
    mon = HealthMonitor(store, alert_dir=Path(alert_dir))
    if mon.resolve_alert(alert_id):
        click.echo(click.style(f'Alert {alert_id} resolved.', fg='green'))
    else:
        click.echo(click.style(
            f'Alert not found or already resolved: {alert_id}', fg='red'
        ))
        raise SystemExit(1)


# ── circuit ───────────────────────────────────────────────────────────────────

_DEFAULT_CIRCUIT_DIR = str(Path(__file__).resolve().parent / 'circuits')


@cli.group()
def circuit():
    """Skill execution circuit breaker: check, record, reset, list."""


@circuit.command('list')
@click.option('--dir', 'data_dir', default=_DEFAULT_CIRCUIT_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def circuit_list(data_dir: str, as_json: bool):
    """List all circuit breaker states."""
    import json as _json
    from marketplace.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(data_dir=Path(data_dir))
    states = cb.list_breakers()
    if as_json:
        click.echo(_json.dumps([s.to_dict() for s in states], indent=2))
    else:
        if not states:
            click.echo('No circuit breakers recorded.')
            return
        for s in states:
            colour = 'green' if s.state == 'closed' else (
                'red' if s.state == 'open' else 'yellow'
            )
            click.echo(
                click.style(f'[{s.state.upper():9s}]', fg=colour) +
                f'  {s.skill_id:40s}  node={s.node_id}  '
                f'failures={s.failure_count}  calls={s.total_calls}'
            )


@circuit.command('check')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_CIRCUIT_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def circuit_check(skill_id: str, node_id: str, data_dir: str, as_json: bool):
    """Check whether an execution is allowed for a skill."""
    import json as _json
    from marketplace.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(data_dir=Path(data_dir))
    result = cb.allow_execution(skill_id, node_id)
    if as_json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        colour = 'green' if result.allowed else 'red'
        click.echo(click.style(
            f'{"ALLOWED" if result.allowed else "REJECTED"}', fg=colour
        ) + f'  {skill_id}  state={result.state}  reason={result.reason}')
    if not result.allowed:
        raise SystemExit(1)


@circuit.command('success')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_CIRCUIT_DIR, show_default=True)
def circuit_success(skill_id: str, node_id: str, data_dir: str):
    """Record a successful execution."""
    from marketplace.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(data_dir=Path(data_dir))
    state = cb.record_success(skill_id, node_id)
    click.echo(click.style('Recorded success.', fg='green') +
               f'  {skill_id}  state={state.state}')


@circuit.command('failure')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_CIRCUIT_DIR, show_default=True)
def circuit_failure(skill_id: str, node_id: str, data_dir: str):
    """Record a failed execution."""
    from marketplace.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(data_dir=Path(data_dir))
    state = cb.record_failure(skill_id, node_id)
    colour = 'red' if state.state == 'open' else 'yellow'
    click.echo(click.style('Recorded failure.', fg=colour) +
               f'  {skill_id}  state={state.state}  '
               f'failures={state.failure_count}')


@circuit.command('reset')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_CIRCUIT_DIR, show_default=True)
def circuit_reset(skill_id: str, node_id: str, data_dir: str):
    """Manually reset a circuit breaker to closed."""
    from marketplace.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(data_dir=Path(data_dir))
    if cb.reset(skill_id, node_id):
        click.echo(click.style(f'Circuit {skill_id} reset to closed.', fg='green'))
    else:
        click.echo(click.style(
            f'No circuit breaker found for: {skill_id}', fg='red'
        ))
        raise SystemExit(1)


# ── retry ─────────────────────────────────────────────────────────────────────

_DEFAULT_RETRY_DIR = str(Path(__file__).resolve().parent / 'retry')


@cli.group()
def retry():
    """Skill execution retry policy: set, list, get, remove, advise."""


@retry.command('set')
@click.argument('skill_id')
@click.option('--max-attempts', default=3, type=int, show_default=True)
@click.option('--backoff', default='exponential',
              type=click.Choice(['fixed', 'linear', 'exponential']),
              show_default=True)
@click.option('--base-delay-ms', 'base_delay_ms', default=500, type=int,
              show_default=True)
@click.option('--max-delay-ms', 'max_delay_ms', default=30000, type=int,
              show_default=True)
@click.option('--jitter-ms', 'jitter_ms', default=100, type=int,
              show_default=True)
@click.option('--retryable', 'retryable_statuses', multiple=True,
              default=['failed', 'aborted'],
              help='Retryable status (repeatable)')
@click.option('--dir', 'data_dir', default=_DEFAULT_RETRY_DIR, show_default=True)
def retry_set(skill_id: str, max_attempts: int, backoff: str,
              base_delay_ms: int, max_delay_ms: int, jitter_ms: int,
              retryable_statuses, data_dir: str):
    """Set retry policy for a skill."""
    from marketplace.retry_policy import RetryConfig, RetryEngine
    try:
        cfg = RetryConfig(
            max_attempts=max_attempts, backoff=backoff,
            base_delay_ms=base_delay_ms, max_delay_ms=max_delay_ms,
            jitter_ms=jitter_ms, retryable_statuses=list(retryable_statuses),
        )
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    engine = RetryEngine(data_dir=Path(data_dir))
    engine.set_policy(skill_id, cfg)
    click.echo(click.style(f'Policy set for {skill_id}.', fg='green'))
    click.echo(f'  max_attempts={cfg.max_attempts}  backoff={cfg.backoff}  '
               f'base={cfg.base_delay_ms}ms  max={cfg.max_delay_ms}ms')


@retry.command('list')
@click.option('--dir', 'data_dir', default=_DEFAULT_RETRY_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def retry_list(data_dir: str, as_json: bool):
    """List all registered retry policies."""
    import json as _json
    from marketplace.retry_policy import RetryEngine
    engine = RetryEngine(data_dir=Path(data_dir))
    policies = engine.list_policies()
    if as_json:
        click.echo(_json.dumps(
            {s: c.to_dict() for s, c in policies.items()}, indent=2
        ))
    else:
        if not policies:
            click.echo('No retry policies registered.')
            return
        for skill_id, cfg in policies.items():
            click.echo(
                f'{skill_id:40s}  max={cfg.max_attempts}  '
                f'{cfg.backoff}  base={cfg.base_delay_ms}ms'
            )


@retry.command('get')
@click.argument('skill_id')
@click.option('--dir', 'data_dir', default=_DEFAULT_RETRY_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def retry_get(skill_id: str, data_dir: str, as_json: bool):
    """Get the retry policy for a skill (shows default if none set)."""
    import json as _json
    from marketplace.retry_policy import RetryEngine
    engine = RetryEngine(data_dir=Path(data_dir))
    cfg = engine.get_config(skill_id)
    explicit = engine._store.get(skill_id) is not None
    if as_json:
        click.echo(_json.dumps({'skill_id': skill_id,
                                'explicit': explicit,
                                'config': cfg.to_dict()}, indent=2))
    else:
        tag = '' if explicit else '  (default)'
        click.echo(f'{skill_id}{tag}')
        click.echo(f'  max_attempts  : {cfg.max_attempts}')
        click.echo(f'  backoff       : {cfg.backoff}')
        click.echo(f'  base_delay_ms : {cfg.base_delay_ms}')
        click.echo(f'  max_delay_ms  : {cfg.max_delay_ms}')
        click.echo(f'  jitter_ms     : {cfg.jitter_ms}')
        click.echo(f'  retryable     : {cfg.retryable_statuses}')


@retry.command('remove')
@click.argument('skill_id')
@click.option('--dir', 'data_dir', default=_DEFAULT_RETRY_DIR, show_default=True)
def retry_remove(skill_id: str, data_dir: str):
    """Remove the explicit retry policy for a skill."""
    from marketplace.retry_policy import RetryEngine
    engine = RetryEngine(data_dir=Path(data_dir))
    if engine.remove_policy(skill_id):
        click.echo(click.style(f'Policy for {skill_id} removed.', fg='green'))
    else:
        click.echo(click.style(f'No policy found for: {skill_id}', fg='red'))
        raise SystemExit(1)


@retry.command('advise')
@click.argument('skill_id')
@click.option('--attempt', 'attempt', required=True, type=int,
              help='1-based attempt number that just completed')
@click.option('--status', 'last_status', required=True,
              help='Execution status of the completed attempt')
@click.option('--dir', 'data_dir', default=_DEFAULT_RETRY_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def retry_advise(skill_id: str, attempt: int, last_status: str,
                 data_dir: str, as_json: bool):
    """Get a retry recommendation for a skill execution outcome."""
    import json as _json
    from marketplace.retry_policy import RetryEngine
    engine = RetryEngine(data_dir=Path(data_dir))
    decision = engine.should_retry(skill_id, attempt, last_status)
    if as_json:
        click.echo(_json.dumps(decision.to_dict(), indent=2))
    else:
        colour = 'green' if decision.retry else 'red'
        click.echo(click.style(
            f'{"RETRY" if decision.retry else "STOP"}', fg=colour
        ) + f'  {skill_id}  attempt={attempt}  '
            f'reason={decision.reason}  delay={decision.delay_ms}ms')


# ── bulkhead ──────────────────────────────────────────────────────────────────

_DEFAULT_BULKHEAD_DIR = str(Path(__file__).resolve().parent / 'bulkhead')


@cli.group()
def bulkhead():
    """Skill execution bulkhead: acquire, release, reset, status, config."""


@bulkhead.command('acquire')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_BULKHEAD_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def bulkhead_acquire(skill_id: str, node_id: str, data_dir: str, as_json: bool):
    """Acquire a concurrency slot for a skill."""
    import json as _json
    from marketplace.bulkhead import Bulkhead
    bh = Bulkhead(data_dir=Path(data_dir))
    result = bh.acquire(skill_id, node_id)
    if as_json:
        click.echo(_json.dumps(result.to_dict(), indent=2))
    else:
        colour = 'green' if result.acquired else 'red'
        click.echo(click.style(
            'ACQUIRED' if result.acquired else 'REJECTED', fg=colour
        ) + f'  {skill_id}  active={result.active_count}/{result.max_concurrent}'
            f'  reason={result.reason}')
    if not result.acquired:
        raise SystemExit(1)


@bulkhead.command('release')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_BULKHEAD_DIR, show_default=True)
def bulkhead_release(skill_id: str, node_id: str, data_dir: str):
    """Release a previously acquired concurrency slot."""
    from marketplace.bulkhead import Bulkhead
    bh = Bulkhead(data_dir=Path(data_dir))
    released = bh.release(skill_id, node_id)
    if released:
        click.echo(click.style(f'Released slot for {skill_id}.', fg='green'))
    else:
        click.echo(click.style(
            f'Nothing to release for: {skill_id}', fg='yellow'
        ))


@bulkhead.command('status')
@click.option('--dir', 'data_dir', default=_DEFAULT_BULKHEAD_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def bulkhead_status(data_dir: str, as_json: bool):
    """List all bulkhead states."""
    import json as _json
    from marketplace.bulkhead import Bulkhead
    bh = Bulkhead(data_dir=Path(data_dir))
    states = bh.list_states()
    if as_json:
        click.echo(_json.dumps([s.to_dict() for s in states], indent=2))
    else:
        if not states:
            click.echo('No bulkhead states recorded.')
            return
        for s in states:
            cfg = bh.get_config(s.skill_id)
            pct = s.active_count / cfg.max_concurrent if cfg.max_concurrent else 0
            colour = 'red' if pct >= 1.0 else ('yellow' if pct >= 0.75 else 'green')
            click.echo(
                click.style(f'{s.active_count:3d}/{cfg.max_concurrent:<3d}',
                            fg=colour) +
                f'  {s.skill_id:40s}  node={s.node_id}  '
                f'acq={s.total_acquired}  rel={s.total_released}'
            )


@bulkhead.command('reset')
@click.argument('skill_id')
@click.option('--node', 'node_id', default='*', show_default=True)
@click.option('--dir', 'data_dir', default=_DEFAULT_BULKHEAD_DIR, show_default=True)
def bulkhead_reset(skill_id: str, node_id: str, data_dir: str):
    """Reset active_count to 0 for a skill bulkhead."""
    from marketplace.bulkhead import Bulkhead
    bh = Bulkhead(data_dir=Path(data_dir))
    if bh.reset(skill_id, node_id):
        click.echo(click.style(f'Bulkhead for {skill_id} reset.', fg='green'))
    else:
        click.echo(click.style(f'No bulkhead state for: {skill_id}', fg='red'))
        raise SystemExit(1)


@bulkhead.command('config-set')
@click.argument('skill_id')
@click.option('--max-concurrent', 'max_concurrent', required=True, type=int)
@click.option('--dir', 'data_dir', default=_DEFAULT_BULKHEAD_DIR, show_default=True)
def bulkhead_config_set(skill_id: str, max_concurrent: int, data_dir: str):
    """Set concurrency limit for a skill."""
    from marketplace.bulkhead import Bulkhead, BulkheadConfig
    try:
        cfg = BulkheadConfig(max_concurrent=max_concurrent)
    except ValueError as exc:
        click.echo(click.style(str(exc), fg='red'))
        raise SystemExit(1)
    Bulkhead(data_dir=Path(data_dir)).set_config(skill_id, cfg)
    click.echo(click.style(
        f'Config set for {skill_id}: max_concurrent={max_concurrent}', fg='green'
    ))


@bulkhead.command('config-list')
@click.option('--dir', 'data_dir', default=_DEFAULT_BULKHEAD_DIR, show_default=True)
@click.option('--json', 'as_json', is_flag=True)
def bulkhead_config_list(data_dir: str, as_json: bool):
    """List all per-skill bulkhead configurations."""
    import json as _json
    from marketplace.bulkhead import Bulkhead
    bh = Bulkhead(data_dir=Path(data_dir))
    configs = bh.list_configs()
    if as_json:
        click.echo(_json.dumps(
            {s: c.to_dict() for s, c in configs.items()}, indent=2
        ))
    else:
        if not configs:
            click.echo('No bulkhead configs registered.')
            return
        for skill_id, cfg in configs.items():
            click.echo(f'{skill_id:40s}  max_concurrent={cfg.max_concurrent}')


if __name__ == '__main__':
    cli()
