"""Tests for marketplace.composer — SkillComposer, composed skill execution."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from marketplace.composer import (
    ComposedSkill,
    ComposedSkillResult,
    SafetyContext,
    SkillComposer,
    SkillStep,
    StepResult,
    load_composed_skill,
    mock_executor,
)

ROOT = Path(__file__).parent.parent
EXAMPLE_COMPOSED = ROOT / 'examples' / 'etd.composed.fetch_inspect_place'


# ── SkillStep ─────────────────────────────────────────────────────────────────

class TestSkillStep:
    def test_defaults(self):
        s = SkillStep(skill_id='etd.foo')
        assert s.version_constraint == ''
        assert s.on_failure == 'abort'
        assert s.retry_count == 0
        assert s.params == {}

    def test_invalid_on_failure_raises(self):
        with pytest.raises(ValueError, match='on_failure'):
            SkillStep(skill_id='x', on_failure='explode')

    def test_negative_retry_count_raises(self):
        with pytest.raises(ValueError, match='retry_count'):
            SkillStep(skill_id='x', retry_count=-1)

    def test_from_dict_full(self):
        d = {
            'skillId': 'etd.foo',
            'versionConstraint': '>=1.0.0',
            'onFailure': 'retry',
            'retryCount': 3,
            'params': {'speed': 0.5},
        }
        s = SkillStep.from_dict(d)
        assert s.skill_id == 'etd.foo'
        assert s.version_constraint == '>=1.0.0'
        assert s.on_failure == 'retry'
        assert s.retry_count == 3
        assert s.params == {'speed': 0.5}

    def test_from_dict_defaults(self):
        s = SkillStep.from_dict({'skillId': 'etd.bar'})
        assert s.version_constraint == ''
        assert s.on_failure == 'abort'
        assert s.retry_count == 0

    def test_to_dict_roundtrip(self):
        s = SkillStep(skill_id='etd.x', version_constraint='>=0.1', on_failure='skip', retry_count=1,
                      params={'k': 'v'})
        d = s.to_dict()
        s2 = SkillStep.from_dict(d)
        assert s2.skill_id == s.skill_id
        assert s2.version_constraint == s.version_constraint
        assert s2.on_failure == s.on_failure
        assert s2.retry_count == s.retry_count
        assert s2.params == s.params

    def test_all_valid_on_failure_values(self):
        for v in ('abort', 'skip', 'retry'):
            s = SkillStep(skill_id='etd.test', on_failure=v)
            assert s.on_failure == v


# ── ComposedSkill ─────────────────────────────────────────────────────────────

class TestComposedSkill:
    def _make(self) -> ComposedSkill:
        return ComposedSkill(
            skill_id='etd.composed.test',
            version='1.0.0',
            name='Test',
            description='desc',
            steps=[SkillStep(skill_id='etd.pickplace.basic')],
        )

    def test_from_dict(self):
        d = {
            'skillId': 'etd.composed.abc',
            'version': '2.0.0',
            'name': 'ABC',
            'description': 'test',
            'steps': [
                {'skillId': 'etd.foo', 'onFailure': 'skip'},
                {'skillId': 'etd.bar'},
            ],
        }
        c = ComposedSkill.from_dict(d)
        assert c.skill_id == 'etd.composed.abc'
        assert c.version == '2.0.0'
        assert len(c.steps) == 2
        assert c.steps[0].on_failure == 'skip'

    def test_from_dict_defaults(self):
        c = ComposedSkill.from_dict({'skillId': 'etd.x'})
        assert c.version == '0.0.0'
        assert c.name == 'etd.x'
        assert c.description == ''
        assert c.steps == []

    def test_to_dict_roundtrip(self):
        c = self._make()
        c2 = ComposedSkill.from_dict(c.to_dict())
        assert c2.skill_id == c.skill_id
        assert c2.version == c.version
        assert len(c2.steps) == len(c.steps)


# ── SafetyContext ─────────────────────────────────────────────────────────────

class TestSafetyContext:
    def test_safe_initially(self):
        ctx = SafetyContext()
        assert ctx.safe is True
        assert ctx.aborted is False
        assert ctx.violations == []

    def test_record_violation_marks_unsafe(self):
        ctx = SafetyContext()
        ctx.record_violation('balance_loss')
        assert ctx.safe is False
        assert 'balance_loss' in ctx.violations

    def test_abort_marks_unsafe(self):
        ctx = SafetyContext()
        ctx.abort('torque_exceeded')
        assert ctx.safe is False
        assert ctx.aborted is True
        assert ctx.abort_reason == 'torque_exceeded'

    def test_multiple_violations(self):
        ctx = SafetyContext()
        ctx.record_violation('v1')
        ctx.record_violation('v2')
        assert len(ctx.violations) == 2


# ── StepResult ────────────────────────────────────────────────────────────────

class TestStepResult:
    def test_succeeded_true(self):
        r = StepResult(step_index=0, skill_id='etd.x', status='success')
        assert r.succeeded is True

    def test_succeeded_false(self):
        for s in ('failed', 'skipped', 'aborted', 'retried'):
            r = StepResult(step_index=0, skill_id='etd.x', status=s)
            assert r.succeeded is False


# ── mock_executor ─────────────────────────────────────────────────────────────

class TestMockExecutor:
    def test_succeeds_on_safe_context(self):
        step = SkillStep(skill_id='etd.x')
        ctx = SafetyContext()
        ok, err = mock_executor(step, ctx, {})
        assert ok is True
        assert err is None

    def test_fails_on_aborted_context(self):
        step = SkillStep(skill_id='etd.x')
        ctx = SafetyContext()
        ctx.abort('hard_stop')
        ok, err = mock_executor(step, ctx, {})
        assert ok is False
        assert err is not None

    def test_fails_on_violated_context(self):
        step = SkillStep(skill_id='etd.x')
        ctx = SafetyContext()
        ctx.record_violation('balance_loss')
        ok, err = mock_executor(step, ctx, {})
        assert ok is False


# ── SkillComposer.validate ────────────────────────────────────────────────────

class TestSkillComposerValidate:
    def _composer(self):
        return SkillComposer()

    def test_valid_composed_skill_no_issues(self):
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[SkillStep(skill_id='etd.foo')])
        issues = self._composer().validate(c)
        assert issues == []

    def test_no_steps_is_an_issue(self):
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[])
        issues = self._composer().validate(c)
        assert any('no steps' in i for i in issues)

    def test_self_reference_is_an_issue(self):
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[SkillStep(skill_id='etd.composed.x')])
        issues = self._composer().validate(c)
        assert any('cycle' in i for i in issues)

    def test_valid_with_multiple_steps(self):
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[
                              SkillStep(skill_id='etd.a'),
                              SkillStep(skill_id='etd.b'),
                              SkillStep(skill_id='etd.c'),
                          ])
        issues = self._composer().validate(c)
        assert issues == []

    def test_store_skill_not_found(self):
        store = MagicMock()
        store.get_versions.return_value = []
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[SkillStep(skill_id='etd.missing')])
        composer = SkillComposer(store=store)
        issues = composer.validate(c)
        assert any('not found' in i for i in issues)

    def test_store_version_not_satisfiable(self):
        from marketplace.skill_store import StoreEntry
        store = MagicMock()
        entry = MagicMock()
        entry.version = '0.0.1'
        store.get_versions.return_value = [entry]
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[
                              SkillStep(skill_id='etd.foo', version_constraint='>=9.0.0'),
                          ])
        composer = SkillComposer(store=store)
        issues = composer.validate(c)
        assert any('no version satisfies' in i for i in issues)

    def test_store_version_satisfiable_no_issue(self):
        store = MagicMock()
        entry = MagicMock()
        entry.version = '1.2.3'
        store.get_versions.return_value = [entry]
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[
                              SkillStep(skill_id='etd.foo', version_constraint='>=1.0.0'),
                          ])
        composer = SkillComposer(store=store)
        issues = composer.validate(c)
        assert issues == []

    def test_store_no_constraint_skips_version_check(self):
        store = MagicMock()
        entry = MagicMock()
        entry.version = '1.0.0'
        store.get_versions.return_value = [entry]
        c = ComposedSkill(skill_id='etd.composed.x', version='1.0.0', name='X',
                          description='', steps=[SkillStep(skill_id='etd.foo')])
        composer = SkillComposer(store=store)
        issues = composer.validate(c)
        assert issues == []


# ── SkillComposer.run ─────────────────────────────────────────────────────────

def _always_succeed(step, ctx, params):
    return True, None


def _always_fail(step, ctx, params):
    return False, 'forced_failure'


def _fail_on(fail_ids):
    def _exec(step, ctx, params):
        if step.skill_id in fail_ids:
            return False, f'{step.skill_id}_failed'
        return True, None
    return _exec


class TestSkillComposerRun:
    def _run(self, steps, executor=None):
        c = ComposedSkill(
            skill_id='etd.composed.test', version='1.0.0', name='T',
            description='', steps=steps,
        )
        return SkillComposer().run(c, executor=executor or _always_succeed)

    def test_all_steps_succeed(self):
        steps = [SkillStep(skill_id=f'etd.s{i}') for i in range(3)]
        result = self._run(steps)
        assert result.succeeded
        assert result.status == 'success'
        assert result.steps_succeeded == 3
        assert result.steps_failed == 0

    def test_uses_mock_executor_by_default(self):
        c = ComposedSkill(
            skill_id='etd.composed.test', version='1.0.0', name='T',
            description='', steps=[SkillStep(skill_id='etd.x')],
        )
        result = SkillComposer().run(c)
        assert result.succeeded

    def test_abort_on_failure_stops_sequence(self):
        steps = [
            SkillStep(skill_id='etd.a', on_failure='abort'),
            SkillStep(skill_id='etd.b'),
            SkillStep(skill_id='etd.c'),
        ]
        result = self._run(steps, executor=_fail_on({'etd.a'}))
        assert result.status == 'aborted'
        assert result.step_results[0].status == 'failed'
        assert result.step_results[1].status == 'aborted'
        assert result.step_results[2].status == 'aborted'

    def test_skip_on_failure_continues(self):
        steps = [
            SkillStep(skill_id='etd.a', on_failure='skip'),
            SkillStep(skill_id='etd.b'),
        ]
        result = self._run(steps, executor=_fail_on({'etd.a'}))
        assert result.step_results[0].status == 'failed'
        assert result.step_results[1].status == 'success'
        assert result.status == 'failed'

    def test_retry_succeeds_on_second_attempt(self):
        call_count = {}

        def flaky(step, ctx, params):
            call_count[step.skill_id] = call_count.get(step.skill_id, 0) + 1
            return call_count[step.skill_id] >= 2, 'flaky_error'

        steps = [SkillStep(skill_id='etd.flaky', on_failure='retry', retry_count=1)]
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=steps)
        result = SkillComposer().run(c, executor=flaky)
        assert result.step_results[0].status == 'retried'
        assert result.step_results[0].attempts == 2
        assert result.succeeded

    def test_retry_exhausted_marks_failed(self):
        steps = [SkillStep(skill_id='etd.x', on_failure='retry', retry_count=2)]
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=steps)
        result = SkillComposer().run(c, executor=_always_fail)
        sr = result.step_results[0]
        assert sr.status == 'failed'
        assert sr.attempts == 3

    def test_executor_exception_is_caught(self):
        def explosive(step, ctx, params):
            raise RuntimeError('boom')

        steps = [SkillStep(skill_id='etd.x', on_failure='skip')]
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=steps)
        result = SkillComposer().run(c, executor=explosive)
        assert result.step_results[0].error == 'boom'

    def test_safety_context_shared_across_steps(self):
        violations = []

        def recording_exec(step, ctx, params):
            violations.append(step.skill_id)
            ctx.record_violation(f'{step.skill_id}_recorded')
            return True, None

        steps = [SkillStep(skill_id='etd.a'), SkillStep(skill_id='etd.b')]
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=steps)
        ctx = SafetyContext()
        result = SkillComposer().run(c, executor=recording_exec, safety_context=ctx)
        assert len(ctx.violations) == 2
        assert result.safety_context is ctx

    def test_pre_aborted_context_skips_all(self):
        ctx = SafetyContext()
        ctx.abort('external_abort')
        steps = [SkillStep(skill_id='etd.a'), SkillStep(skill_id='etd.b')]
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=steps)
        result = SkillComposer().run(c, executor=_always_succeed, safety_context=ctx)
        assert all(r.status == 'aborted' for r in result.step_results)

    def test_duration_ms_is_set(self):
        steps = [SkillStep(skill_id='etd.x')]
        result = self._run(steps)
        assert result.total_duration_ms >= 0
        assert result.step_results[0].duration_ms >= 0

    def test_result_skill_id_and_version(self):
        c = ComposedSkill(skill_id='etd.composed.foo', version='2.3.4', name='F',
                          description='', steps=[SkillStep(skill_id='etd.x')])
        result = SkillComposer().run(c, executor=_always_succeed)
        assert result.skill_id == 'etd.composed.foo'
        assert result.version == '2.3.4'

    def test_overall_failed_when_skip_step_fails(self):
        steps = [SkillStep(skill_id='etd.a', on_failure='skip')]
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=steps)
        result = SkillComposer().run(c, executor=_always_fail)
        assert result.status == 'failed'
        assert not result.succeeded


# ── ComposedSkillResult.summary / to_dict ─────────────────────────────────────

class TestComposedSkillResult:
    def _result(self):
        c = ComposedSkill(skill_id='etd.composed.test', version='1.0.0', name='T',
                          description='', steps=[
                              SkillStep(skill_id='etd.a'),
                              SkillStep(skill_id='etd.b', on_failure='skip'),
                          ])
        return SkillComposer().run(c, executor=_fail_on({'etd.b'}))

    def test_summary_contains_skill_id(self):
        r = self._result()
        s = r.summary()
        assert 'etd.composed.test' in s

    def test_summary_contains_step_info(self):
        r = self._result()
        s = r.summary()
        assert 'etd.a' in s
        assert 'etd.b' in s

    def test_to_dict_structure(self):
        r = self._result()
        d = r.to_dict()
        assert 'skill_id' in d
        assert 'status' in d
        assert 'step_results' in d
        assert isinstance(d['step_results'], list)
        assert 'safety_violations' in d

    def test_steps_succeeded_failed_skipped_counts(self):
        r = self._result()
        assert r.steps_succeeded == 1
        assert r.steps_failed == 1
        assert r.steps_skipped == 0

    def test_summary_shows_attempts_when_gt_1(self):
        call_count = {}

        def flaky(step, ctx, params):
            call_count[step.skill_id] = call_count.get(step.skill_id, 0) + 1
            return call_count[step.skill_id] >= 2, None

        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=[
                              SkillStep(skill_id='etd.f', on_failure='retry', retry_count=1),
                          ])
        r = SkillComposer().run(c, executor=flaky)
        assert '×2' in r.summary()

    def test_summary_shows_safety_violations(self):
        ctx = SafetyContext()
        ctx.record_violation('balance_loss')
        c = ComposedSkill(skill_id='etd.composed.t', version='1.0.0', name='T',
                          description='', steps=[SkillStep(skill_id='etd.x')])
        r = SkillComposer().run(c, executor=_always_succeed, safety_context=ctx)
        assert 'balance_loss' in r.summary()


# ── load_composed_skill ────────────────────────────────────────────────────────

class TestLoadComposedSkill:
    def test_load_example_package(self):
        c = load_composed_skill(EXAMPLE_COMPOSED)
        assert c.skill_id == 'etd.composed.fetch_inspect_place'
        assert c.version == '1.0.0'
        assert len(c.steps) == 3

    def test_example_step_ids(self):
        c = load_composed_skill(EXAMPLE_COMPOSED)
        ids = [s.skill_id for s in c.steps]
        assert 'etd.atlas.humanoid_walkfetch' in ids
        assert 'etd.inspect.vision' in ids
        assert 'etd.pickplace.basic' in ids

    def test_example_on_failure_values(self):
        c = load_composed_skill(EXAMPLE_COMPOSED)
        assert c.steps[0].on_failure == 'abort'
        assert c.steps[1].on_failure == 'skip'
        assert c.steps[2].on_failure == 'abort'

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match='composed_skill.json'):
            load_composed_skill(tmp_path / 'nonexistent')

    def test_load_from_string_path(self):
        c = load_composed_skill(str(EXAMPLE_COMPOSED))
        assert c.skill_id == 'etd.composed.fetch_inspect_place'


# ── CLI: compose validate ──────────────────────────────────────────────────────

class TestCLIComposeValidate:
    def test_validate_example_ok(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'validate', str(EXAMPLE_COMPOSED)])
        assert result.exit_code == 0
        assert 'VALID' in result.output

    def test_validate_example_json(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'validate', str(EXAMPLE_COMPOSED), '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['valid'] is True
        assert data['step_count'] == 3

    def test_validate_missing_package(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'validate', str(tmp_path / 'nope')])
        assert result.exit_code == 1

    def test_validate_invalid_step_shows_issues_json(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = tmp_path / 'bad_composed'
        pkg.mkdir()
        (pkg / 'composed_skill.json').write_text(json.dumps({
            'skillId': 'etd.composed.bad',
            'version': '1.0.0',
            'steps': [
                {'skillId': 'etd.composed.bad', 'onFailure': 'abort'},  # self-reference
            ],
        }))
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'validate', str(pkg), '--json'])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data['valid'] is False
        assert len(data['issues']) > 0


# ── CLI: compose run ──────────────────────────────────────────────────────────

class TestCLIComposeRun:
    def test_run_example_succeeds(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'run', str(EXAMPLE_COMPOSED)])
        assert result.exit_code == 0
        assert 'SUCCESS' in result.output

    def test_run_example_json(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'run', str(EXAMPLE_COMPOSED), '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['status'] == 'success'
        assert len(data['step_results']) == 3

    def test_run_missing_package(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['compose', 'run', str(tmp_path / 'nope')])
        assert result.exit_code == 1
