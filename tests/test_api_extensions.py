"""Tests for the extended ETD REST API: cross-platform, fleet, and composer routers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)

ROOT = Path(__file__).parent.parent
ATLAS_PKG = ROOT / 'examples' / 'etd.atlas.humanoid_walkfetch'
COMPOSED_PKG_NAME = 'etd.composed.fetch_inspect_place'


# ── /platform ─────────────────────────────────────────────────────────────────

class TestPlatformList:
    def test_list_returns_200(self):
        r = client.get('/platform/list')
        assert r.status_code == 200

    def test_list_returns_six_platforms(self):
        data = client.get('/platform/list').json()
        assert len(data) == 6

    def test_list_has_atlas(self):
        data = client.get('/platform/list').json()
        ids = {p['platform_id'] for p in data}
        assert 'atlas' in ids

    def test_list_platform_structure(self):
        data = client.get('/platform/list').json()
        for p in data:
            assert 'platform_id' in p
            assert 'families' in p
            assert 'supported_primitives' in p


class TestPlatformGet:
    def test_get_known_platform(self):
        r = client.get('/platform/platform/atlas')
        assert r.status_code == 200
        assert r.json()['platform_id'] == 'atlas'

    def test_get_unknown_platform_404(self):
        r = client.get('/platform/platform/ghost_bot')
        assert r.status_code == 404

    def test_get_unitree_g1(self):
        r = client.get('/platform/platform/unitree_g1')
        assert r.status_code == 200
        data = r.json()
        assert 'humanoid' in data['families']


class TestPlatformCheck:
    def _atlas_skill_body(self):
        import json as _json
        info = _json.loads((ATLAS_PKG / 'skill.json').read_text())
        return {
            'skill_info': {
                'skillId': info['skillId'],
                'family': info['family'],
                'primitiveOrder': info.get('primitiveOrder', []),
            },
            'source': 'atlas',
            'target': 'unitree_g1',
        }

    def test_compatible_returns_200(self):
        r = client.post('/platform/check', json=self._atlas_skill_body())
        assert r.status_code == 200

    def test_compatible_result(self):
        data = client.post('/platform/check', json=self._atlas_skill_body()).json()
        assert data['compatible'] is True
        assert data['source_platform'] == 'atlas'
        assert data['target_platform'] == 'unitree_g1'

    def test_incompatible_result(self):
        body = self._atlas_skill_body()
        body['target'] = 'unitree_h1'
        data = client.post('/platform/check', json=body).json()
        assert data['compatible'] is False
        assert len(data['missing_primitives']) > 0

    def test_topic_remappings_present(self):
        data = client.post('/platform/check', json=self._atlas_skill_body()).json()
        assert isinstance(data['topic_remappings'], dict)
        assert len(data['topic_remappings']) > 0

    def test_family_mismatch(self):
        body = self._atlas_skill_body()
        body['target'] = 'hyundai_mobed'
        data = client.post('/platform/check', json=body).json()
        assert data['compatible'] is False


class TestPlatformMatrix:
    def test_matrix_no_skill_returns_200(self):
        r = client.post('/platform/matrix', json={})
        assert r.status_code == 200

    def test_matrix_returns_30_pairs(self):
        data = client.post('/platform/matrix', json={}).json()
        assert len(data) == 30

    def test_matrix_no_self_pairs(self):
        data = client.post('/platform/matrix', json={}).json()
        for row in data:
            assert row['source'] != row['target']

    def test_matrix_with_skill_info(self):
        import json as _json
        info = _json.loads((ATLAS_PKG / 'skill.json').read_text())
        body = {
            'skill_info': {
                'skillId': info['skillId'],
                'family': info['family'],
                'primitiveOrder': info.get('primitiveOrder', []),
            }
        }
        data = client.post('/platform/matrix', json=body).json()
        assert len(data) == 30
        assert all('missing_primitives' in row for row in data)

    def test_matrix_family_filter(self):
        data = client.post('/platform/matrix',
                           json={'families': ['humanoid']}).json()
        assert len(data) == 6  # 3 humanoid platforms → 3×2 pairs


# ── /fleet ────────────────────────────────────────────────────────────────────

class TestFleetNodes:
    def test_list_nodes_empty(self):
        r = client.get('/fleet/nodes')
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_register_node_201(self):
        r = client.post('/fleet/nodes', json={
            'node_id': 'api-r01',
            'station_id': 'ws-api-01',
            'platform_id': 'atlas',
        })
        assert r.status_code == 201
        assert r.json()['node_id'] == 'api-r01'

    def test_register_then_list(self):
        client.post('/fleet/nodes', json={
            'node_id': 'api-r99',
            'station_id': 'ws-99',
            'platform_id': 'unitree_g1',
        })
        nodes = client.get('/fleet/nodes').json()
        ids = {n['node_id'] for n in nodes}
        assert 'api-r99' in ids

    def test_get_node_found(self):
        client.post('/fleet/nodes', json={
            'node_id': 'api-get-01',
            'station_id': 'ws-01',
            'platform_id': 'atlas',
        })
        r = client.get('/fleet/nodes/api-get-01')
        assert r.status_code == 200
        assert r.json()['node_id'] == 'api-get-01'

    def test_get_node_404(self):
        r = client.get('/fleet/nodes/ghost-node-zzz')
        assert r.status_code == 404

    def test_delete_node(self):
        client.post('/fleet/nodes', json={
            'node_id': 'api-del-01',
            'station_id': 'ws-del',
            'platform_id': 'atlas',
        })
        r = client.delete('/fleet/nodes/api-del-01')
        assert r.status_code == 200
        assert r.json()['removed'] == 'api-del-01'

    def test_delete_node_404(self):
        r = client.delete('/fleet/nodes/ghost-node-delete')
        assert r.status_code == 404

    def test_heartbeat_updates_status(self):
        client.post('/fleet/nodes', json={
            'node_id': 'api-hb-01',
            'station_id': 'ws-hb',
            'platform_id': 'atlas',
        })
        r = client.put('/fleet/nodes/api-hb-01/heartbeat',
                       json={'status': 'online'})
        assert r.status_code == 200
        assert r.json()['status'] == 'online'

    def test_heartbeat_404(self):
        r = client.put('/fleet/nodes/ghost-hb/heartbeat',
                       json={'status': 'online'})
        assert r.status_code == 404


class TestFleetDeployments:
    def _ensure_node(self, node_id='api-dep-node'):
        client.post('/fleet/nodes', json={
            'node_id': node_id,
            'station_id': 'ws-dep',
            'platform_id': 'atlas',
        })

    def test_deploy_201(self):
        self._ensure_node()
        r = client.post('/fleet/deployments', json={
            'skill_id': 'etd.pickplace.basic',
            'version': '0.1.0',
            'target_node_ids': ['api-dep-node'],
        })
        assert r.status_code == 201

    def test_deploy_completed_status(self):
        self._ensure_node()
        data = client.post('/fleet/deployments', json={
            'skill_id': 'etd.pickplace.basic',
            'version': '0.1.0',
            'target_node_ids': ['api-dep-node'],
        }).json()
        assert data['status'] == 'completed'

    def test_deploy_result_structure(self):
        self._ensure_node()
        data = client.post('/fleet/deployments', json={
            'skill_id': 'etd.pickplace.basic',
            'version': '0.1.0',
            'target_node_ids': ['api-dep-node'],
        }).json()
        assert 'deployment_id' in data
        assert 'node_results' in data
        assert isinstance(data['node_results'], list)

    def test_list_deployments_200(self):
        r = client.get('/fleet/deployments')
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_deployment_found(self):
        self._ensure_node()
        dep = client.post('/fleet/deployments', json={
            'skill_id': 'etd.pickplace.basic',
            'version': '0.1.0',
            'target_node_ids': ['api-dep-node'],
        }).json()
        r = client.get(f'/fleet/deployments/{dep["deployment_id"]}')
        assert r.status_code == 200

    def test_get_deployment_404(self):
        r = client.get('/fleet/deployments/nonexistent-uuid')
        assert r.status_code == 404

    def test_list_deployments_filter_skill(self):
        self._ensure_node('api-filter-node')
        client.post('/fleet/deployments', json={
            'skill_id': 'etd.inspect.vision',
            'version': '0.1.0',
            'target_node_ids': ['api-filter-node'],
        })
        data = client.get('/fleet/deployments?skill_id=etd.inspect.vision').json()
        assert all(d['skill_id'] == 'etd.inspect.vision' for d in data)


class TestFleetStatus:
    def test_status_200(self):
        r = client.get('/fleet/status')
        assert r.status_code == 200

    def test_status_structure(self):
        data = client.get('/fleet/status').json()
        assert 'total_nodes' in data
        assert 'skill_coverage' in data
        assert 'total_deployments' in data


# ── /compose ──────────────────────────────────────────────────────────────────

def _simple_composed_body(valid=True):
    steps = [{'skillId': 'etd.pickplace.basic'}] if valid else []
    return {
        'composed': {
            'skillId': 'etd.composed.test',
            'version': '1.0.0',
            'steps': steps,
        }
    }


class TestComposeValidate:
    def test_valid_returns_200(self):
        r = client.post('/compose/validate', json=_simple_composed_body(valid=True))
        assert r.status_code == 200

    def test_valid_result(self):
        data = client.post('/compose/validate',
                           json=_simple_composed_body(valid=True)).json()
        assert data['valid'] is True
        assert data['issues'] == []
        assert data['step_count'] == 1

    def test_invalid_no_steps(self):
        data = client.post('/compose/validate',
                           json=_simple_composed_body(valid=False)).json()
        assert data['valid'] is False
        assert len(data['issues']) > 0

    def test_self_reference_invalid(self):
        body = {
            'composed': {
                'skillId': 'etd.composed.loop',
                'version': '1.0.0',
                'steps': [{'skillId': 'etd.composed.loop'}],
            }
        }
        data = client.post('/compose/validate', json=body).json()
        assert data['valid'] is False
        assert any('cycle' in i for i in data['issues'])

    def test_response_has_skill_id(self):
        data = client.post('/compose/validate',
                           json=_simple_composed_body()).json()
        assert data['skill_id'] == 'etd.composed.test'


class TestComposeRun:
    def test_run_returns_200(self):
        r = client.post('/compose/run', json=_simple_composed_body())
        assert r.status_code == 200

    def test_run_success_status(self):
        data = client.post('/compose/run', json=_simple_composed_body()).json()
        assert data['status'] == 'success'

    def test_run_step_results(self):
        data = client.post('/compose/run', json=_simple_composed_body()).json()
        assert len(data['step_results']) == 1
        assert data['step_results'][0]['status'] == 'success'

    def test_run_multi_step(self):
        body = {
            'composed': {
                'skillId': 'etd.composed.multi',
                'version': '1.0.0',
                'steps': [
                    {'skillId': 'etd.pickplace.basic'},
                    {'skillId': 'etd.inspect.vision'},
                    {'skillId': 'etd.cobot.safeassist'},
                ],
            }
        }
        data = client.post('/compose/run', json=body).json()
        assert data['status'] == 'success'
        assert len(data['step_results']) == 3

    def test_run_result_structure(self):
        data = client.post('/compose/run', json=_simple_composed_body()).json()
        assert 'skill_id' in data
        assert 'total_duration_ms' in data
        assert 'safety_violations' in data


class TestComposeExamples:
    def test_list_examples(self):
        r = client.get('/compose/examples')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_example_structure(self):
        data = client.get('/compose/examples').json()
        assert data[0]['skill_id'] == 'etd.composed.fetch_inspect_place'
        assert data[0]['step_count'] == 3

    def test_validate_example(self):
        r = client.get(f'/compose/examples/{COMPOSED_PKG_NAME}/validate')
        assert r.status_code == 200
        data = r.json()
        assert data['valid'] is True

    def test_run_example(self):
        r = client.get(f'/compose/examples/{COMPOSED_PKG_NAME}/run')
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'success'
        assert len(data['step_results']) == 3

    def test_validate_example_404(self):
        r = client.get('/compose/examples/nonexistent.package/validate')
        assert r.status_code == 404

    def test_run_example_404(self):
        r = client.get('/compose/examples/nonexistent.package/run')
        assert r.status_code == 404
