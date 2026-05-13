"""Tests for the ETD Publisher Portal (submission + review workflow)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.publisher_portal import (
    PublisherPortal,
    SubmissionRecord,
    STATUSES,
    _read_skill_meta,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_pkg(tmp_path: Path, name: str = 'etd.test.skill',
              version: str = '1.0.0', risk: str = 'medium') -> Path:
    pkg = tmp_path / name
    pkg.mkdir(exist_ok=True)
    (pkg / 'manifest.yaml').write_text(yaml.dump({
        'apiVersion': 'etd/v1', 'kind': 'SkillPackage',
        'metadata': {'name': name, 'version': version, 'riskLevel': risk},
        'compatibility': {
            'robotClass': ['humanoid'],
            'requiresServices': ['manipulation.arm_control'],
        },
    }), encoding='utf-8')
    (pkg / 'capabilities.json').write_text(
        json.dumps({'write': ['command.skill_intent'], 'read': [], 'forbidden': []}),
        encoding='utf-8',
    )
    (pkg / 'chs_profiles.json').write_text(
        json.dumps({'profiles': [
            {'name': 'default', 'payloadKg': 2.0, 'forceWindowN': [10, 100],
             'arcZoneRadius_m': 1.5}
        ]}), encoding='utf-8',
    )
    (pkg / 'skill.json').write_text(
        json.dumps({'skillId': name, 'version': version, 'family': 'test',
                    'riskLevel': risk}),
        encoding='utf-8',
    )
    return pkg


def _portal(tmp_path: Path, **kw) -> PublisherPortal:
    submissions_path = tmp_path / 'submissions.json'
    return PublisherPortal(ROOT, submissions_path=submissions_path, **kw)


# ── STATUSES constant ─────────────────────────────────────────────────────────

class TestStatuses:
    def test_all_expected_statuses_present(self):
        for s in ('submitted', 'in_review', 'approved', 'rejected', 'needs_revision'):
            assert s in STATUSES


# ── SubmissionRecord ──────────────────────────────────────────────────────────

class TestSubmissionRecord:
    def _rec(self, **kw):
        defaults = dict(
            submission_id='abc123', skill_id='etd.x', version='1.0.0',
            package_path='/tmp/pkg', publisher='test', submitted_at='2026-01-01T00:00:00Z',
            status='submitted',
        )
        defaults.update(kw)
        return SubmissionRecord(**defaults)

    def test_to_dict_has_required_keys(self):
        r = self._rec()
        d = r.to_dict()
        for k in ('submission_id', 'skill_id', 'version', 'package_path',
                  'publisher', 'submitted_at', 'status'):
            assert k in d

    def test_to_dict_is_json_serialisable(self):
        r = self._rec()
        json.dumps(r.to_dict())

    def test_from_dict_roundtrip(self):
        r = self._rec(status='approved', decision_reason='ok')
        r2 = SubmissionRecord.from_dict(r.to_dict())
        assert r2.submission_id == r.submission_id
        assert r2.status == 'approved'
        assert r2.decision_reason == 'ok'

    def test_blocking_findings_default_empty(self):
        r = self._rec()
        assert r.blocking_findings == []

    def test_decided_at_default_none(self):
        r = self._rec()
        assert r.decided_at is None


# ── _read_skill_meta ──────────────────────────────────────────────────────────

class TestReadSkillMeta:
    def test_reads_from_manifest_yaml(self, tmp_path):
        p = tmp_path / 'pkg'
        p.mkdir()
        (p / 'manifest.yaml').write_text(yaml.dump({
            'metadata': {'name': 'etd.m', 'version': '2.0.0'}
        }))
        skill_id, version = _read_skill_meta(p)
        assert skill_id == 'etd.m'
        assert version == '2.0.0'

    def test_reads_from_skill_json(self, tmp_path):
        p = tmp_path / 'pkg'
        p.mkdir()
        (p / 'skill.json').write_text(json.dumps({'skillId': 'etd.s', 'version': '3.0.0'}))
        skill_id, version = _read_skill_meta(p)
        assert skill_id == 'etd.s'
        assert version == '3.0.0'

    def test_falls_back_to_dir_name(self, tmp_path):
        p = tmp_path / 'etd.fallback'
        p.mkdir()
        skill_id, version = _read_skill_meta(p)
        assert skill_id == 'etd.fallback'
        assert version == '0.0.0'


# ── PublisherPortal.submit ────────────────────────────────────────────────────

class TestPortalSubmit:
    def test_submit_valid_package_auto_approves(self, tmp_path):
        pkg = ROOT / 'examples' / 'etd.pickplace.basic'
        if not pkg.exists():
            pytest.skip('etd.pickplace.basic not present')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, publisher='etd-lab')
        assert rec.status == 'approved'
        assert rec.decided_by == 'auto'
        assert rec.pipeline_passed is True

    def test_submit_high_risk_goes_to_review(self, tmp_path):
        pkg = _make_pkg(tmp_path, risk='high')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, publisher='test-pub')
        assert rec.status == 'in_review'
        assert rec.human_review_required is True

    def test_submit_with_forbidden_import_goes_to_review(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        (pkg / 'adapter.py').write_text('import subprocess\n')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, publisher='test-pub')
        assert rec.status == 'in_review'
        assert rec.pipeline_passed is False

    def test_submit_assigns_unique_submission_id(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path)
        r1 = portal.submit(pkg, publisher='a')
        r2 = portal.submit(pkg, publisher='b')
        assert r1.submission_id != r2.submission_id

    def test_submit_records_skill_id_and_version(self, tmp_path):
        pkg = _make_pkg(tmp_path, name='etd.test.v2', version='2.5.0')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, publisher='pub')
        assert rec.skill_id == 'etd.test.v2'
        assert rec.version == '2.5.0'

    def test_submit_records_publisher(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, publisher='hyundai-robotics')
        assert rec.publisher == 'hyundai-robotics'

    def test_submit_no_auto_approve_flag(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path, auto_approve_on_pass=False)
        rec = portal.submit(pkg, publisher='pub')
        assert rec.status == 'in_review'

    def test_submit_real_pickplace_package(self, tmp_path):
        pkg = ROOT / 'examples' / 'etd.pickplace.basic'
        if not pkg.exists():
            pytest.skip('etd.pickplace.basic not present')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, publisher='etd-lab')
        assert rec.submission_id
        assert rec.skill_id == 'etd.pickplace.basic'
        assert rec.status in ('approved', 'in_review')

    def test_submit_persists_to_disk(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        submissions_path = tmp_path / 'subs.json'
        portal1 = PublisherPortal(ROOT, submissions_path=submissions_path)
        rec = portal1.submit(pkg, publisher='pub')
        # Load fresh portal
        portal2 = PublisherPortal(ROOT, submissions_path=submissions_path)
        loaded = portal2.get_submission(rec.submission_id)
        assert loaded is not None
        assert loaded.status == rec.status


# ── PublisherPortal.get_submission / list_submissions ─────────────────────────

class TestPortalQuery:
    def test_get_submission_returns_record(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, 'pub')
        fetched = portal.get_submission(rec.submission_id)
        assert fetched is not None
        assert fetched.submission_id == rec.submission_id

    def test_get_submission_unknown_returns_none(self, tmp_path):
        portal = _portal(tmp_path)
        assert portal.get_submission('does-not-exist') is None

    def test_list_submissions_all(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path)
        portal.submit(pkg, 'pub-a')
        portal.submit(pkg, 'pub-b')
        assert portal.submission_count == 2
        assert len(portal.list_submissions()) == 2

    def test_list_submissions_filter_publisher(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path)
        portal.submit(pkg, 'etd-lab')
        portal.submit(pkg, 'acme')
        result = portal.list_submissions(publisher='etd-lab')
        assert all(r.publisher == 'etd-lab' for r in result)

    def test_list_submissions_filter_status(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        pkg_high = _make_pkg(tmp_path, name='etd.high', risk='high')
        portal = _portal(tmp_path)
        portal.submit(pkg, 'pub')          # → approved
        portal.submit(pkg_high, 'pub')     # → in_review
        approved = portal.list_submissions(status='approved')
        assert all(r.status == 'approved' for r in approved)

    def test_list_submissions_newest_first(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        portal = _portal(tmp_path)
        r1 = portal.submit(pkg, 'pub')
        r2 = portal.submit(pkg, 'pub')
        listed = portal.list_submissions()
        # Newer submission should appear first
        assert listed[0].submitted_at >= listed[-1].submitted_at


# ── PublisherPortal.approve / reject / request_revision ───────────────────────

class TestPortalDecisions:
    def _in_review_rec(self, tmp_path) -> tuple:
        pkg = _make_pkg(tmp_path, risk='high')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, 'pub')
        assert rec.status == 'in_review'
        return portal, rec

    def test_approve_moves_to_approved(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        updated = portal.approve(rec.submission_id, decided_by='reviewer@etd')
        assert updated.status == 'approved'
        assert updated.decided_by == 'reviewer@etd'
        assert updated.decided_at is not None

    def test_approve_sets_reason(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        updated = portal.approve(rec.submission_id, reason='LGTM')
        assert 'LGTM' in updated.decision_reason

    def test_reject_moves_to_rejected(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        updated = portal.reject(rec.submission_id, reason='unsafe payload')
        assert updated.status == 'rejected'
        assert 'unsafe payload' in updated.decision_reason

    def test_request_revision_moves_to_needs_revision(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        updated = portal.request_revision(rec.submission_id, reason='fix the safety constraints')
        assert updated.status == 'needs_revision'

    def test_approve_unknown_id_raises(self, tmp_path):
        portal = _portal(tmp_path)
        with pytest.raises(KeyError):
            portal.approve('nonexistent', decided_by='admin')

    def test_approve_wrong_status_raises(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        portal.approve(rec.submission_id)  # → approved
        # Cannot approve an already-approved submission
        with pytest.raises(ValueError):
            portal.approve(rec.submission_id)

    def test_reject_wrong_status_raises(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        portal.approve(rec.submission_id)  # → approved
        with pytest.raises(ValueError):
            portal.reject(rec.submission_id, reason='nope')

    def test_revision_wrong_status_raises(self, tmp_path):
        portal, rec = self._in_review_rec(tmp_path)
        portal.approve(rec.submission_id)  # → approved
        with pytest.raises(ValueError):
            portal.request_revision(rec.submission_id, reason='fix it')


# ── PublisherPortal.resubmit ──────────────────────────────────────────────────

class TestPortalResubmit:
    def test_resubmit_after_revision(self, tmp_path):
        pkg = _make_pkg(tmp_path, risk='high')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, 'pub')
        portal.request_revision(rec.submission_id, reason='needs fix')
        updated = portal.resubmit(rec.submission_id)
        assert updated.submission_id == rec.submission_id
        assert updated.status in ('approved', 'in_review')

    def test_resubmit_wrong_status_raises(self, tmp_path):
        pkg = _make_pkg(tmp_path, risk='high')
        portal = _portal(tmp_path)
        rec = portal.submit(pkg, 'pub')  # → in_review, not needs_revision
        with pytest.raises(ValueError):
            portal.resubmit(rec.submission_id)


# ── API router ────────────────────────────────────────────────────────────────

class TestPublisherAPI:
    def _client(self):
        from fastapi.testclient import TestClient
        from api.app import app
        return TestClient(app)

    def test_submit_valid_package(self):
        client = self._client()
        pkg = ROOT / 'examples' / 'etd.pickplace.basic'
        if not pkg.exists():
            pytest.skip('etd.pickplace.basic not present')
        resp = client.post('/publisher/submit', json={
            'package_path': str(pkg),
            'publisher': 'etd-lab',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'submission_id' in data
        assert data['status'] in ('approved', 'in_review')

    def test_submit_nonexistent_path_returns_404(self):
        client = self._client()
        resp = client.post('/publisher/submit', json={
            'package_path': '/nonexistent/path',
            'publisher': 'test',
        })
        assert resp.status_code == 404

    def test_list_submissions_returns_list(self):
        client = self._client()
        resp = client.get('/publisher/submissions')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_submission_unknown_returns_404(self):
        client = self._client()
        resp = client.get('/publisher/submission/nonexistent-uuid')
        assert resp.status_code == 404

    def test_stats_endpoint(self):
        client = self._client()
        resp = client.get('/publisher/stats')
        assert resp.status_code == 200
        data = resp.json()
        assert 'total' in data
        assert 'by_status' in data
        assert 'auto_approved' in data

    def test_approve_unknown_submission_returns_404(self):
        client = self._client()
        resp = client.post('/publisher/submission/bad-id/approve',
                           json={'reason': 'ok', 'decided_by': 'admin'})
        assert resp.status_code == 404


# ── CLI publisher commands ────────────────────────────────────────────────────

class TestPublisherCLI:
    def test_submit_valid_exits_zero_or_two(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / 'examples' / 'etd.pickplace.basic'
        if not pkg.exists():
            pytest.skip('etd.pickplace.basic not present')
        runner = CliRunner()
        result = runner.invoke(cli, ['publisher', 'submit', str(pkg)])
        assert result.exit_code in (0, 2)  # 0 = auto-approved, 2 = in_review

    def test_submit_json_output(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / 'examples' / 'etd.pickplace.basic'
        if not pkg.exists():
            pytest.skip('etd.pickplace.basic not present')
        runner = CliRunner()
        result = runner.invoke(cli, ['publisher', 'submit', '--json', str(pkg)])
        assert result.exit_code in (0, 2)
        data = json.loads(result.output)
        assert 'submission_id' in data
        assert 'status' in data

    def test_submit_nonexistent_exits_one(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['publisher', 'submit', '/nonexistent/path'])
        assert result.exit_code == 1

    def test_list_command(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['publisher', 'list'])
        assert result.exit_code == 0

    def test_approve_unknown_exits_one(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['publisher', 'approve', 'nonexistent-uuid'])
        assert result.exit_code == 1
