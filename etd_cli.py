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
