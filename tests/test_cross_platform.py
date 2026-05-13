"""Tests for marketplace.cross_platform — HumanoidRegistry and compat checks."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketplace.cross_platform import (
    BUILTIN_PLATFORMS,
    HumanoidPlatform,
    HumanoidRegistry,
    PlatformCompatResult,
    load_skill_info,
)

ROOT = Path(__file__).parent.parent
ATLAS_PKG = ROOT / 'examples' / 'etd.atlas.humanoid_walkfetch'
PICKPLACE_PKG = ROOT / 'examples' / 'etd.pickplace.basic'
MOBED_PKG = ROOT / 'examples' / 'etd.hyundai.mobed_transport'
INSPECT_PKG = ROOT / 'examples' / 'etd.inspect.vision'
COBOT_PKG = ROOT / 'examples' / 'etd.cobot.safeassist'
WIA_PKG = ROOT / 'examples' / 'etd.hyundai.wia_welding'


# ── HumanoidPlatform ─────────────────────────────────────────────────────────

class TestHumanoidPlatform:
    def _make(self) -> HumanoidPlatform:
        return HumanoidPlatform(
            platform_id='test_bot',
            name='Test Bot',
            robot_class='humanoid',
            families=frozenset({'humanoid', 'manipulator'}),
            topic_namespace='/test',
            supported_primitives=frozenset({'walk', 'grasp'}),
            capability_flags=frozenset({'bipedal_locomotion'}),
        )

    def test_supports_family_true(self):
        p = self._make()
        assert p.supports_family('humanoid') is True

    def test_supports_family_false(self):
        p = self._make()
        assert p.supports_family('transport') is False

    def test_supports_primitive_true(self):
        p = self._make()
        assert p.supports_primitive('walk') is True

    def test_supports_primitive_false(self):
        p = self._make()
        assert p.supports_primitive('weld') is False

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        assert 'platform_id' in d
        assert 'families' in d
        assert 'supported_primitives' in d
        assert 'capability_flags' in d

    def test_to_dict_families_sorted(self):
        d = self._make().to_dict()
        assert d['families'] == sorted(d['families'])


# ── BUILTIN_PLATFORMS ─────────────────────────────────────────────────────────

class TestBuiltinPlatforms:
    def test_six_builtin_platforms(self):
        assert len(BUILTIN_PLATFORMS) == 6

    def test_atlas_is_humanoid(self):
        atlas = next(p for p in BUILTIN_PLATFORMS if p.platform_id == 'atlas')
        assert 'humanoid' in atlas.families

    def test_hyundai_mobed_is_transport(self):
        mobed = next(p for p in BUILTIN_PLATFORMS if p.platform_id == 'hyundai_mobed')
        assert 'transport' in mobed.families

    def test_hyundai_wia_supports_weld(self):
        wia = next(p for p in BUILTIN_PLATFORMS if p.platform_id == 'hyundai_wia')
        assert 'weld' in wia.families

    def test_hyundai_mex_is_exoskeleton(self):
        mex = next(p for p in BUILTIN_PLATFORMS if p.platform_id == 'hyundai_mex')
        assert mex.robot_class == 'exoskeleton'

    def test_all_platforms_have_namespace(self):
        for p in BUILTIN_PLATFORMS:
            assert p.topic_namespace.startswith('/')

    def test_all_platforms_have_primitives(self):
        for p in BUILTIN_PLATFORMS:
            assert len(p.supported_primitives) > 0


# ── load_skill_info ───────────────────────────────────────────────────────────

class TestLoadSkillInfo:
    def test_loads_atlas_skill(self):
        info = load_skill_info(ATLAS_PKG)
        assert info['skillId'] == 'etd.atlas.humanoid_walkfetch'
        assert info['family'] == 'humanoid'
        assert len(info['primitiveOrder']) == 9

    def test_loads_mobed_skill(self):
        info = load_skill_info(MOBED_PKG)
        assert info['family'] == 'transport'

    def test_missing_skill_json_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match='skill.json'):
            load_skill_info(tmp_path / 'no_such_pkg')

    def test_accepts_string_path(self):
        info = load_skill_info(str(ATLAS_PKG))
        assert 'skillId' in info


# ── HumanoidRegistry ──────────────────────────────────────────────────────────

class TestHumanoidRegistry:
    def test_default_platform_count(self):
        reg = HumanoidRegistry()
        assert reg.platform_count == 6

    def test_get_known_platform(self):
        reg = HumanoidRegistry()
        p = reg.get('atlas')
        assert p is not None
        assert p.platform_id == 'atlas'

    def test_get_unknown_platform_none(self):
        reg = HumanoidRegistry()
        assert reg.get('nonexistent') is None

    def test_register_adds_platform(self):
        reg = HumanoidRegistry()
        custom = HumanoidPlatform(
            platform_id='custom_bot',
            name='Custom',
            robot_class='humanoid',
            families=frozenset({'humanoid'}),
            topic_namespace='/custom',
            supported_primitives=frozenset({'walk'}),
            capability_flags=frozenset(),
        )
        reg.register(custom)
        assert reg.platform_count == 7
        assert reg.get('custom_bot') is not None

    def test_register_replaces_existing(self):
        reg = HumanoidRegistry()
        original = reg.get('atlas')
        replacement = HumanoidPlatform(
            platform_id='atlas',
            name='Atlas Replacement',
            robot_class='humanoid',
            families=frozenset({'humanoid'}),
            topic_namespace='/atlas_new',
            supported_primitives=frozenset(),
            capability_flags=frozenset(),
        )
        reg.register(replacement)
        assert reg.platform_count == 6
        assert reg.get('atlas').name == 'Atlas Replacement'

    def test_unregister_removes_platform(self):
        reg = HumanoidRegistry()
        reg.unregister('atlas')
        assert reg.platform_count == 5
        assert reg.get('atlas') is None

    def test_unregister_nonexistent_is_silent(self):
        reg = HumanoidRegistry()
        reg.unregister('ghost')
        assert reg.platform_count == 6

    def test_list_platforms_returns_all(self):
        reg = HumanoidRegistry()
        platforms = reg.list_platforms()
        assert len(platforms) == 6
        ids = {p.platform_id for p in platforms}
        assert 'atlas' in ids
        assert 'unitree_g1' in ids


# ── check_compat ──────────────────────────────────────────────────────────────

class TestCheckCompat:
    def _reg(self):
        return HumanoidRegistry()

    def test_same_platform_is_compatible(self):
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='atlas')
        assert result.compatible is True
        assert 'no adaptation' in result.adaptation_notes[0]

    def test_atlas_to_unitree_g1_compatible(self):
        """Atlas humanoid_walkfetch should be portable to Unitree G1 (both humanoids)."""
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_g1')
        assert result.compatible is True

    def test_atlas_to_unitree_h1_incompatible(self):
        """H1 lacks dexterous hands → can't satisfy grasp primitives."""
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_h1')
        assert result.compatible is False
        assert len(result.missing_primitives) > 0

    def test_atlas_to_mobed_family_mismatch(self):
        """MobED supports transport only — humanoid family not supported."""
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='hyundai_mobed')
        assert result.compatible is False
        assert any('family' in w.lower() for w in result.warnings)

    def test_mobed_skill_to_mobed_compatible(self):
        reg = self._reg()
        info = load_skill_info(MOBED_PKG)
        result = reg.check_compat(info, source='hyundai_mobed', target='hyundai_mobed')
        assert result.compatible is True

    def test_topic_remappings_generated(self):
        """Different namespaces → remappings dict populated."""
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_g1')
        assert len(result.topic_remappings) > 0
        for src_topic, tgt_topic in result.topic_remappings.items():
            assert src_topic.startswith('/atlas/')
            assert tgt_topic.startswith('/unitree/g1/')

    def test_unknown_target_returns_incompatible(self):
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='ghost_bot')
        assert result.compatible is False
        assert any('ghost_bot' in w for w in result.warnings)

    def test_unknown_source_warns_but_checks_target(self):
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='unknown_src', target='unitree_g1')
        assert any('source platform' in w for w in result.warnings)

    def test_result_fields_populated(self):
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_h1')
        assert result.skill_id == 'etd.atlas.humanoid_walkfetch'
        assert result.source_platform == 'atlas'
        assert result.target_platform == 'unitree_h1'
        assert isinstance(result.missing_primitives, list)
        assert isinstance(result.warnings, list)

    def test_pickplace_atlas_to_unitree_g1(self):
        """pickplace.basic's primitives are in G1's set."""
        reg = self._reg()
        info = load_skill_info(PICKPLACE_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_g1')
        assert result.compatible is True

    def test_cobot_wia_compatible(self):
        """cobot.safeassist primitives are in WIA's set."""
        reg = self._reg()
        info = load_skill_info(COBOT_PKG)
        result = reg.check_compat(info, source='hyundai_wia', target='hyundai_wia')
        assert result.compatible is True

    def test_missing_capability_flags_reported(self):
        """Unitree H1 lacks 'dexterous_manipulation' compared to Atlas."""
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_h1')
        assert 'dexterous_manipulation' in result.missing_capability_flags

    def test_inspect_vision_atlas_to_unitree_g1(self):
        reg = self._reg()
        info = load_skill_info(INSPECT_PKG)
        result = reg.check_compat(info, source='atlas', target='unitree_g1')
        assert result.compatible is True

    def test_no_topic_remappings_same_platform(self):
        reg = self._reg()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, source='atlas', target='atlas')
        assert result.topic_remappings == {}


# ── PlatformCompatResult.summary / to_dict ────────────────────────────────────

class TestPlatformCompatResult:
    def test_summary_compatible(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, 'atlas', 'unitree_g1')
        s = result.summary()
        assert 'COMPATIBLE' in s
        assert result.skill_id in s

    def test_summary_incompatible_shows_missing(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, 'atlas', 'unitree_h1')
        s = result.summary()
        assert 'INCOMPATIBLE' in s
        assert len(result.missing_primitives) > 0

    def test_to_dict_keys(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, 'atlas', 'unitree_g1')
        d = result.to_dict()
        for key in ('skill_id', 'source_platform', 'target_platform',
                    'compatible', 'missing_primitives', 'topic_remappings',
                    'missing_capability_flags', 'warnings', 'adaptation_notes'):
            assert key in d

    def test_to_dict_compatible_true(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, 'atlas', 'unitree_g1')
        assert result.to_dict()['compatible'] is True

    def test_to_dict_compatible_false(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        result = reg.check_compat(info, 'atlas', 'unitree_h1')
        assert result.to_dict()['compatible'] is False


# ── compat_matrix ─────────────────────────────────────────────────────────────

class TestCompatMatrix:
    def test_matrix_without_skill_info(self):
        reg = HumanoidRegistry()
        rows = reg.compat_matrix()
        # 6 platforms → 6*5 = 30 pairs
        assert len(rows) == 30

    def test_matrix_with_skill_info(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        rows = reg.compat_matrix(skill_info=info)
        assert len(rows) == 30
        for row in rows:
            assert 'compatible' in row
            assert 'missing_primitives' in row

    def test_matrix_family_filter(self):
        reg = HumanoidRegistry()
        rows = reg.compat_matrix(families={'humanoid'})
        # Only Atlas, Unitree G1, Unitree H1 support humanoid → 3*2 = 6 pairs
        assert len(rows) == 6

    def test_matrix_transport_filter(self):
        reg = HumanoidRegistry()
        rows = reg.compat_matrix(families={'transport'})
        # Only MobED supports transport → 0 pairs (single platform)
        assert len(rows) == 0

    def test_matrix_row_structure(self):
        reg = HumanoidRegistry()
        rows = reg.compat_matrix()
        for row in rows:
            assert 'source' in row
            assert 'target' in row
            assert 'compatible' in row

    def test_matrix_no_self_pairs(self):
        reg = HumanoidRegistry()
        rows = reg.compat_matrix()
        for row in rows:
            assert row['source'] != row['target']


# ── render_matrix_ascii ───────────────────────────────────────────────────────

class TestRenderMatrixAscii:
    def test_renders_without_error(self):
        reg = HumanoidRegistry()
        out = reg.render_matrix_ascii()
        assert len(out) > 0

    def test_contains_platform_ids(self):
        reg = HumanoidRegistry()
        out = reg.render_matrix_ascii()
        assert 'atlas' in out
        assert 'unitree_g1' in out

    def test_contains_check_marks_with_skill(self):
        reg = HumanoidRegistry()
        info = load_skill_info(ATLAS_PKG)
        out = reg.render_matrix_ascii(skill_info=info)
        assert '✓' in out or '✗' in out

    def test_self_diagonal_is_dot(self):
        reg = HumanoidRegistry()
        out = reg.render_matrix_ascii()
        assert '·' in out


# ── CLI: platform list ────────────────────────────────────────────────────────

class TestCLIPlatformList:
    def test_list_shows_platforms(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['platform', 'list'])
        assert result.exit_code == 0
        assert 'atlas' in result.output
        assert 'unitree_g1' in result.output

    def test_list_json(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['platform', 'list', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 6
        ids = {p['platform_id'] for p in data}
        assert 'atlas' in ids


# ── CLI: platform check ───────────────────────────────────────────────────────

class TestCLIPlatformCheck:
    def test_check_compatible(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'platform', 'check', str(ATLAS_PKG),
            '--source', 'atlas', '--target', 'unitree_g1',
        ])
        assert result.exit_code == 0
        assert 'COMPATIBLE' in result.output

    def test_check_incompatible(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'platform', 'check', str(ATLAS_PKG),
            '--source', 'atlas', '--target', 'unitree_h1',
        ])
        assert result.exit_code == 1
        assert 'INCOMPATIBLE' in result.output

    def test_check_json(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'platform', 'check', str(ATLAS_PKG),
            '--source', 'atlas', '--target', 'unitree_g1', '--json',
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['compatible'] is True
        assert 'topic_remappings' in data

    def test_check_missing_package(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'platform', 'check', str(tmp_path / 'nope'),
            '--source', 'atlas', '--target', 'unitree_g1',
        ])
        assert result.exit_code == 1


# ── CLI: platform matrix ──────────────────────────────────────────────────────

class TestCLIPlatformMatrix:
    def test_matrix_ascii(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['platform', 'matrix'])
        assert result.exit_code == 0
        assert 'atlas' in result.output

    def test_matrix_json(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['platform', 'matrix', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 30

    def test_matrix_with_skill(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            'platform', 'matrix', '--skill', str(ATLAS_PKG), '--json',
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all('missing_primitives' in row for row in data)

    def test_matrix_family_filter(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['platform', 'matrix', '--family', 'humanoid', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 6  # 3 humanoid platforms → 3*2 pairs
