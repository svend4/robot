#!/usr/bin/env python3
"""ETD CLI — command-line tool for managing ETD skill packages.

Usage:
    python etd_cli.py validate  <package-path> [--runtime-context FILE] [--json]
    python etd_cli.py publish   <package-path> [--key FILE] [--out DIR] [--skip-sign]
    python etd_cli.py verify    <package-path> [--pub-key FILE]
    python etd_cli.py install   <skill-id>     [--token TOKEN] [--robot-class CLASS]
    python etd_cli.py list      [--family FAM] [--free] [--json]
    python etd_cli.py info      <skill-id>
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

_CTX_PATH = ROOT / 'runtime_context.json'


def _load_ctx(runtime_context: str, robot_class: str, services: tuple) -> RuntimeContext:
    ctx_path = Path(runtime_context)
    if ctx_path.exists():
        ctx = load_runtime_context(ctx_path)
    else:
        ctx = default_runtime_context()
    if robot_class:
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


@cli.command()
@click.argument('package_path')
@click.option('--runtime-context', default=str(_CTX_PATH), show_default=True)
@click.option('--robot-class', default='humanoid', show_default=True)
@click.option('--service', 'services', multiple=True, metavar='SVC',
              help='Available service (repeat for each)')
@click.option('--json', 'as_json', is_flag=True, help='Output raw JSON report')
def validate(package_path: str, runtime_context: str, robot_class: str, services: tuple, as_json: bool):
    """Validate an ETD skill package directory."""
    ctx = _load_ctx(runtime_context, robot_class, services)
    report = ETDReferenceValidator(ctx).validate_package(package_path)
    _print_report(report, as_json)
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
@click.argument('skill_id')
@click.option('--token', default=None, help='Entitlement token for commercial skills')
@click.option('--robot-class', default='humanoid', show_default=True)
@click.option('--runtime-context', default=str(_CTX_PATH), show_default=True)
def install(skill_id: str, token: str | None, robot_class: str, runtime_context: str):
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
    sys.exit(0 if decision.allowed else 1)


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
