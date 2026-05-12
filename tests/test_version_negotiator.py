"""Tests for semver version negotiator."""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.version_negotiator import (
    best_version,
    parse_version,
    satisfies,
    sort_versions,
)


# ── parse_version ─────────────────────────────────────────────────────────────

class TestParseVersion:
    def test_semver_three_parts(self):
        assert parse_version('1.2.3') == (1, 2, 3)

    def test_semver_two_parts(self):
        assert parse_version('1.2') == (1, 2, 0)

    def test_semver_one_part(self):
        assert parse_version('3') == (3, 0, 0)

    def test_invalid_returns_zeros(self):
        assert parse_version('not.a.version') == (0, 0, 0)

    def test_empty_returns_zeros(self):
        assert parse_version('') == (0, 0, 0)

    def test_leading_whitespace(self):
        assert parse_version('  1.2.3') == (1, 2, 3)


# ── satisfies — single constraints ───────────────────────────────────────────

class TestSatisfiesSingle:
    def test_ge_satisfied(self):
        assert satisfies('1.0.0', '>=0.1.0') is True

    def test_ge_equal(self):
        assert satisfies('0.1.0', '>=0.1.0') is True

    def test_ge_not_satisfied(self):
        assert satisfies('0.0.9', '>=0.1.0') is False

    def test_gt_satisfied(self):
        assert satisfies('1.0.0', '>0.9.0') is True

    def test_gt_not_satisfied_equal(self):
        assert satisfies('0.9.0', '>0.9.0') is False

    def test_le_satisfied(self):
        assert satisfies('0.5.0', '<=1.0.0') is True

    def test_le_equal(self):
        assert satisfies('1.0.0', '<=1.0.0') is True

    def test_le_not_satisfied(self):
        assert satisfies('1.0.1', '<=1.0.0') is False

    def test_lt_satisfied(self):
        assert satisfies('0.9.9', '<1.0.0') is True

    def test_lt_not_satisfied_equal(self):
        assert satisfies('1.0.0', '<1.0.0') is False

    def test_eq_satisfied(self):
        assert satisfies('1.2.3', '==1.2.3') is True

    def test_eq_not_satisfied(self):
        assert satisfies('1.2.4', '==1.2.3') is False

    def test_ne_satisfied(self):
        assert satisfies('1.0.0', '!=0.9.0') is True

    def test_ne_not_satisfied(self):
        assert satisfies('0.9.0', '!=0.9.0') is False

    def test_empty_constraint_always_true(self):
        assert satisfies('anything', '') is True

    def test_wildcard_always_true(self):
        assert satisfies('1.0.0', '*') is True

    def test_bare_version_acts_as_eq(self):
        assert satisfies('1.2.3', '1.2.3') is True
        assert satisfies('1.2.4', '1.2.3') is False


class TestSatisfiesConjunction:
    def test_range_satisfied(self):
        assert satisfies('0.5.0', '>=0.1.0, <1.0.0') is True

    def test_range_upper_fail(self):
        assert satisfies('1.0.0', '>=0.1.0, <1.0.0') is False

    def test_range_lower_fail(self):
        assert satisfies('0.0.9', '>=0.1.0, <1.0.0') is False

    def test_three_parts(self):
        assert satisfies('0.5.1', '>=0.5.0, <=0.5.1, !=0.5.0') is True


class TestSatisfiesCompatRelease:
    def test_tilde_minor(self):
        # ~=1.2 → >=1.2.0, <2.0.0
        assert satisfies('1.9.9', '~=1.2') is True
        assert satisfies('2.0.0', '~=1.2') is False
        assert satisfies('1.1.9', '~=1.2') is False

    def test_tilde_patch(self):
        # ~=1.2.3 → >=1.2.3, <1.3.0
        assert satisfies('1.2.5', '~=1.2.3') is True
        assert satisfies('1.3.0', '~=1.2.3') is False
        assert satisfies('1.2.2', '~=1.2.3') is False


# ── best_version ──────────────────────────────────────────────────────────────

@dataclass
class _FakeEntry:
    skillId: str
    version: str
    runtimeConstraint: str = ''


class TestBestVersion:
    def test_single_entry_no_constraint(self):
        entries = [_FakeEntry('s', '1.0.0')]
        result = best_version(entries, '0.5.0')
        assert result is not None
        assert result.version == '1.0.0'

    def test_picks_highest_compatible(self):
        entries = [
            _FakeEntry('s', '0.3.0', '>=0.1.0'),
            _FakeEntry('s', '1.0.0', '>=0.5.0'),
            _FakeEntry('s', '2.0.0', '>=1.0.0'),
        ]
        result = best_version(entries, '0.7.0')
        assert result.version == '1.0.0'

    def test_newest_when_all_compatible(self):
        entries = [
            _FakeEntry('s', '1.0.0', '>=0.1.0'),
            _FakeEntry('s', '2.0.0', '>=0.1.0'),
            _FakeEntry('s', '1.5.0', '>=0.1.0'),
        ]
        result = best_version(entries, '9.9.9')
        assert result.version == '2.0.0'

    def test_returns_none_when_none_compatible(self):
        entries = [_FakeEntry('s', '1.0.0', '>=2.0.0')]
        assert best_version(entries, '0.5.0') is None

    def test_empty_entries(self):
        assert best_version([], '1.0.0') is None

    def test_constraint_from_entry_attribute(self):
        entries = [
            _FakeEntry('s', '0.5.0', '>=0.5.0, <1.0.0'),
            _FakeEntry('s', '1.0.0', '>=1.0.0'),
        ]
        result = best_version(entries, '0.8.0')
        assert result.version == '0.5.0'

    def test_no_constraint_attribute_always_compatible(self):
        @dataclass
        class _NoConstraint:
            version: str
        entries = [_NoConstraint('2.0.0'), _NoConstraint('1.0.0')]
        result = best_version(entries, '0.1.0')
        assert result.version == '2.0.0'


# ── sort_versions ─────────────────────────────────────────────────────────────

class TestSortVersions:
    def test_descending_default(self):
        entries = [_FakeEntry('s', '1.0.0'), _FakeEntry('s', '2.0.0'), _FakeEntry('s', '0.5.0')]
        sorted_ = sort_versions(entries)
        assert [e.version for e in sorted_] == ['2.0.0', '1.0.0', '0.5.0']

    def test_ascending(self):
        entries = [_FakeEntry('s', '1.0.0'), _FakeEntry('s', '2.0.0'), _FakeEntry('s', '0.5.0')]
        sorted_ = sort_versions(entries, descending=False)
        assert [e.version for e in sorted_] == ['0.5.0', '1.0.0', '2.0.0']


# ── SkillStore integration ────────────────────────────────────────────────────

class TestSkillStoreVersionNegotiation:
    def test_get_versions_returns_entries_for_skill(self):
        from marketplace.skill_store import SkillStore
        store = SkillStore(ROOT)
        versions = store.get_versions('etd.pickplace.basic')
        assert len(versions) >= 1
        assert all(e.skillId == 'etd.pickplace.basic' for e in versions)

    def test_get_entry_returns_for_any_runtime(self):
        from marketplace.skill_store import SkillStore
        store = SkillStore(ROOT)
        entry = store.get_entry('etd.pickplace.basic', '0.5.0')
        assert entry is not None
        assert entry.skillId == 'etd.pickplace.basic'

    def test_get_entry_returns_none_for_unknown_skill(self):
        from marketplace.skill_store import SkillStore
        store = SkillStore(ROOT)
        assert store.get_entry('etd.nonexistent', '0.5.0') is None

    def test_find_skill_returns_raw_dict(self):
        from marketplace.skill_store import SkillStore
        store = SkillStore(ROOT)
        raw = store.find_skill('etd.pickplace.basic')
        assert isinstance(raw, dict)
        assert raw['skillId'] == 'etd.pickplace.basic'


# ── CLI versions command ──────────────────────────────────────────────────────

class TestVersionsCLI:
    def test_versions_known_skill(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['versions', 'etd.pickplace.basic'])
        assert result.exit_code == 0
        assert 'etd.pickplace.basic' in result.output

    def test_versions_unknown_skill_exits_one(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['versions', 'etd.nonexistent.skill'])
        assert result.exit_code == 1
