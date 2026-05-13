"""Tests for marketplace.onrobot_store — on-robot embedded skill store."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from marketplace.onrobot_store import (
    CachedEntitlement,
    CachedManifest,
    EntitlementCache,
    MeshSync,
    MeshSyncRecord,
    OfflineInstallResult,
    OnRobotStore,
    SkillManifestCache,
    _utcnow,
)


def _future_expiry(days: int = 365) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def _past_expiry(days: int = 1) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# ── CachedEntitlement ─────────────────────────────────────────────────────────

class TestCachedEntitlement:
    def _make(self, expiry=None, station='workcell-01') -> CachedEntitlement:
        return CachedEntitlement(
            skill_id='etd.pickplace.basic',
            station_id=station,
            operator_org='ACME',
            expiry=expiry or _future_expiry(),
            token_str='tok.sig',
        )

    def test_not_expired_future(self):
        e = self._make()
        assert e.is_expired is False

    def test_expired_past(self):
        e = self._make(expiry=_past_expiry())
        assert e.is_expired is True

    def test_covers_matching(self):
        e = self._make()
        assert e.covers('etd.pickplace.basic', 'workcell-01') is True

    def test_covers_wrong_skill(self):
        e = self._make()
        assert e.covers('etd.other', 'workcell-01') is False

    def test_covers_wrong_station(self):
        e = self._make()
        assert e.covers('etd.pickplace.basic', 'workcell-99') is False

    def test_covers_wildcard_station(self):
        e = self._make(station='*')
        assert e.covers('etd.pickplace.basic', 'any-station') is True

    def test_covers_expired_returns_false(self):
        e = self._make(expiry=_past_expiry())
        assert e.covers('etd.pickplace.basic', 'workcell-01') is False

    def test_to_dict_roundtrip(self):
        e = self._make()
        e2 = CachedEntitlement.from_dict(e.to_dict())
        assert e2.skill_id == e.skill_id
        assert e2.station_id == e.station_id
        assert e2.expiry == e.expiry
        assert e2.token_str == e.token_str

    def test_from_dict_defaults(self):
        e = CachedEntitlement.from_dict({
            'skill_id': 'etd.x', 'station_id': '*',
            'expiry': _future_expiry(), 'token_str': 'tok',
        })
        assert e.operator_org == ''
        assert e.verified_by_node == ''


# ── EntitlementCache ──────────────────────────────────────────────────────────

class TestEntitlementCache:
    def _cache(self, tmp_path) -> EntitlementCache:
        return EntitlementCache(tmp_path / 'ent.json', node_id='robot-01')

    def test_empty_initially(self, tmp_path):
        c = self._cache(tmp_path)
        assert c.entry_count == 0

    def test_add_and_get(self, tmp_path):
        c = self._cache(tmp_path)
        ok, reason = c.add(
            token_str='tok.sig',
            skill_id='etd.foo',
            station_id='ws-01',
            operator_org='ACME',
            expiry=_future_expiry(),
        )
        assert ok is True
        assert reason == 'cached'
        ent = c.get('etd.foo', 'ws-01')
        assert ent is not None
        assert ent.skill_id == 'etd.foo'

    def test_get_returns_none_when_absent(self, tmp_path):
        c = self._cache(tmp_path)
        assert c.get('etd.missing', 'ws-01') is None

    def test_add_expired_token_rejected(self, tmp_path):
        c = self._cache(tmp_path)
        ok, reason = c.add(
            token_str='tok.sig',
            skill_id='etd.foo',
            station_id='*',
            operator_org='ACME',
            expiry=_past_expiry(),
        )
        assert ok is False
        assert 'expired' in reason

    def test_add_replaces_existing(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok1', 'etd.foo', 'ws-01', 'ACME', _future_expiry(100))
        c.add('tok2', 'etd.foo', 'ws-01', 'ACME', _future_expiry(200))
        assert c.entry_count == 1
        assert c.get('etd.foo', 'ws-01').token_str == 'tok2'

    def test_evict_expired(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok1', 'etd.foo', 'ws-01', 'ACME', _future_expiry())
        # inject an already-expired entry directly (bypassing add's guard)
        c._entries.append(CachedEntitlement(
            skill_id='etd.bar', station_id='ws-01',
            operator_org='ACME', expiry=_past_expiry(), token_str='tok2',
        ))
        removed = c.evict_expired()
        assert removed == 1
        assert c.entry_count == 1

    def test_evict_no_expired(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok1', 'etd.foo', 'ws-01', 'ACME', _future_expiry())
        assert c.evict_expired() == 0

    def test_list_skills(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok1', 'etd.foo', 'ws-01', 'ACME', _future_expiry())
        c.add('tok2', 'etd.bar', 'ws-01', 'ACME', _future_expiry())
        skills = c.list_skills()
        assert 'etd.foo' in skills
        assert 'etd.bar' in skills

    def test_list_skills_excludes_expired(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok1', 'etd.foo', 'ws-01', 'ACME', _future_expiry())
        # manually insert expired entry
        c._entries.append(CachedEntitlement(
            skill_id='etd.expired', station_id='*',
            operator_org='', expiry=_past_expiry(), token_str='x',
        ))
        skills = c.list_skills()
        assert 'etd.expired' not in skills

    def test_valid_count(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok1', 'etd.foo', 'ws-01', 'ACME', _future_expiry())
        c._entries.append(CachedEntitlement(
            skill_id='etd.exp', station_id='*',
            operator_org='', expiry=_past_expiry(), token_str='x',
        ))
        assert c.valid_count == 1

    def test_persists_across_instances(self, tmp_path):
        c1 = EntitlementCache(tmp_path / 'ent.json', node_id='r01')
        c1.add('tok', 'etd.foo', '*', 'ACME', _future_expiry())
        c2 = EntitlementCache(tmp_path / 'ent.json', node_id='r01')
        assert c2.get('etd.foo', 'any') is not None

    def test_node_id_recorded(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok', 'etd.foo', '*', 'ACME', _future_expiry())
        assert c.get('etd.foo', '*').verified_by_node == 'robot-01'

    def test_wildcard_station_get(self, tmp_path):
        c = self._cache(tmp_path)
        c.add('tok', 'etd.foo', '*', 'ACME', _future_expiry())
        assert c.get('etd.foo', 'any-station-at-all') is not None


# ── CachedManifest ────────────────────────────────────────────────────────────

class TestCachedManifest:
    def _make(self) -> CachedManifest:
        return CachedManifest(
            skill_id='etd.foo', version='1.2.3',
            family='pickplace', primitive_order=['approach', 'grasp', 'place'],
        )

    def test_to_dict_roundtrip(self):
        m = self._make()
        m2 = CachedManifest.from_dict(m.to_dict())
        assert m2.skill_id == m.skill_id
        assert m2.version == m.version
        assert m2.family == m.family
        assert m2.primitive_order == m.primitive_order

    def test_from_dict_defaults(self):
        m = CachedManifest.from_dict({'skill_id': 'etd.x', 'version': '0.1'})
        assert m.family == ''
        assert m.primitive_order == []
        assert m.source_node == ''


# ── SkillManifestCache ────────────────────────────────────────────────────────

class TestSkillManifestCache:
    def _cache(self, tmp_path) -> SkillManifestCache:
        return SkillManifestCache(tmp_path / 'manifests.json', node_id='r01')

    def test_empty_initially(self, tmp_path):
        c = self._cache(tmp_path)
        assert c.manifest_count == 0

    def test_put_and_get(self, tmp_path):
        c = self._cache(tmp_path)
        m = CachedManifest(skill_id='etd.foo', version='1.0', family='pickplace',
                           primitive_order=['a', 'b'])
        c.put(m)
        retrieved = c.get('etd.foo')
        assert retrieved is not None
        assert retrieved.version == '1.0'

    def test_put_replaces(self, tmp_path):
        c = self._cache(tmp_path)
        c.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=[]))
        c.put(CachedManifest(skill_id='etd.foo', version='2.0', family='f', primitive_order=[]))
        assert c.manifest_count == 1
        assert c.get('etd.foo').version == '2.0'

    def test_get_unknown_returns_none(self, tmp_path):
        c = self._cache(tmp_path)
        assert c.get('etd.missing') is None

    def test_remove_existing(self, tmp_path):
        c = self._cache(tmp_path)
        c.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=[]))
        assert c.remove('etd.foo') is True
        assert c.get('etd.foo') is None

    def test_remove_nonexistent_returns_false(self, tmp_path):
        c = self._cache(tmp_path)
        assert c.remove('etd.ghost') is False

    def test_list_skills(self, tmp_path):
        c = self._cache(tmp_path)
        c.put(CachedManifest(skill_id='etd.a', version='1.0', family='f', primitive_order=[]))
        c.put(CachedManifest(skill_id='etd.b', version='1.0', family='f', primitive_order=[]))
        assert set(c.list_skills()) == {'etd.a', 'etd.b'}

    def test_persists_across_instances(self, tmp_path):
        c1 = SkillManifestCache(tmp_path / 'm.json')
        c1.put(CachedManifest(skill_id='etd.x', version='0.1', family='f', primitive_order=[]))
        c2 = SkillManifestCache(tmp_path / 'm.json')
        assert c2.get('etd.x') is not None

    def test_source_node_set_on_put(self, tmp_path):
        c = SkillManifestCache(tmp_path / 'm.json', node_id='r99')
        c.put(CachedManifest(skill_id='etd.x', version='1.0', family='f', primitive_order=[]))
        assert c.get('etd.x').source_node == 'r99'


# ── MeshSyncRecord ────────────────────────────────────────────────────────────

class TestMeshSyncRecord:
    def test_to_dict_roundtrip(self):
        r = MeshSyncRecord(peer_node_id='peer-02', last_sync_at='2026-01-01T00:00:00+00:00',
                           synced_skill_ids=['etd.foo'], sync_count=3)
        r2 = MeshSyncRecord.from_dict(r.to_dict())
        assert r2.peer_node_id == r.peer_node_id
        assert r2.sync_count == r.sync_count
        assert r2.synced_skill_ids == r.synced_skill_ids

    def test_from_dict_defaults(self):
        r = MeshSyncRecord.from_dict({'peer_node_id': 'p1'})
        assert r.last_sync_at is None
        assert r.synced_skill_ids == []
        assert r.sync_count == 0


# ── MeshSync ──────────────────────────────────────────────────────────────────

class TestMeshSync:
    def _setup(self, tmp_path):
        mc = SkillManifestCache(tmp_path / 'manifests.json', node_id='r01')
        ms = MeshSync(node_id='r01', manifest_cache=mc)
        return mc, ms

    def test_no_peers_initially(self, tmp_path):
        _, ms = self._setup(tmp_path)
        assert ms.peer_count == 0

    def test_register_peer(self, tmp_path):
        _, ms = self._setup(tmp_path)
        ms.register_peer('r02')
        assert ms.peer_count == 1

    def test_announce_known_skill(self, tmp_path):
        mc, ms = self._setup(tmp_path)
        mc.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=[]))
        ms.register_peer('r02')
        ms.announce('etd.foo')
        assert ms.pending_announcement_count == 1

    def test_announce_unknown_skill_noop(self, tmp_path):
        _, ms = self._setup(tmp_path)
        ms.register_peer('r02')
        ms.announce('etd.unknown')
        assert ms.pending_announcement_count == 0

    def test_receive_from_peer_imports_manifest(self, tmp_path):
        mc, ms = self._setup(tmp_path)
        mc.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=['a']))
        ms.register_peer('r02')
        ms.announce('etd.foo')

        # r02 side
        mc2 = SkillManifestCache(tmp_path / 'm2.json', node_id='r02')
        ms2 = MeshSync(node_id='r02', manifest_cache=mc2)
        # simulate: r02 receives r01's announcement via shared ms object
        imported = ms.receive_from_peer('r02')
        assert 'etd.foo' in imported

    def test_receive_updates_sync_record(self, tmp_path):
        mc, ms = self._setup(tmp_path)
        mc.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=[]))
        ms.register_peer('r02')
        ms.announce('etd.foo')
        ms.receive_from_peer('r02')
        status = ms.sync_status()
        assert len(status) == 1
        assert status[0]['sync_count'] == 1
        assert 'etd.foo' in status[0]['synced_skill_ids']
        assert status[0]['last_sync_at'] is not None

    def test_receive_auto_registers_peer(self, tmp_path):
        mc, ms = self._setup(tmp_path)
        mc.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=[]))
        ms.announce('etd.foo')  # no peers registered yet
        imported = ms.receive_from_peer('r99')
        assert ms.peer_count == 1

    def test_receive_clears_pending(self, tmp_path):
        mc, ms = self._setup(tmp_path)
        mc.put(CachedManifest(skill_id='etd.foo', version='1.0', family='f', primitive_order=[]))
        ms.register_peer('r02')
        ms.announce('etd.foo')
        ms.receive_from_peer('r02')
        assert ms.pending_announcement_count == 0


# ── OnRobotStore ──────────────────────────────────────────────────────────────

class TestOnRobotStore:
    def _store(self, tmp_path, node_id='robot-01') -> OnRobotStore:
        return OnRobotStore(cache_dir=tmp_path / 'cache', node_id=node_id)

    def _populate(self, store: OnRobotStore, skill_id='etd.pickplace.basic') -> None:
        store.entitlement_cache.add(
            token_str='tok.sig',
            skill_id=skill_id, station_id='ws-01',
            operator_org='ACME', expiry=_future_expiry(),
        )
        store.manifest_cache.put(CachedManifest(
            skill_id=skill_id, version='0.1.0',
            family='pickplace', primitive_order=['approach', 'grasp', 'place'],
        ))

    def test_not_available_offline_initially(self, tmp_path):
        store = self._store(tmp_path)
        assert store.is_available_offline('etd.foo', 'ws-01') is False

    def test_is_available_offline_after_populate(self, tmp_path):
        store = self._store(tmp_path)
        self._populate(store)
        assert store.is_available_offline('etd.pickplace.basic', 'ws-01') is True

    def test_install_offline_success(self, tmp_path):
        store = self._store(tmp_path)
        self._populate(store)
        result = store.install_offline('etd.pickplace.basic', 'ws-01')
        assert result.success is True
        assert result.reason == 'served_from_cache'
        assert result.entitlement is not None
        assert result.manifest is not None

    def test_install_offline_no_entitlement(self, tmp_path):
        store = self._store(tmp_path)
        store.manifest_cache.put(CachedManifest(
            skill_id='etd.foo', version='1.0', family='f', primitive_order=[],
        ))
        result = store.install_offline('etd.foo', 'ws-01')
        assert result.success is False
        assert 'entitlement' in result.reason

    def test_install_offline_no_manifest(self, tmp_path):
        store = self._store(tmp_path)
        store.entitlement_cache.add(
            'tok', 'etd.foo', 'ws-01', 'ACME', _future_expiry(),
        )
        result = store.install_offline('etd.foo', 'ws-01')
        assert result.success is False
        assert 'manifest' in result.reason

    def test_offline_install_result_str(self, tmp_path):
        store = self._store(tmp_path)
        self._populate(store)
        result = store.install_offline('etd.pickplace.basic', 'ws-01')
        s = str(result)
        assert '[OK]' in s
        assert 'etd.pickplace.basic' in s

    def test_sync_from_central_updates_manifests(self, tmp_path):
        store = self._store(tmp_path)
        entries = [
            {'skillId': 'etd.foo', 'version': '1.0', 'family': 'pickplace',
             'primitiveOrder': ['a', 'b']},
            {'skillId': 'etd.bar', 'version': '2.0', 'family': 'weld',
             'primitiveOrder': ['x']},
        ]
        stats = store.sync_from_central(entries)
        assert stats['manifests_updated'] == 2
        assert store.manifest_cache.get('etd.foo') is not None
        assert store.manifest_cache.get('etd.bar') is not None

    def test_sync_from_central_caches_entitlements(self, tmp_path):
        store = self._store(tmp_path)
        tokens = [{'token_str': 't', 'skill_id': 'etd.foo', 'station_id': '*',
                   'operator_org': 'X', 'expiry': _future_expiry()}]
        stats = store.sync_from_central([], entitlement_tokens=tokens)
        assert stats['entitlements_cached'] == 1

    def test_sync_skips_expired_tokens(self, tmp_path):
        store = self._store(tmp_path)
        tokens = [{'token_str': 't', 'skill_id': 'etd.foo', 'station_id': '*',
                   'operator_org': 'X', 'expiry': _past_expiry()}]
        stats = store.sync_from_central([], entitlement_tokens=tokens)
        assert stats['entitlements_skipped'] == 1

    def test_sync_skips_entries_without_skill_id(self, tmp_path):
        store = self._store(tmp_path)
        stats = store.sync_from_central([{'version': '1.0'}])
        assert stats['manifests_updated'] == 0

    def test_get_offline_skills(self, tmp_path):
        store = self._store(tmp_path)
        self._populate(store, 'etd.pickplace.basic')
        self._populate(store, 'etd.inspect.vision')
        offline = store.get_offline_skills()
        assert 'etd.pickplace.basic' in offline
        assert 'etd.inspect.vision' in offline

    def test_get_offline_skills_excludes_manifest_only(self, tmp_path):
        store = self._store(tmp_path)
        store.manifest_cache.put(CachedManifest(
            skill_id='etd.noent', version='1.0', family='f', primitive_order=[],
        ))
        offline = store.get_offline_skills()
        assert 'etd.noent' not in offline

    def test_evict_expired_entitlements(self, tmp_path):
        store = self._store(tmp_path)
        # inject expired entry directly
        store.entitlement_cache._entries.append(CachedEntitlement(
            skill_id='etd.exp', station_id='*',
            operator_org='', expiry=_past_expiry(), token_str='t',
        ))
        self._populate(store)
        removed = store.evict_expired_entitlements()
        assert removed == 1

    def test_summary_contains_node_id(self, tmp_path):
        store = self._store(tmp_path, node_id='arm-bot-42')
        assert 'arm-bot-42' in store.summary()

    def test_to_dict_structure(self, tmp_path):
        store = self._store(tmp_path)
        self._populate(store)
        d = store.to_dict()
        assert 'node_id' in d
        assert 'offline_skills' in d
        assert isinstance(d['offline_skills'], list)

    def test_cache_dir_created_automatically(self, tmp_path):
        nested = tmp_path / 'a' / 'b' / 'cache'
        store = OnRobotStore(cache_dir=nested)
        assert nested.exists()


# ── CLI: onrobot cache list ───────────────────────────────────────────────────

class TestCLIOnRobotCacheList:
    def test_list_empty(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'cache', 'list', '--cache-dir', str(tmp_path),
        ])
        assert result.exit_code == 0
        assert 'OnRobotStore' in result.output

    def test_list_json(self, tmp_path):
        import json as _json
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'cache', 'list', '--cache-dir', str(tmp_path), '--json',
        ])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert 'node_id' in data
        assert 'offline_skills' in data


# ── CLI: onrobot cache add ────────────────────────────────────────────────────

class TestCLIOnRobotCacheAdd:
    def test_add_valid_token(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'cache', 'add', 'etd.foo',
            '--token', 'tok.sig',
            '--station', 'ws-01',
            '--expiry', _future_expiry(),
            '--cache-dir', str(tmp_path),
        ])
        assert result.exit_code == 0
        assert 'Cached' in result.output

    def test_add_expired_token_fails(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'cache', 'add', 'etd.foo',
            '--token', 'tok.sig',
            '--station', 'ws-01',
            '--expiry', _past_expiry(),
            '--cache-dir', str(tmp_path),
        ])
        assert result.exit_code == 1


# ── CLI: onrobot cache evict ──────────────────────────────────────────────────

class TestCLIOnRobotCacheEvict:
    def test_evict(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'cache', 'evict', '--cache-dir', str(tmp_path),
        ])
        assert result.exit_code == 0
        assert 'Evicted' in result.output


# ── CLI: onrobot sync status ──────────────────────────────────────────────────

class TestCLIOnRobotSyncStatus:
    def test_sync_status_no_peers(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'sync', 'status', '--cache-dir', str(tmp_path),
        ])
        assert result.exit_code == 0
        assert 'No mesh peers' in result.output

    def test_sync_status_json(self, tmp_path):
        import json as _json
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'onrobot', 'sync', 'status', '--cache-dir', str(tmp_path), '--json',
        ])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert isinstance(data, list)
