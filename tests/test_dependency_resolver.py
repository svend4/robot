"""Tests for marketplace.dependency_resolver and the /deps REST API."""
from __future__ import annotations

from pathlib import Path

import pytest

from marketplace.dependency_resolver import (
    CyclicDependencyError,
    DependencyGraph,
    DependencyResolver,
    DependencyStore,
    SkillDependency,
)


# ── SkillDependency ───────────────────────────────────────────────────────────

class TestSkillDependency:
    def test_to_dict_keys(self):
        d = SkillDependency('etd.pick', '>=0.1.0', optional=True)
        dd = d.to_dict()
        assert set(dd) == {'skill_id', 'version_constraint', 'optional'}

    def test_round_trip(self):
        d = SkillDependency('etd.pick', '>=0.2.0', optional=False)
        d2 = SkillDependency.from_dict(d.to_dict())
        assert d2.skill_id == 'etd.pick'
        assert d2.version_constraint == '>=0.2.0'
        assert d2.optional is False

    def test_defaults(self):
        d = SkillDependency.from_dict({'skill_id': 'x'})
        assert d.version_constraint == ''
        assert d.optional is False

    def test_optional_flag(self):
        d = SkillDependency.from_dict({'skill_id': 'x', 'optional': True})
        assert d.optional is True


# ── DependencyGraph ───────────────────────────────────────────────────────────

class TestDependencyGraph:
    def _graph(self) -> DependencyGraph:
        g = DependencyGraph()
        g.add_skill('etd.pipeline', ['etd.pick', 'etd.inspect'])
        g.add_skill('etd.pick', ['etd.gripper'])
        g.add_skill('etd.inspect', [])
        g.add_skill('etd.gripper', [])
        return g

    def test_skills_listed(self):
        g = self._graph()
        assert set(g.skills()) >= {'etd.pipeline', 'etd.pick', 'etd.inspect'}

    def test_resolve_leaf(self):
        g = self._graph()
        assert g.resolve('etd.gripper') == ['etd.gripper']

    def test_resolve_order_deps_before_root(self):
        g = self._graph()
        order = g.resolve('etd.pipeline')
        assert order[-1] == 'etd.pipeline'
        assert order.index('etd.pick') < order.index('etd.pipeline')
        assert order.index('etd.inspect') < order.index('etd.pipeline')
        assert order.index('etd.gripper') < order.index('etd.pick')

    def test_resolve_unknown_returns_single(self):
        g = DependencyGraph()
        assert g.resolve('ghost') == ['ghost']

    def test_resolve_raises_on_cycle(self):
        g = DependencyGraph()
        g.add_skill('a', ['b'])
        g.add_skill('b', ['a'])
        with pytest.raises(CyclicDependencyError):
            g.resolve('a')

    def test_resolve_self_cycle(self):
        g = DependencyGraph()
        g.add_skill('a', ['a'])
        with pytest.raises(CyclicDependencyError):
            g.resolve('a')

    def test_detect_cycles_none(self):
        g = self._graph()
        assert g.detect_cycles() == []

    def test_detect_cycles_finds_cycle(self):
        g = DependencyGraph()
        g.add_skill('a', ['b'])
        g.add_skill('b', ['c'])
        g.add_skill('c', ['a'])
        cycles = g.detect_cycles()
        assert len(cycles) >= 1
        # Each cycle contains 'a', 'b', 'c'
        flat = [n for c in cycles for n in c]
        assert 'a' in flat

    def test_transitive_deps(self):
        g = self._graph()
        t = g.transitive_deps('etd.pipeline')
        assert 'etd.pick' in t
        assert 'etd.inspect' in t
        assert 'etd.gripper' in t
        assert 'etd.pipeline' not in t

    def test_transitive_deps_leaf(self):
        g = self._graph()
        assert g.transitive_deps('etd.gripper') == []

    def test_transitive_deps_cycle_returns_empty(self):
        g = DependencyGraph()
        g.add_skill('a', ['b'])
        g.add_skill('b', ['a'])
        assert g.transitive_deps('a') == []

    def test_missing_none_available(self):
        g = self._graph()
        missing = g.missing('etd.pipeline', set())
        assert set(missing) == {'etd.pick', 'etd.inspect'}

    def test_missing_all_available(self):
        g = self._graph()
        missing = g.missing('etd.pipeline', {'etd.pick', 'etd.inspect'})
        assert missing == []

    def test_missing_partial(self):
        g = self._graph()
        missing = g.missing('etd.pipeline', {'etd.pick'})
        assert 'etd.inspect' in missing
        assert 'etd.pick' not in missing


# ── DependencyResolver ────────────────────────────────────────────────────────

class TestDependencyResolver:
    def _resolver(self) -> DependencyResolver:
        return DependencyResolver({
            'etd.pipeline': [
                SkillDependency('etd.pick'),
                SkillDependency('etd.inspect', optional=True),
            ],
            'etd.pick': [SkillDependency('etd.gripper')],
            'etd.inspect': [],
            'etd.gripper': [],
        })

    def test_install_order_leaf(self):
        r = self._resolver()
        assert r.install_order('etd.gripper') == ['etd.gripper']

    def test_install_order_deps_first(self):
        r = self._resolver()
        order = r.install_order('etd.pipeline')
        assert order[-1] == 'etd.pipeline'
        assert order.index('etd.gripper') < order.index('etd.pick')

    def test_check_satisfied_all_present(self):
        r = self._resolver()
        ok, missing = r.check_satisfied(
            'etd.pipeline', {'etd.pick', 'etd.inspect'}
        )
        assert ok is True
        assert missing == []

    def test_check_satisfied_missing_required(self):
        r = self._resolver()
        ok, missing = r.check_satisfied('etd.pipeline', {'etd.inspect'})
        assert ok is False
        assert 'etd.pick' in missing

    def test_check_optional_not_in_missing(self):
        # etd.inspect is optional → not in missing even if absent
        r = self._resolver()
        ok, missing = r.check_satisfied('etd.pipeline', {'etd.pick'})
        assert ok is True
        assert 'etd.inspect' not in missing

    def test_check_unknown_skill_satisfied(self):
        r = self._resolver()
        ok, missing = r.check_satisfied('ghost.skill', set())
        assert ok is True
        assert missing == []

    def test_dependency_tree_structure(self):
        r = self._resolver()
        tree = r.dependency_tree('etd.pipeline')
        assert tree['skill_id'] == 'etd.pipeline'
        assert isinstance(tree['deps'], list)
        assert len(tree['deps']) == 2

    def test_dependency_tree_nested(self):
        r = self._resolver()
        tree = r.dependency_tree('etd.pipeline')
        pick_node = next(d for d in tree['deps']
                         if d['skill_id'] == 'etd.pick')
        assert any(d['skill_id'] == 'etd.gripper'
                   for d in pick_node['deps'])

    def test_dependency_tree_cycle_flagged(self):
        r = DependencyResolver({
            'a': [SkillDependency('b')],
            'b': [SkillDependency('a')],
        })
        tree = r.dependency_tree('a')
        # The cycle back to 'a' should be marked
        def _find_cycle(node):
            if node.get('cycle'):
                return True
            return any(_find_cycle(d) for d in node.get('deps', []))
        assert _find_cycle(tree)

    def test_from_dict(self):
        r = DependencyResolver.from_dict({
            'etd.pipeline': [
                {'skill_id': 'etd.pick', 'version_constraint': '>=0.1.0'},
            ]
        })
        order = r.install_order('etd.pipeline')
        assert 'etd.pick' in order

    def test_cycles_clean_graph(self):
        r = self._resolver()
        assert r.cycles() == []

    def test_cycles_detected(self):
        r = DependencyResolver({
            'a': [SkillDependency('b')],
            'b': [SkillDependency('a')],
        })
        assert len(r.cycles()) >= 1


# ── DependencyStore ───────────────────────────────────────────────────────────

class TestDependencyStore:
    @pytest.fixture()
    def store(self, tmp_path) -> DependencyStore:
        return DependencyStore(tmp_path / 'deps')

    def test_empty(self, store):
        assert store.skill_count == 0

    def test_register_and_get(self, store):
        store.register('etd.pick', [SkillDependency('etd.gripper')])
        deps = store.get('etd.pick')
        assert deps is not None
        assert deps[0].skill_id == 'etd.gripper'

    def test_get_unknown_none(self, store):
        assert store.get('ghost') is None

    def test_list_skills(self, store):
        store.register('etd.a', [])
        store.register('etd.b', [])
        assert set(store.list_skills()) == {'etd.a', 'etd.b'}

    def test_remove_existing(self, store):
        store.register('etd.pick', [])
        assert store.remove('etd.pick') is True
        assert store.get('etd.pick') is None

    def test_remove_unknown_false(self, store):
        assert store.remove('ghost') is False

    def test_update_replaces(self, store):
        store.register('etd.pick', [SkillDependency('etd.a')])
        store.register('etd.pick', [SkillDependency('etd.b')])
        assert store.get('etd.pick')[0].skill_id == 'etd.b'

    def test_persists(self, tmp_path):
        s1 = DependencyStore(tmp_path / 'deps')
        s1.register('etd.pick', [SkillDependency('etd.gripper', '>=0.1.0')])
        s2 = DependencyStore(tmp_path / 'deps')
        deps = s2.get('etd.pick')
        assert deps[0].version_constraint == '>=0.1.0'

    def test_creates_dir(self, tmp_path):
        s = DependencyStore(tmp_path / 'a' / 'b')
        s.register('x', [])
        assert (tmp_path / 'a' / 'b' / 'deps.json').exists()

    def test_corrupt_file_loads_empty(self, tmp_path):
        (tmp_path / 'deps.json').write_text('bad')
        s = DependencyStore(tmp_path)
        assert s.skill_count == 0

    def test_resolver_method(self, store):
        store.register('etd.pipeline', [SkillDependency('etd.pick')])
        r = store.resolver()
        order = r.install_order('etd.pipeline')
        assert order[-1] == 'etd.pipeline'


# ── REST API /deps ────────────────────────────────────────────────────────────

import api.dependency as _dep_mod


@pytest.fixture(autouse=True)
def patch_deps_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_dep_mod, '_DEPS_DIR', tmp_path / 'deps')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _reg(api_client, skill_id='etd.pipeline', deps=None):
    if deps is None:
        deps = [{'skill_id': 'etd.pick'}, {'skill_id': 'etd.inspect'}]
    return api_client.post('/deps/skills',
                           json={'skill_id': skill_id, 'deps': deps})


class TestDepsApiRegister:
    def test_register_201(self, api_client):
        r = _reg(api_client)
        assert r.status_code == 201

    def test_register_has_skill_id(self, api_client):
        data = _reg(api_client).json()
        assert data['skill_id'] == 'etd.pipeline'
        assert len(data['deps']) == 2


class TestDepsApiList:
    def test_list_200(self, api_client):
        assert api_client.get('/deps/skills').status_code == 200

    def test_list_empty(self, api_client):
        data = api_client.get('/deps/skills').json()
        assert data['count'] == 0

    def test_list_after_register(self, api_client):
        _reg(api_client)
        data = api_client.get('/deps/skills').json()
        assert data['count'] == 1


class TestDepsApiGet:
    def test_get_found(self, api_client):
        _reg(api_client)
        r = api_client.get('/deps/skills/etd.pipeline')
        assert r.status_code == 200
        assert r.json()['skill_id'] == 'etd.pipeline'

    def test_get_404(self, api_client):
        assert api_client.get('/deps/skills/ghost').status_code == 404


class TestDepsApiDelete:
    def test_delete_200(self, api_client):
        _reg(api_client)
        r = api_client.delete('/deps/skills/etd.pipeline')
        assert r.status_code == 200

    def test_delete_404(self, api_client):
        assert api_client.delete('/deps/skills/ghost').status_code == 404


class TestDepsApiOrder:
    def test_order_no_deps(self, api_client):
        _reg(api_client, 'etd.leaf', [])
        data = api_client.get('/deps/order/etd.leaf').json()
        assert data['install_order'] == ['etd.leaf']
        assert data['dep_count'] == 0

    def test_order_with_deps(self, api_client):
        _reg(api_client, 'etd.pick', [])
        _reg(api_client, 'etd.inspect', [])
        _reg(api_client, 'etd.pipeline',
             [{'skill_id': 'etd.pick'}, {'skill_id': 'etd.inspect'}])
        data = api_client.get('/deps/order/etd.pipeline').json()
        order = data['install_order']
        assert order[-1] == 'etd.pipeline'
        assert 'etd.pick' in order

    def test_order_cycle_409(self, api_client):
        _reg(api_client, 'a', [{'skill_id': 'b'}])
        _reg(api_client, 'b', [{'skill_id': 'a'}])
        r = api_client.get('/deps/order/a')
        assert r.status_code == 409


class TestDepsApiTree:
    def test_tree_200(self, api_client):
        _reg(api_client)
        r = api_client.get('/deps/tree/etd.pipeline')
        assert r.status_code == 200

    def test_tree_structure(self, api_client):
        _reg(api_client)
        data = api_client.get('/deps/tree/etd.pipeline').json()
        assert data['skill_id'] == 'etd.pipeline'
        assert isinstance(data['deps'], list)


class TestDepsApiCheck:
    def test_check_satisfied(self, api_client):
        _reg(api_client, 'etd.pipeline',
             [{'skill_id': 'etd.pick'}])
        data = api_client.post('/deps/check', json={
            'skill_id': 'etd.pipeline',
            'available': ['etd.pick'],
        }).json()
        assert data['satisfied'] is True
        assert data['missing'] == []

    def test_check_missing(self, api_client):
        _reg(api_client, 'etd.pipeline', [{'skill_id': 'etd.pick'}])
        data = api_client.post('/deps/check', json={
            'skill_id': 'etd.pipeline',
            'available': [],
        }).json()
        assert data['satisfied'] is False
        assert 'etd.pick' in data['missing']


class TestDepsApiCycles:
    def test_no_cycles(self, api_client):
        _reg(api_client)
        data = api_client.get('/deps/cycles').json()
        assert data['cycle_count'] == 0

    def test_cycle_detected(self, api_client):
        _reg(api_client, 'a', [{'skill_id': 'b'}])
        _reg(api_client, 'b', [{'skill_id': 'a'}])
        data = api_client.get('/deps/cycles').json()
        assert data['cycle_count'] >= 1
