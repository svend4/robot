"""Tests for marketplace.fleet_manager — FleetManager and fleet deployment."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketplace.fleet_manager import (
    DEPLOY_STATUSES,
    FleetDeployment,
    FleetHealthSnapshot,
    FleetManager,
    NodeDeployResult,
    RobotNode,
)

ROOT = Path(__file__).parent.parent
ATLAS_PKG = ROOT / 'examples' / 'etd.atlas.humanoid_walkfetch'
PICKPLACE_PKG = ROOT / 'examples' / 'etd.pickplace.basic'


# ── RobotNode ─────────────────────────────────────────────────────────────────

class TestRobotNode:
    def _make(self, node_id='r01', platform='atlas') -> RobotNode:
        return RobotNode(node_id=node_id, station_id='ws-01', platform_id=platform)

    def test_defaults(self):
        n = self._make()
        assert n.status == 'unknown'
        assert n.installed_skills == []
        assert n.last_seen is None

    def test_to_dict_roundtrip(self):
        n = self._make()
        n.installed_skills = ['etd.foo']
        n2 = RobotNode.from_dict(n.to_dict())
        assert n2.node_id == n.node_id
        assert n2.station_id == n.station_id
        assert n2.platform_id == n.platform_id
        assert n2.installed_skills == n.installed_skills

    def test_from_dict_defaults(self):
        n = RobotNode.from_dict({'node_id': 'r', 'station_id': 's',
                                  'platform_id': 'atlas'})
        assert n.status == 'unknown'
        assert n.metadata == {}


# ── NodeDeployResult ──────────────────────────────────────────────────────────

class TestNodeDeployResult:
    def test_to_dict_roundtrip(self):
        r = NodeDeployResult(node_id='r1', station_id='ws-01',
                             success=True, reason='deployed',
                             deployed_at='2026-01-01T00:00:00+00:00')
        r2 = NodeDeployResult.from_dict(r.to_dict())
        assert r2.node_id == r.node_id
        assert r2.success == r.success
        assert r2.deployed_at == r.deployed_at

    def test_from_dict_defaults(self):
        r = NodeDeployResult.from_dict(
            {'node_id': 'r', 'station_id': 's', 'success': False, 'reason': 'x'})
        assert r.deployed_at is None


# ── FleetDeployment ───────────────────────────────────────────────────────────

class TestFleetDeployment:
    def _make(self) -> FleetDeployment:
        d = FleetDeployment(
            deployment_id='dep-001',
            skill_id='etd.pickplace.basic',
            version='0.1.0',
            target_node_ids=['r01', 'r02'],
            status='completed',
        )
        d.node_results = [
            NodeDeployResult('r01', 'ws-01', True, 'deployed'),
            NodeDeployResult('r02', 'ws-02', False, 'platform_incompatible'),
        ]
        return d

    def test_nodes_succeeded(self):
        d = self._make()
        assert d.nodes_succeeded == 1

    def test_nodes_failed(self):
        d = self._make()
        assert d.nodes_failed == 1

    def test_summary_contains_skill_id(self):
        s = self._make().summary()
        assert 'etd.pickplace.basic' in s

    def test_summary_contains_node_results(self):
        s = self._make().summary()
        assert 'r01' in s
        assert 'r02' in s

    def test_to_dict_roundtrip(self):
        d = self._make()
        d2 = FleetDeployment.from_dict(d.to_dict())
        assert d2.deployment_id == d.deployment_id
        assert d2.skill_id == d.skill_id
        assert len(d2.node_results) == 2

    def test_to_dict_has_counts(self):
        d = self._make().to_dict()
        assert d['nodes_succeeded'] == 1
        assert d['nodes_failed'] == 1

    def test_valid_deploy_statuses(self):
        assert 'completed' in DEPLOY_STATUSES
        assert 'failed' in DEPLOY_STATUSES
        assert 'partial' in DEPLOY_STATUSES


# ── FleetHealthSnapshot ───────────────────────────────────────────────────────

class TestFleetHealthSnapshot:
    def _make(self) -> FleetHealthSnapshot:
        return FleetHealthSnapshot(
            generated_at='2026-01-01T00:00:00+00:00',
            total_nodes=3,
            online_nodes=2,
            offline_nodes=0,
            unknown_nodes=1,
            total_deployments=5,
            active_deployments=1,
            skill_coverage={'etd.pickplace.basic': 2, 'etd.inspect.vision': 1},
        )

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        for key in ('total_nodes', 'online_nodes', 'skill_coverage',
                    'total_deployments', 'active_deployments'):
            assert key in d

    def test_render_ascii_contains_nodes(self):
        out = self._make().render_ascii()
        assert '3' in out
        assert 'Fleet Health' in out

    def test_render_ascii_contains_skills(self):
        out = self._make().render_ascii()
        assert 'etd.pickplace.basic' in out


# ── FleetManager ──────────────────────────────────────────────────────────────

class TestFleetManagerRegistry:
    def _fm(self, tmp_path) -> FleetManager:
        return FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=False)

    def test_no_nodes_initially(self, tmp_path):
        fm = self._fm(tmp_path)
        assert fm.node_count == 0

    def test_register_node(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        assert fm.node_count == 1
        assert fm.get_node('r01') is not None

    def test_register_replaces_existing(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        fm.register_node(RobotNode('r01', 'ws-02', 'unitree_g1'))
        assert fm.node_count == 1
        assert fm.get_node('r01').station_id == 'ws-02'

    def test_unregister_existing(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        assert fm.unregister_node('r01') is True
        assert fm.node_count == 0

    def test_unregister_nonexistent(self, tmp_path):
        fm = self._fm(tmp_path)
        assert fm.unregister_node('ghost') is False

    def test_get_node_returns_none_when_absent(self, tmp_path):
        fm = self._fm(tmp_path)
        assert fm.get_node('missing') is None

    def test_list_nodes_returns_all(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        fm.register_node(RobotNode('r02', 'ws-02', 'unitree_g1'))
        nodes = fm.list_nodes()
        ids = {n.node_id for n in nodes}
        assert 'r01' in ids
        assert 'r02' in ids

    def test_persists_across_instances(self, tmp_path):
        fm1 = FleetManager(tmp_path / 'fleet', check_platform_compat=False)
        fm1.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        fm2 = FleetManager(tmp_path / 'fleet', check_platform_compat=False)
        assert fm2.get_node('r01') is not None

    def test_data_dir_created_automatically(self, tmp_path):
        nested = tmp_path / 'a' / 'b' / 'fleet'
        FleetManager(data_dir=nested)
        assert nested.exists()


class TestFleetManagerHeartbeat:
    def _fm(self, tmp_path) -> FleetManager:
        fm = FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=False)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        return fm

    def test_heartbeat_updates_status(self, tmp_path):
        fm = self._fm(tmp_path)
        assert fm.heartbeat('r01', status='online') is True
        assert fm.get_node('r01').status == 'online'

    def test_heartbeat_updates_last_seen(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.heartbeat('r01')
        assert fm.get_node('r01').last_seen is not None

    def test_heartbeat_updates_skills(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.heartbeat('r01', installed_skills=['etd.pickplace.basic'])
        assert 'etd.pickplace.basic' in fm.get_node('r01').installed_skills

    def test_heartbeat_unknown_node_returns_false(self, tmp_path):
        fm = self._fm(tmp_path)
        assert fm.heartbeat('ghost') is False


class TestFleetManagerDeploy:
    def _fm(self, tmp_path) -> FleetManager:
        fm = FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=False)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        fm.register_node(RobotNode('r02', 'ws-02', 'unitree_g1'))
        return fm

    def test_deploy_all_nodes_succeed(self, tmp_path):
        fm = self._fm(tmp_path)
        dep = fm.deploy('etd.pickplace.basic', '0.1.0', ['r01', 'r02'])
        assert dep.status == 'completed'
        assert dep.nodes_succeeded == 2
        assert dep.nodes_failed == 0

    def test_deploy_unknown_node_fails(self, tmp_path):
        fm = self._fm(tmp_path)
        dep = fm.deploy('etd.pickplace.basic', '0.1.0', ['ghost'])
        assert dep.status == 'failed'
        assert dep.node_results[0].reason == 'node_not_registered'

    def test_deploy_partial_when_some_fail(self, tmp_path):
        fm = self._fm(tmp_path)
        dep = fm.deploy('etd.pickplace.basic', '0.1.0', ['r01', 'ghost'])
        assert dep.status == 'partial'
        assert dep.nodes_succeeded == 1
        assert dep.nodes_failed == 1

    def test_deploy_updates_installed_skills(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        assert 'etd.pickplace.basic' in fm.get_node('r01').installed_skills

    def test_deploy_no_duplicate_skill_in_inventory(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        assert fm.get_node('r01').installed_skills.count('etd.pickplace.basic') == 1

    def test_deploy_sets_completed_at(self, tmp_path):
        fm = self._fm(tmp_path)
        dep = fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        assert dep.completed_at is not None

    def test_deploy_result_node_id_and_station(self, tmp_path):
        fm = self._fm(tmp_path)
        dep = fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        r = dep.node_results[0]
        assert r.node_id == 'r01'
        assert r.station_id == 'ws-01'

    def test_deploy_persists_deployment(self, tmp_path):
        fm = self._fm(tmp_path)
        dep = fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        fm2 = FleetManager(tmp_path / 'fleet', check_platform_compat=False)
        assert fm2.get_deployment(dep.deployment_id) is not None

    def test_deploy_with_platform_compat_check(self, tmp_path):
        """atlas skill should be incompatible with hyundai_mobed (transport only)."""
        from marketplace.cross_platform import load_skill_info
        fm = FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=True)
        fm.register_node(RobotNode('mobed-01', 'dock-01', 'hyundai_mobed'))
        skill_info = load_skill_info(ATLAS_PKG)
        dep = fm.deploy(
            skill_id=skill_info['skillId'],
            version='0.1.0',
            target_node_ids=['mobed-01'],
            skill_info=skill_info,
            source_platform='atlas',
        )
        assert dep.node_results[0].reason == 'platform_incompatible'

    def test_deploy_with_compat_check_compatible(self, tmp_path):
        """Atlas skill compatible with Unitree G1."""
        from marketplace.cross_platform import load_skill_info
        fm = FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=True)
        fm.register_node(RobotNode('g1-01', 'ws-01', 'unitree_g1'))
        skill_info = load_skill_info(ATLAS_PKG)
        dep = fm.deploy(
            skill_id=skill_info['skillId'],
            version='0.1.0',
            target_node_ids=['g1-01'],
            skill_info=skill_info,
            source_platform='atlas',
        )
        assert dep.node_results[0].success is True


class TestFleetManagerDeploymentQueries:
    def _fm_with_deployments(self, tmp_path) -> FleetManager:
        fm = FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=False)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        fm.deploy('etd.inspect.vision', '0.1.0', ['r01'])
        return fm

    def test_list_deployments_all(self, tmp_path):
        fm = self._fm_with_deployments(tmp_path)
        deps = fm.list_deployments()
        assert len(deps) == 2

    def test_list_deployments_filter_skill(self, tmp_path):
        fm = self._fm_with_deployments(tmp_path)
        deps = fm.list_deployments(skill_id='etd.pickplace.basic')
        assert len(deps) == 1
        assert all(d.skill_id == 'etd.pickplace.basic' for d in deps)

    def test_list_deployments_filter_status(self, tmp_path):
        fm = self._fm_with_deployments(tmp_path)
        deps = fm.list_deployments(status='completed')
        assert all(d.status == 'completed' for d in deps)

    def test_get_deployment_found(self, tmp_path):
        fm = self._fm_with_deployments(tmp_path)
        dep = fm.list_deployments()[0]
        found = fm.get_deployment(dep.deployment_id)
        assert found is not None
        assert found.deployment_id == dep.deployment_id

    def test_get_deployment_not_found(self, tmp_path):
        fm = self._fm_with_deployments(tmp_path)
        assert fm.get_deployment('nonexistent-id') is None

    def test_deployment_count(self, tmp_path):
        fm = self._fm_with_deployments(tmp_path)
        assert fm.deployment_count == 2


class TestFleetManagerFleetStatus:
    def _fm(self, tmp_path) -> FleetManager:
        fm = FleetManager(data_dir=tmp_path / 'fleet', check_platform_compat=False)
        fm.register_node(RobotNode('r01', 'ws-01', 'atlas'))
        fm.register_node(RobotNode('r02', 'ws-02', 'unitree_g1'))
        fm.heartbeat('r01', status='online',
                     installed_skills=['etd.pickplace.basic'])
        fm.heartbeat('r02', status='online',
                     installed_skills=['etd.pickplace.basic', 'etd.inspect.vision'])
        return fm

    def test_fleet_status_node_counts(self, tmp_path):
        fm = self._fm(tmp_path)
        snap = fm.fleet_status()
        assert snap.total_nodes == 2
        assert snap.online_nodes == 2

    def test_fleet_status_skill_coverage(self, tmp_path):
        fm = self._fm(tmp_path)
        snap = fm.fleet_status()
        assert snap.skill_coverage.get('etd.pickplace.basic') == 2
        assert snap.skill_coverage.get('etd.inspect.vision') == 1

    def test_fleet_status_deployment_count(self, tmp_path):
        fm = self._fm(tmp_path)
        fm.deploy('etd.pickplace.basic', '0.1.0', ['r01'])
        snap = fm.fleet_status()
        assert snap.total_deployments == 1

    def test_fleet_status_to_dict(self, tmp_path):
        snap = self._fm(tmp_path).fleet_status()
        d = snap.to_dict()
        assert 'total_nodes' in d
        assert 'skill_coverage' in d

    def test_fleet_status_render_ascii(self, tmp_path):
        snap = self._fm(tmp_path).fleet_status()
        out = snap.render_ascii()
        assert 'Fleet Health' in out


# ── CLI: fleet nodes ──────────────────────────────────────────────────────────

class TestCLIFleetNodes:
    def test_list_empty(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['fleet', 'nodes', 'list',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert 'No nodes' in result.output

    def test_register_and_list(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        runner.invoke(cli, ['fleet', 'nodes', 'register', 'r01',
                             '--station', 'ws-01', '--platform', 'atlas',
                             '--fleet-dir', str(tmp_path)])
        result = runner.invoke(cli, ['fleet', 'nodes', 'list',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert 'r01' in result.output

    def test_register_and_list_json(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        runner.invoke(cli, ['fleet', 'nodes', 'register', 'r01',
                             '--station', 'ws-01', '--platform', 'atlas',
                             '--fleet-dir', str(tmp_path)])
        result = runner.invoke(cli, ['fleet', 'nodes', 'list', '--json',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]['node_id'] == 'r01'

    def test_unregister_existing(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        runner.invoke(cli, ['fleet', 'nodes', 'register', 'r01',
                             '--station', 'ws-01', '--platform', 'atlas',
                             '--fleet-dir', str(tmp_path)])
        result = runner.invoke(cli, ['fleet', 'nodes', 'unregister', 'r01',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0

    def test_unregister_nonexistent_exits_1(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['fleet', 'nodes', 'unregister', 'ghost',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 1


# ── CLI: fleet deploy ─────────────────────────────────────────────────────────

class TestCLIFleetDeploy:
    def _setup(self, runner, tmp_path):
        from etd_cli import cli
        runner.invoke(cli, ['fleet', 'nodes', 'register', 'r01',
                             '--station', 'ws-01', '--platform', 'atlas',
                             '--fleet-dir', str(tmp_path)])

    def test_deploy_succeeds(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        self._setup(runner, tmp_path)
        result = runner.invoke(cli, [
            'fleet', 'deploy', 'etd.pickplace.basic',
            '--nodes', 'r01', '--fleet-dir', str(tmp_path),
        ])
        assert result.exit_code == 0
        assert 'COMPLETED' in result.output

    def test_deploy_json(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        self._setup(runner, tmp_path)
        result = runner.invoke(cli, [
            'fleet', 'deploy', 'etd.pickplace.basic',
            '--nodes', 'r01', '--json', '--fleet-dir', str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['status'] == 'completed'

    def test_deploy_no_nodes_exits_1(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'fleet', 'deploy', 'etd.pickplace.basic',
            '--fleet-dir', str(tmp_path),
        ])
        assert result.exit_code == 1


# ── CLI: fleet status ─────────────────────────────────────────────────────────

class TestCLIFleetStatus:
    def test_status_ascii(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['fleet', 'status', '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert 'Fleet Health' in result.output

    def test_status_json(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['fleet', 'status', '--json',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'total_nodes' in data


# ── CLI: fleet deployments ────────────────────────────────────────────────────

class TestCLIFleetDeployments:
    def test_deployments_empty(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['fleet', 'deployments',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        assert 'No deployments' in result.output

    def test_deployments_json(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        runner.invoke(cli, ['fleet', 'nodes', 'register', 'r01',
                             '--station', 'ws-01', '--platform', 'atlas',
                             '--fleet-dir', str(tmp_path)])
        runner.invoke(cli, ['fleet', 'deploy', 'etd.pickplace.basic',
                             '--nodes', 'r01', '--fleet-dir', str(tmp_path)])
        result = runner.invoke(cli, ['fleet', 'deployments', '--json',
                                     '--fleet-dir', str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
