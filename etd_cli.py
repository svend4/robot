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


if __name__ == '__main__':
    cli()
