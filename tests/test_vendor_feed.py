"""Tests for the ETD multi-vendor index (vendor_feed module)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.vendor_feed import (
    FeedRecord,
    VendorFeed,
    VendorFeedManager,
    create_feed_payload,
    verify_feed_signature,
)
from marketplace.skill_store import StoreEntry


# ── Helpers ───────────────────────────────────────────────────────────────────

def _keypair():
    from nacl.signing import SigningKey
    sk = SigningKey.generate()
    return sk, sk.verify_key.encode().hex()


def _entry(skill_id: str, version: str = '1.0.0', publisher: str = 'test') -> dict:
    return {
        'skillId': skill_id,
        'version': version,
        'family': 'test',
        'packagePath': f'examples/{skill_id}',
        'publisher': publisher,
        'riskLevel': 'low',
        'certificationState': 'reference_validated',
        'targetUse': 'testing',
    }


def _feed(sk, feed_id: str = 'test-feed', entries=None) -> dict:
    if entries is None:
        entries = [_entry('etd.test.skill')]
    _, pubkey_hex = sk, sk.verify_key.encode().hex()
    return create_feed_payload(feed_id, 'Test Feed', entries, sk)


# ── VendorFeed dataclass ──────────────────────────────────────────────────────

class TestVendorFeed:
    def test_fields(self):
        vf = VendorFeed(feed_id='f1', name='Feed 1', public_key_hex='aabb')
        assert vf.feed_id == 'f1'
        assert vf.name == 'Feed 1'
        assert vf.public_key_hex == 'aabb'


# ── FeedRecord dataclass ──────────────────────────────────────────────────────

class TestFeedRecord:
    def test_entry_count(self):
        entry = StoreEntry.from_dict(_entry('etd.a', '1.0.0'))
        r = FeedRecord(feed_id='f', feed_name='F', feed_version='1.0.0',
                       entries=[entry], verified=True)
        assert r.entry_count == 1

    def test_verified_true(self):
        r = FeedRecord(feed_id='f', feed_name='F', feed_version='1.0.0',
                       entries=[], verified=True)
        assert r.verified is True

    def test_error_default_empty(self):
        r = FeedRecord(feed_id='f', feed_name='F', feed_version='1.0.0',
                       entries=[], verified=True)
        assert r.error == ''


# ── create_feed_payload ───────────────────────────────────────────────────────

class TestCreateFeedPayload:
    def test_has_required_keys(self):
        sk, _ = _keypair()
        p = create_feed_payload('test', 'Test', [_entry('etd.x')], sk)
        for k in ('feedId', 'name', 'version', 'entries', 'signature'):
            assert k in p

    def test_feed_id_matches(self):
        sk, _ = _keypair()
        p = create_feed_payload('my-feed', 'My Feed', [], sk)
        assert p['feedId'] == 'my-feed'

    def test_entries_preserved(self):
        sk, _ = _keypair()
        entries = [_entry('etd.a'), _entry('etd.b')]
        p = create_feed_payload('f', 'F', entries, sk)
        assert len(p['entries']) == 2

    def test_signature_is_string(self):
        sk, _ = _keypair()
        p = create_feed_payload('f', 'F', [], sk)
        assert isinstance(p['signature'], str)
        assert len(p['signature']) > 10

    def test_custom_feed_version(self):
        sk, _ = _keypair()
        p = create_feed_payload('f', 'F', [], sk, feed_version='2.0.0')
        assert p['version'] == '2.0.0'

    def test_roundtrip_verify(self):
        sk, pubkey_hex = _keypair()
        p = create_feed_payload('f', 'F', [_entry('etd.x')], sk)
        ok, reason = verify_feed_signature(p, pubkey_hex)
        assert ok, reason


# ── verify_feed_signature ─────────────────────────────────────────────────────

class TestVerifyFeedSignature:
    def test_valid_signature(self):
        sk, pubkey_hex = _keypair()
        p = _feed(sk)
        ok, reason = verify_feed_signature(p, pubkey_hex)
        assert ok is True
        assert reason == 'signature_valid'

    def test_wrong_key_fails(self):
        sk, _ = _keypair()
        _, other_pubkey = _keypair()
        p = _feed(sk)
        ok, reason = verify_feed_signature(p, other_pubkey)
        assert ok is False
        assert reason == 'signature_invalid'

    def test_missing_signature_fails(self):
        sk, pubkey_hex = _keypair()
        p = _feed(sk)
        del p['signature']
        ok, reason = verify_feed_signature(p, pubkey_hex)
        assert ok is False
        assert reason == 'missing_signature'

    def test_empty_signature_fails(self):
        sk, pubkey_hex = _keypair()
        p = _feed(sk)
        p['signature'] = ''
        ok, reason = verify_feed_signature(p, pubkey_hex)
        assert ok is False
        assert reason == 'missing_signature'

    def test_tampered_entries_fail(self):
        sk, pubkey_hex = _keypair()
        p = _feed(sk, entries=[_entry('etd.a')])
        p['entries'].append(_entry('etd.injected'))  # tamper
        ok, reason = verify_feed_signature(p, pubkey_hex)
        assert ok is False
        assert reason == 'signature_invalid'

    def test_tampered_entry_field_fails(self):
        sk, pubkey_hex = _keypair()
        p = _feed(sk, entries=[_entry('etd.a', version='1.0.0')])
        p['entries'][0]['version'] = '9.9.9'  # tamper version
        ok, reason = verify_feed_signature(p, pubkey_hex)
        assert ok is False

    def test_invalid_pubkey_hex_errors(self):
        sk, _ = _keypair()
        p = _feed(sk)
        ok, reason = verify_feed_signature(p, 'not-valid-hex')
        assert ok is False
        assert 'error' in reason.lower() or 'key_error' in reason


# ── VendorFeedManager — registration ─────────────────────────────────────────

class TestVendorFeedManagerRegistration:
    def test_register_feed(self):
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Feed 1', 'aabbcc'))
        assert 'f1' in mgr._feeds

    def test_unregister_feed(self):
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Feed 1', 'aabbcc'))
        mgr.unregister_feed('f1')
        assert 'f1' not in mgr._feeds

    def test_unregister_removes_record(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Feed 1', pubkey_hex))
        mgr.load_feed('f1', _feed(sk, 'f1'))
        mgr.unregister_feed('f1')
        assert 'f1' not in mgr._records

    def test_load_unregistered_feed_raises(self):
        mgr = VendorFeedManager()
        with pytest.raises(KeyError, match='not registered'):
            mgr.load_feed('unknown', {})

    def test_load_feed_from_file_unregistered_raises(self, tmp_path):
        sk, pubkey_hex = _keypair()
        payload = _feed(sk, 'test-feed')
        f = tmp_path / 'test-feed.feed.json'
        f.write_text(json.dumps(payload), encoding='utf-8')
        mgr = VendorFeedManager()
        with pytest.raises(KeyError):
            mgr.load_feed_from_file(f)


# ── VendorFeedManager — loading ───────────────────────────────────────────────

class TestVendorFeedManagerLoading:
    def test_load_verified_feed(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Feed 1', pubkey_hex))
        record = mgr.load_feed('f1', _feed(sk, 'f1'))
        assert record.verified is True
        assert record.error == ''

    def test_load_invalid_signature_marks_unverified(self):
        sk, _ = _keypair()
        _, other_pubkey = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Feed 1', other_pubkey))
        record = mgr.load_feed('f1', _feed(sk, 'f1'))
        assert record.verified is False
        assert record.error == 'signature_invalid'

    def test_entries_parsed(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Feed 1', pubkey_hex))
        entries = [_entry('etd.a'), _entry('etd.b')]
        record = mgr.load_feed('f1', create_feed_payload('f1', 'F', entries, sk))
        assert len(record.entries) == 2
        assert all(isinstance(e, StoreEntry) for e in record.entries)

    def test_load_feed_from_file(self, tmp_path):
        sk, pubkey_hex = _keypair()
        payload = _feed(sk, 'file-feed', entries=[_entry('etd.file.skill')])
        f = tmp_path / 'file-feed.feed.json'
        f.write_text(json.dumps(payload), encoding='utf-8')
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('file-feed', 'File Feed', pubkey_hex))
        record = mgr.load_feed_from_file(f)
        assert record.verified
        assert record.entry_count == 1

    def test_feed_name_from_payload(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'Registered Name', pubkey_hex))
        payload = create_feed_payload('f1', 'Payload Name', [], sk)
        record = mgr.load_feed('f1', payload)
        assert record.feed_name == 'Payload Name'

    def test_feed_version_from_payload(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        payload = create_feed_payload('f1', 'F', [], sk, feed_version='3.0.0')
        record = mgr.load_feed('f1', payload)
        assert record.feed_version == '3.0.0'


# ── VendorFeedManager — aggregation ──────────────────────────────────────────

class TestVendorFeedManagerAggregation:
    def test_aggregate_empty_returns_empty(self):
        mgr = VendorFeedManager()
        assert mgr.aggregate() == []

    def test_aggregate_single_feed(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        mgr.load_feed('f1', create_feed_payload('f1', 'F', [_entry('etd.x', '1.0.0')], sk))
        result = mgr.aggregate()
        assert len(result) == 1
        assert result[0].skillId == 'etd.x'

    def test_aggregate_two_feeds(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        for fid, sid in [('f1', 'etd.a'), ('f2', 'etd.b')]:
            mgr.register_feed(VendorFeed(fid, fid, pubkey_hex))
            mgr.load_feed(fid, create_feed_payload(fid, fid, [_entry(sid)], sk))
        skills = {e.skillId for e in mgr.aggregate()}
        assert skills == {'etd.a', 'etd.b'}

    def test_deduplication_same_skill_version(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        for fid in ('f1', 'f2'):
            mgr.register_feed(VendorFeed(fid, fid, pubkey_hex))
            mgr.load_feed(fid, create_feed_payload(fid, fid, [_entry('etd.dup', '1.0.0')], sk))
        result = mgr.aggregate()
        assert len(result) == 1

    def test_same_skill_different_versions_both_present(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        entries = [_entry('etd.multi', '1.0.0'), _entry('etd.multi', '2.0.0')]
        mgr.load_feed('f1', create_feed_payload('f1', 'F', entries, sk))
        result = mgr.aggregate()
        versions = {e.version for e in result if e.skillId == 'etd.multi'}
        assert versions == {'1.0.0', '2.0.0'}

    def test_verified_feed_wins_dedup_over_unverified(self):
        sk_verified, pubkey_verified = _keypair()
        sk_other, _ = _keypair()  # different key
        mgr = VendorFeedManager()
        # f1: verified
        mgr.register_feed(VendorFeed('f1', 'Verified', pubkey_verified))
        mgr.load_feed('f1', create_feed_payload('f1', 'Verified',
                                                [_entry('etd.dup', '1.0.0', publisher='v-publisher')],
                                                sk_verified))
        # f2: same pubkey but signed with different key → unverified
        mgr.register_feed(VendorFeed('f2', 'Unverified', pubkey_verified))
        p2 = create_feed_payload('f2', 'Unverified',
                                  [_entry('etd.dup', '1.0.0', publisher='u-publisher')],
                                  sk_other)  # wrong key → sig invalid
        mgr.load_feed('f2', p2)
        result = [e for e in mgr.aggregate() if e.skillId == 'etd.dup']
        assert len(result) == 1
        # verified feed's entry should win
        assert result[0].publisher == 'v-publisher'

    def test_feed_count(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        for fid in ('f1', 'f2', 'f3'):
            mgr.register_feed(VendorFeed(fid, fid, pubkey_hex))
            mgr.load_feed(fid, create_feed_payload(fid, fid, [], sk))
        assert mgr.feed_count == 3

    def test_total_entries(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        entries = [_entry('etd.a'), _entry('etd.b'), _entry('etd.c')]
        mgr.load_feed('f1', create_feed_payload('f1', 'F', entries, sk))
        assert mgr.total_entries == 3


# ── VendorFeedManager — queries ───────────────────────────────────────────────

class TestVendorFeedManagerQueries:
    def _load_multi_version_feed(self, mgr, sk, pubkey_hex):
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        entries = [
            {**_entry('etd.query.skill', '0.5.0'), 'runtimeConstraint': '>=0.1.0'},
            {**_entry('etd.query.skill', '1.0.0'), 'runtimeConstraint': '>=0.5.0'},
            {**_entry('etd.query.skill', '2.0.0'), 'runtimeConstraint': '>=1.0.0'},
        ]
        mgr.load_feed('f1', create_feed_payload('f1', 'F', entries, sk))

    def test_get_versions_sorted_descending(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        self._load_multi_version_feed(mgr, sk, pubkey_hex)
        versions = [e.version for e in mgr.get_versions('etd.query.skill')]
        assert versions == ['2.0.0', '1.0.0', '0.5.0']

    def test_get_versions_unknown_skill(self):
        mgr = VendorFeedManager()
        assert mgr.get_versions('etd.nonexistent') == []

    def test_find_skill_best_version(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        self._load_multi_version_feed(mgr, sk, pubkey_hex)
        entry = mgr.find_skill('etd.query.skill', runtime_version='0.7.0')
        assert entry is not None
        assert entry.version == '1.0.0'

    def test_find_skill_unknown_returns_none(self):
        mgr = VendorFeedManager()
        assert mgr.find_skill('etd.no.such') is None

    def test_list_feeds_has_expected_keys(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F1', pubkey_hex))
        mgr.load_feed('f1', create_feed_payload('f1', 'F1', [_entry('etd.x')], sk))
        feeds = mgr.list_feeds()
        assert len(feeds) == 1
        for k in ('feed_id', 'name', 'version', 'entry_count', 'verified', 'error'):
            assert k in feeds[0]

    def test_list_skills_returns_all(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        entries = [_entry('etd.a'), _entry('etd.b')]
        mgr.load_feed('f1', create_feed_payload('f1', 'F', entries, sk))
        skills = mgr.list_skills()
        assert len(skills) == 2
        ids = {s['skillId'] for s in skills}
        assert ids == {'etd.a', 'etd.b'}

    def test_list_skills_has_expected_keys(self):
        sk, pubkey_hex = _keypair()
        mgr = VendorFeedManager()
        mgr.register_feed(VendorFeed('f1', 'F', pubkey_hex))
        mgr.load_feed('f1', create_feed_payload('f1', 'F', [_entry('etd.x')], sk))
        skill = mgr.list_skills()[0]
        for k in ('skillId', 'version', 'family', 'publisher', 'licenseModel', 'runtimeConstraint'):
            assert k in skill


# ── CLI feed commands ─────────────────────────────────────────────────────────

class TestFeedCLI:
    def test_feed_create(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        # generate a temp keypair
        sk = SigningKey.generate()
        key_path = tmp_path / 'signing.hex'
        key_path.write_text(sk.encode().hex())
        out = tmp_path / 'test.feed.json'
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'create',
            '--id', 'test-feed',
            '--name', 'Test Feed',
            '--key', str(key_path),
            '--out', str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()
        payload = json.loads(out.read_text())
        assert payload['feedId'] == 'test-feed'
        assert 'signature' in payload

    def test_feed_verify_valid(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pubkey_path = tmp_path / 'verify.hex'
        pubkey_path.write_text(sk.verify_key.encode().hex())
        payload = create_feed_payload('vf', 'VF', [_entry('etd.v')], sk)
        feed_path = tmp_path / 'vf.feed.json'
        feed_path.write_text(json.dumps(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'verify', str(feed_path), '--pubkey', str(pubkey_path)
        ])
        assert result.exit_code == 0
        assert 'OK' in result.output

    def test_feed_verify_invalid_signature(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        other = SigningKey.generate()
        pubkey_path = tmp_path / 'verify.hex'
        pubkey_path.write_text(other.verify_key.encode().hex())
        payload = create_feed_payload('vf', 'VF', [], sk)  # signed with sk, not other
        feed_path = tmp_path / 'vf.feed.json'
        feed_path.write_text(json.dumps(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'verify', str(feed_path), '--pubkey', str(pubkey_path)
        ])
        assert result.exit_code == 1
        assert 'FAIL' in result.output

    def test_feed_verify_json_output(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pubkey_path = tmp_path / 'verify.hex'
        pubkey_path.write_text(sk.verify_key.encode().hex())
        payload = create_feed_payload('jf', 'JF', [], sk)
        feed_path = tmp_path / 'jf.feed.json'
        feed_path.write_text(json.dumps(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'verify', '--json', str(feed_path), '--pubkey', str(pubkey_path)
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['verified'] is True

    def test_feed_verify_missing_file_exits_one(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['feed', 'verify', '/nonexistent/feed.json'])
        assert result.exit_code == 1

    def test_feed_import_valid_feed(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pubkey_path = tmp_path / 'verify.hex'
        pubkey_path.write_text(sk.verify_key.encode().hex())
        entries = [_entry('etd.import.skill', '1.0.0')]
        payload = create_feed_payload('if', 'Import Feed', entries, sk)
        feed_path = tmp_path / 'import.feed.json'
        feed_path.write_text(json.dumps(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'import', str(feed_path), '--pubkey', str(pubkey_path)
        ])
        assert result.exit_code == 0
        assert 'etd.import.skill' in result.output

    def test_feed_import_json_output(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pubkey_path = tmp_path / 'verify.hex'
        pubkey_path.write_text(sk.verify_key.encode().hex())
        payload = create_feed_payload('jif', 'JIF', [_entry('etd.j')], sk)
        feed_path = tmp_path / 'jif.feed.json'
        feed_path.write_text(json.dumps(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'import', '--json', str(feed_path), '--pubkey', str(pubkey_path)
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['verified'] is True
        assert data['entry_count'] == 1

    def test_feed_import_invalid_signature_exits_one(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        other = SigningKey.generate()
        pubkey_path = tmp_path / 'verify.hex'
        pubkey_path.write_text(other.verify_key.encode().hex())
        payload = create_feed_payload('bad', 'Bad', [], sk)
        feed_path = tmp_path / 'bad.feed.json'
        feed_path.write_text(json.dumps(payload))
        runner = CliRunner()
        result = runner.invoke(cli, [
            'feed', 'import', str(feed_path), '--pubkey', str(pubkey_path)
        ])
        assert result.exit_code == 1
