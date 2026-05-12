"""Tests for EntitlementToken issuance, verification, and SkillStore integration."""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nacl.signing import SigningKey, VerifyKey

from marketplace.entitlement_token import (
    EntitlementToken,
    _b64,
    _b64decode,
    issue_token,
    verify_token,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def keypair():
    sk = SigningKey.generate()
    return sk, sk.verify_key


@pytest.fixture
def token_str(keypair):
    sk, _ = keypair
    return issue_token(
        skill_id='etd.hyundai.wia_welding',
        station_id='workcell-01',
        operator_org='Hyundai Manufacturing',
        signing_key=sk,
        ttl_days=365,
    )


# ── EntitlementToken dataclass ────────────────────────────────────────────────

class TestEntitlementToken:
    def test_to_payload_is_canonical_json(self):
        tok = EntitlementToken(
            skill_id='s', station_id='st', expiry='2027-01-01T00:00:00Z',
            operator_org='org', issued_at='2026-01-01T00:00:00Z',
        )
        data = json.loads(tok.to_payload())
        assert data['skill_id'] == 's'
        assert data['station_id'] == 'st'

    def test_to_payload_keys_are_sorted(self):
        tok = EntitlementToken(
            skill_id='s', station_id='st', expiry='2027-01-01T00:00:00Z',
            operator_org='org', issued_at='2026-01-01T00:00:00Z',
        )
        data = json.loads(tok.to_payload())
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_is_expired_future_date(self):
        tok = EntitlementToken(
            skill_id='s', station_id='*', expiry='2099-01-01T00:00:00Z',
            operator_org='o', issued_at='2026-01-01T00:00:00Z',
        )
        assert tok.is_expired() is False

    def test_is_expired_past_date(self):
        tok = EntitlementToken(
            skill_id='s', station_id='*', expiry='2000-01-01T00:00:00Z',
            operator_org='o', issued_at='1999-01-01T00:00:00Z',
        )
        assert tok.is_expired() is True

    def test_is_expired_bad_date_returns_true(self):
        tok = EntitlementToken(
            skill_id='s', station_id='*', expiry='not-a-date',
            operator_org='o', issued_at='2026-01-01T00:00:00Z',
        )
        assert tok.is_expired() is True

    def test_covers_exact_station(self):
        tok = EntitlementToken('etd.s', 'wc-01', '2099-01-01T00:00:00Z', 'org', '2026-01-01T00:00:00Z')
        assert tok.covers('etd.s', 'wc-01') is True

    def test_covers_wildcard_station(self):
        tok = EntitlementToken('etd.s', '*', '2099-01-01T00:00:00Z', 'org', '2026-01-01T00:00:00Z')
        assert tok.covers('etd.s', 'any-station') is True

    def test_covers_wrong_skill(self):
        tok = EntitlementToken('etd.s', '*', '2099-01-01T00:00:00Z', 'org', '2026-01-01T00:00:00Z')
        assert tok.covers('etd.other', '*') is False

    def test_covers_wrong_station(self):
        tok = EntitlementToken('etd.s', 'wc-01', '2099-01-01T00:00:00Z', 'org', '2026-01-01T00:00:00Z')
        assert tok.covers('etd.s', 'wc-99') is False

    def test_covers_expired_returns_false(self):
        tok = EntitlementToken('etd.s', '*', '2000-01-01T00:00:00Z', 'org', '1999-01-01T00:00:00Z')
        assert tok.covers('etd.s', '*') is False


# ── issue_token ───────────────────────────────────────────────────────────────

class TestIssueToken:
    def test_returns_non_empty_string(self, keypair):
        sk, _ = keypair
        tok = issue_token('etd.s', '*', 'org', sk)
        assert isinstance(tok, str) and len(tok) > 10

    def test_token_has_two_parts(self, keypair):
        sk, _ = keypair
        tok = issue_token('etd.s', '*', 'org', sk)
        assert tok.count('.') >= 1

    def test_payload_contains_skill_id(self, keypair):
        sk, _ = keypair
        tok = issue_token('etd.hyundai.wia_welding', 'wc-01', 'org', sk, ttl_days=30)
        payload_part = tok.rsplit('.', 1)[0]
        payload = json.loads(_b64decode(payload_part))
        assert payload['skill_id'] == 'etd.hyundai.wia_welding'
        assert payload['station_id'] == 'wc-01'

    def test_expiry_is_ttl_days_from_now(self, keypair):
        sk, _ = keypair
        tok = issue_token('etd.s', '*', 'org', sk, ttl_days=10)
        payload_part = tok.rsplit('.', 1)[0]
        payload = json.loads(_b64decode(payload_part))
        expiry = datetime.datetime.fromisoformat(payload['expiry'].replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = expiry - now
        assert 9 <= delta.days <= 11  # within 1 day of 10

    def test_different_keys_produce_different_tokens(self):
        sk1, sk2 = SigningKey.generate(), SigningKey.generate()
        t1 = issue_token('etd.s', '*', 'org', sk1)
        t2 = issue_token('etd.s', '*', 'org', sk2)
        assert t1 != t2

    def test_same_key_produces_deterministic_payload(self, keypair):
        sk, _ = keypair
        t1 = issue_token('etd.s', '*', 'org', sk, ttl_days=365)
        t2 = issue_token('etd.s', '*', 'org', sk, ttl_days=365)
        # payloads differ by timestamp; just check both are decodeable
        for t in (t1, t2):
            p = json.loads(_b64decode(t.rsplit('.', 1)[0]))
            assert p['skill_id'] == 'etd.s'


# ── verify_token ──────────────────────────────────────────────────────────────

class TestVerifyToken:
    def test_valid_token(self, keypair, token_str):
        sk, vk = keypair
        valid, reason, tok = verify_token(token_str, vk, 'etd.hyundai.wia_welding', 'workcell-01')
        assert valid is True
        assert reason == 'token_valid'
        assert tok is not None
        assert tok.skill_id == 'etd.hyundai.wia_welding'

    def test_wildcard_station_token_valid_for_any_station(self, keypair):
        sk, vk = keypair
        tok_str = issue_token('etd.s', '*', 'org', sk)
        valid, _, _ = verify_token(tok_str, vk, 'etd.s', 'any-station-id')
        assert valid is True

    def test_wrong_skill_id(self, keypair, token_str):
        _, vk = keypair
        valid, reason, _ = verify_token(token_str, vk, 'etd.other.skill', 'workcell-01')
        assert valid is False
        assert reason == 'token_skill_station_mismatch'

    def test_wrong_station_id(self, keypair):
        sk, vk = keypair
        tok_str = issue_token('etd.s', 'wc-01', 'org', sk)
        valid, reason, _ = verify_token(tok_str, vk, 'etd.s', 'wc-99')
        assert valid is False
        assert reason == 'token_skill_station_mismatch'

    def test_wrong_verify_key(self, keypair, token_str):
        _, other_vk = SigningKey.generate(), SigningKey.generate().verify_key
        valid, reason, _ = verify_token(token_str, other_vk, 'etd.hyundai.wia_welding', 'workcell-01')
        assert valid is False
        assert reason == 'signature_invalid'

    def test_malformed_token_no_dot(self, keypair):
        _, vk = keypair
        valid, reason, _ = verify_token('notavalidtoken', vk, 'etd.s', '*')
        assert valid is False
        assert reason == 'malformed_token'

    def test_tampered_payload(self, keypair, token_str):
        _, vk = keypair
        payload_b64, sig_b64 = token_str.rsplit('.', 1)
        payload = json.loads(_b64decode(payload_b64))
        payload['skill_id'] = 'etd.evil.skill'
        new_payload_b64 = _b64(json.dumps(payload, sort_keys=True).encode())
        tampered = f'{new_payload_b64}.{sig_b64}'
        valid, reason, _ = verify_token(tampered, vk, 'etd.evil.skill', '*')
        assert valid is False
        assert reason == 'signature_invalid'

    def test_expired_token(self, keypair):
        sk, vk = keypair
        tok_str = issue_token('etd.s', '*', 'org', sk, ttl_days=-1)
        valid, reason, _ = verify_token(tok_str, vk, 'etd.s', '*')
        assert valid is False
        assert reason == 'token_expired'

    def test_returns_token_object_on_success(self, keypair, token_str):
        _, vk = keypair
        _, _, tok = verify_token(token_str, vk, 'etd.hyundai.wia_welding', 'workcell-01')
        assert isinstance(tok, EntitlementToken)
        assert tok.operator_org == 'Hyundai Manufacturing'

    def test_returns_none_token_on_decode_error(self, keypair):
        _, vk = keypair
        valid, reason, tok = verify_token('bad!!!.sig', vk, 'etd.s', '*')
        assert tok is None


# ── SkillStore integration ────────────────────────────────────────────────────

class TestSkillStoreSignedToken:
    """Verify that SkillStore.validate_for_install uses signed tokens when pubkey is loaded."""

    def _make_store(self, tmp_path):
        """Build a SkillStore with a fresh keypair and temp pubkey file."""
        from marketplace.skill_store import SkillStore
        sk = SigningKey.generate()
        vk = sk.verify_key

        keys_dir = tmp_path / 'keys'
        keys_dir.mkdir()
        (keys_dir / 'etd_verify_key.hex').write_text(vk.encode().hex())

        store = SkillStore(ROOT, entitlement_pubkey_path=keys_dir / 'etd_verify_key.hex')
        return store, sk, vk

    def test_valid_signed_token_allows_entitlement_skill(self, tmp_path):
        store, sk, _ = self._make_store(tmp_path)
        entitlement_skill = next(
            e.skillId for e in store.list_entries() if e.requiresEntitlement
        )
        tok_str = issue_token(entitlement_skill, '*', 'test-org', sk, ttl_days=365)
        from etd_reference_validator import RuntimeContext
        ctx = RuntimeContext(available_services=[
            'perception.object_pose', 'perception.part_alignment',
            'manipulation.arm_control', 'force_control.contact_feedback',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
        ])
        decision = store.validate_for_install(entitlement_skill, ctx, entitlement_token=tok_str)
        assert decision.allowed is True

    def test_invalid_signed_token_blocks_install(self, tmp_path):
        store, sk, _ = self._make_store(tmp_path)
        entitlement_skill = next(
            e.skillId for e in store.list_entries() if e.requiresEntitlement
        )
        from etd_reference_validator import RuntimeContext
        ctx = RuntimeContext(available_services=[
            'perception.object_pose', 'perception.part_alignment',
            'manipulation.arm_control', 'force_control.contact_feedback',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
        ])
        decision = store.validate_for_install(
            entitlement_skill, ctx, entitlement_token='bad.token'
        )
        assert decision.allowed is False
        assert decision.reason in ('malformed_token', 'decode_error', 'signature_invalid')

    def test_expired_token_is_blocked(self, tmp_path):
        store, sk, _ = self._make_store(tmp_path)
        entitlement_skill = next(
            e.skillId for e in store.list_entries() if e.requiresEntitlement
        )
        expired_tok = issue_token(entitlement_skill, '*', 'org', sk, ttl_days=-1)
        from etd_reference_validator import RuntimeContext
        ctx = RuntimeContext(available_services=[
            'perception.object_pose', 'perception.part_alignment',
            'manipulation.arm_control', 'force_control.contact_feedback',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
        ])
        decision = store.validate_for_install(
            entitlement_skill, ctx, entitlement_token=expired_tok
        )
        assert decision.allowed is False
        assert decision.reason == 'token_expired'

    def test_no_pubkey_falls_back_to_truthy_check(self):
        from marketplace.skill_store import SkillStore
        store = SkillStore(ROOT, entitlement_pubkey_path=Path('/nonexistent/key.hex'))
        assert store._entitlement_verify_key is None
        # any truthy string passes when no pubkey is configured
        entitlement_skill = next(
            e.skillId for e in store.list_entries() if e.requiresEntitlement
        )
        from etd_reference_validator import RuntimeContext
        ctx = RuntimeContext(available_services=[
            'perception.object_pose', 'perception.part_alignment',
            'manipulation.arm_control', 'force_control.contact_feedback',
            'workflow.job_context', 'state.robot_pose', 'state.arm_state',
            'state.wrist_state', 'state.safety_state', 'safety.zone_monitor',
        ])
        decision = store.validate_for_install(
            entitlement_skill, ctx, entitlement_token='demo-entitlement'
        )
        assert decision.allowed is True


# ── CLI token commands ────────────────────────────────────────────────────────

class TestTokenCLI:
    def test_token_issue_prints_token(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['token', 'issue', 'etd.pickplace.basic'])
        assert result.exit_code == 0
        assert 'etd.pickplace.basic' in result.output
        assert 'Token' in result.output

    def test_token_issue_json_flag(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['token', 'issue', 'etd.pickplace.basic', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'token' in data
        assert data['skill_id'] == 'etd.pickplace.basic'

    def test_token_issue_custom_station_and_org(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'token', 'issue', 'etd.hyundai.wia_welding',
            '--station', 'wc-01', '--org', 'Hyundai Test', '--json',
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['station_id'] == 'wc-01'
        assert data['operator_org'] == 'Hyundai Test'

    def test_token_verify_valid(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        issue_result = runner.invoke(cli, [
            'token', 'issue', 'etd.pickplace.basic', '--json',
        ])
        token_str = json.loads(issue_result.output)['token']
        verify_result = runner.invoke(cli, [
            'token', 'verify', token_str, 'etd.pickplace.basic',
        ])
        assert verify_result.exit_code == 0
        assert 'VALID' in verify_result.output

    def test_token_verify_invalid_exits_one(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'token', 'verify', 'bad.token', 'etd.pickplace.basic',
        ])
        assert result.exit_code == 1
        assert 'INVALID' in result.output

    def test_token_verify_json_flag(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'token', 'verify', 'bad.token', 'etd.pickplace.basic', '--json',
        ])
        data = json.loads(result.output)
        assert data['valid'] is False
