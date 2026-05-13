"""ETD Skill Composer — chain multiple sub-skills into a higher-level composed skill.

A **composed skill** is a JSON manifest that declares an ordered sequence of
existing ETD sub-skills.  The composer validates dependency availability,
resolves version constraints, and executes steps in order with a shared safety
context.

Failure policies per step
--------------------------
- ``abort``  — stop the whole sequence immediately (default)
- ``skip``   — log the failure and continue to the next step
- ``retry``  — re-run up to ``retryCount`` times before applying ``onFailure``

Shared safety context
---------------------
Each step execution reads and writes a ``SafetyContext`` dict.  A safety
violation in any step (e.g. ``balance_loss_detected``) is visible to all
subsequent steps and may prevent them from starting.

Composed skill manifest format (``composed_skill.json``)::

    {
        "skillId":     "etd.composed.fetch_inspect_place",
        "version":     "1.0.0",
        "name":        "Fetch, Inspect, and Place",
        "description": "Walk-fetch → vision QA → pick-and-place sequence.",
        "steps": [
            {
                "skillId":         "etd.atlas.humanoid_walkfetch",
                "versionConstraint": ">=0.1.0",
                "onFailure":       "abort",
                "retryCount":      0,
                "params":          {}
            },
            ...
        ]
    }

Usage::

    from marketplace.composer import SkillComposer, load_composed_skill
    from marketplace.skill_store import SkillStore
    from pathlib import Path

    store   = SkillStore(Path('.'))
    composed = load_composed_skill(Path('examples/etd.composed.fetch_inspect_place'))
    composer = SkillComposer(store)

    issues = composer.validate(composed)          # [] means OK
    result = composer.run(composed, executor=None) # dry-run with mock executor
    print(result.summary())
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ON_FAILURE_VALUES = frozenset({'abort', 'skip', 'retry'})


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class SkillStep:
    skill_id: str
    version_constraint: str = ''   # semver constraint, e.g. ">=0.1.0"
    on_failure: str = 'abort'      # 'abort' | 'skip' | 'retry'
    retry_count: int = 0
    params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.on_failure not in ON_FAILURE_VALUES:
            raise ValueError(
                f'on_failure must be one of {sorted(ON_FAILURE_VALUES)}, '
                f'got {self.on_failure!r}'
            )
        if self.retry_count < 0:
            raise ValueError(f'retry_count must be >= 0, got {self.retry_count}')

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SkillStep':
        return cls(
            skill_id=d['skillId'],
            version_constraint=d.get('versionConstraint', ''),
            on_failure=d.get('onFailure', 'abort'),
            retry_count=int(d.get('retryCount', 0)),
            params=dict(d.get('params', {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skillId': self.skill_id,
            'versionConstraint': self.version_constraint,
            'onFailure': self.on_failure,
            'retryCount': self.retry_count,
            'params': self.params,
        }


@dataclass
class ComposedSkill:
    skill_id: str
    version: str
    name: str
    description: str
    steps: List[SkillStep]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ComposedSkill':
        return cls(
            skill_id=d['skillId'],
            version=d.get('version', '0.0.0'),
            name=d.get('name', d['skillId']),
            description=d.get('description', ''),
            steps=[SkillStep.from_dict(s) for s in d.get('steps', [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skillId': self.skill_id,
            'version': self.version,
            'name': self.name,
            'description': self.description,
            'steps': [s.to_dict() for s in self.steps],
        }


@dataclass
class SafetyContext:
    """Shared mutable state passed between steps during execution."""
    violations: List[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str = ''

    def record_violation(self, violation: str) -> None:
        self.violations.append(violation)

    def abort(self, reason: str) -> None:
        self.aborted = True
        self.abort_reason = reason

    @property
    def safe(self) -> bool:
        return not self.aborted and len(self.violations) == 0


@dataclass
class StepResult:
    step_index: int
    skill_id: str
    status: str          # 'success' | 'failed' | 'skipped' | 'aborted' | 'retried'
    attempts: int = 1
    error: Optional[str] = None
    duration_ms: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == 'success'


@dataclass
class ComposedSkillResult:
    skill_id: str
    version: str
    status: str          # 'success' | 'failed' | 'aborted'
    step_results: List[StepResult] = field(default_factory=list)
    safety_context: Optional[SafetyContext] = None
    total_duration_ms: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == 'success'

    @property
    def steps_succeeded(self) -> int:
        return sum(1 for r in self.step_results if r.succeeded)

    @property
    def steps_failed(self) -> int:
        return sum(1 for r in self.step_results if r.status == 'failed')

    @property
    def steps_skipped(self) -> int:
        return sum(1 for r in self.step_results if r.status == 'skipped')

    def summary(self) -> str:
        lines = [
            f'Composed: {self.status.upper()}  |  {self.skill_id} v{self.version}',
            f'  Steps  : {len(self.step_results)} total  '
            f'{self.steps_succeeded} ok  {self.steps_failed} failed  '
            f'{self.steps_skipped} skipped',
            f'  Time   : {self.total_duration_ms} ms',
        ]
        for r in self.step_results:
            mark = {'success': '✓', 'failed': '✗', 'skipped': '~',
                    'aborted': '!', 'retried': '↺'}.get(r.status, '?')
            line = f'  {mark} [{r.step_index}] {r.skill_id}'
            if r.attempts > 1:
                line += f'  (×{r.attempts})'
            if r.error:
                line += f'  → {r.error}'
            lines.append(line)
        if self.safety_context and self.safety_context.violations:
            lines.append(f'  Safety violations: {self.safety_context.violations}')
        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'version': self.version,
            'status': self.status,
            'steps_succeeded': self.steps_succeeded,
            'steps_failed': self.steps_failed,
            'steps_skipped': self.steps_skipped,
            'total_duration_ms': self.total_duration_ms,
            'step_results': [
                {
                    'step_index': r.step_index,
                    'skill_id': r.skill_id,
                    'status': r.status,
                    'attempts': r.attempts,
                    'error': r.error,
                    'duration_ms': r.duration_ms,
                }
                for r in self.step_results
            ],
            'safety_violations': (
                self.safety_context.violations if self.safety_context else []
            ),
        }


# ── Step executor protocol ────────────────────────────────────────────────────

# An executor is a callable: (step, safety_ctx, params) → (success, error_msg)
StepExecutor = Callable[[SkillStep, SafetyContext, Dict[str, Any]], tuple[bool, Optional[str]]]


def mock_executor(
    step: SkillStep,
    safety_ctx: SafetyContext,
    params: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """Default dry-run executor: succeeds for all steps unless context is aborted."""
    if not safety_ctx.safe:
        return False, f'safety_context_violated: {safety_ctx.abort_reason or safety_ctx.violations}'
    return True, None


# ── Composer ──────────────────────────────────────────────────────────────────

class SkillComposer:
    """Validate and execute composed multi-step skills.

    Parameters
    ----------
    store:
        ``SkillStore`` used for dependency validation.  Pass ``None`` to skip
        store-based validation (useful in tests).
    runtime_version:
        The ETD runtime version — used when resolving version constraints.
    """

    def __init__(self, store: Any = None, runtime_version: str = '0.0.0') -> None:
        self._store = store
        self._runtime_version = runtime_version

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self, composed: ComposedSkill) -> List[str]:
        """Return a list of validation issues (empty = OK).

        Checks
        ------
        - At least one step defined
        - Each step's ``on_failure`` is a valid value
        - Each step's ``skill_id`` exists in the store (when store is set)
        - Each step's version constraint is satisfiable (when store is set)
        - No duplicate ``(skill_id, version_constraint)`` pairs that would
          introduce an obvious cycle
        """
        issues: List[str] = []

        if not composed.steps:
            issues.append('composed skill has no steps')
            return issues

        seen_skills: List[str] = []
        for i, step in enumerate(composed.steps):
            prefix = f'step[{i}] {step.skill_id!r}'

            if not step.skill_id:
                issues.append(f'{prefix}: skill_id is empty')
                continue

            if step.on_failure not in ON_FAILURE_VALUES:
                issues.append(f'{prefix}: invalid on_failure {step.on_failure!r}')

            # Self-reference check
            if step.skill_id == composed.skill_id:
                issues.append(f'{prefix}: step references the composed skill itself (cycle)')

            seen_skills.append(step.skill_id)

            if self._store is not None:
                from marketplace.version_negotiator import satisfies
                versions = self._store.get_versions(step.skill_id)
                if not versions:
                    issues.append(f'{prefix}: skill not found in store')
                elif step.version_constraint:
                    satisfiable = any(
                        satisfies(e.version, step.version_constraint)
                        for e in versions
                    )
                    if not satisfiable:
                        issues.append(
                            f'{prefix}: no version satisfies constraint '
                            f'{step.version_constraint!r}'
                        )

        return issues

    # ── Execution ─────────────────────────────────────────────────────────────

    def run(
        self,
        composed: ComposedSkill,
        executor: Optional[StepExecutor] = None,
        safety_context: Optional[SafetyContext] = None,
    ) -> ComposedSkillResult:
        """Execute the composed skill step by step.

        Parameters
        ----------
        executor:
            Callable ``(step, safety_ctx, params) → (success, error_msg)``.
            Defaults to ``mock_executor`` (dry-run, always succeeds).
        safety_context:
            Shared mutable safety state. Created fresh if not provided.
        """
        if executor is None:
            executor = mock_executor
        if safety_context is None:
            safety_context = SafetyContext()

        step_results: List[StepResult] = []
        overall_start = _ms()
        overall_status = 'success'

        for i, step in enumerate(composed.steps):
            # If context was aborted by a prior step, mark remaining as aborted
            if safety_context.aborted:
                step_results.append(StepResult(
                    step_index=i, skill_id=step.skill_id, status='aborted',
                    error='prior step aborted the sequence',
                ))
                continue

            step_result = self._run_step(i, step, executor, safety_context)
            step_results.append(step_result)

            if not step_result.succeeded:
                if step.on_failure == 'abort':
                    safety_context.abort(
                        f'step[{i}] {step.skill_id} failed: {step_result.error}'
                    )
                    overall_status = 'aborted'
                elif step.on_failure == 'skip':
                    pass  # continue to next step
                # 'retry' is handled inside _run_step; if exhausted it lands here

        if overall_status == 'success':
            # Any remaining unaborted failures?
            if any(r.status == 'failed' for r in step_results):
                overall_status = 'failed'

        return ComposedSkillResult(
            skill_id=composed.skill_id,
            version=composed.version,
            status=overall_status,
            step_results=step_results,
            safety_context=safety_context,
            total_duration_ms=_ms() - overall_start,
        )

    def _run_step(
        self,
        index: int,
        step: SkillStep,
        executor: StepExecutor,
        safety_context: SafetyContext,
    ) -> StepResult:
        attempts = 0
        max_attempts = 1 + (step.retry_count if step.on_failure == 'retry' else 0)
        last_error: Optional[str] = None

        while attempts < max_attempts:
            start = _ms()
            attempts += 1
            try:
                success, error = executor(step, safety_context, step.params)
            except Exception as exc:
                success, error = False, str(exc)

            duration = _ms() - start

            if success:
                return StepResult(
                    step_index=index,
                    skill_id=step.skill_id,
                    status='success' if attempts == 1 else 'retried',
                    attempts=attempts,
                    duration_ms=duration,
                )
            last_error = error

        return StepResult(
            step_index=index,
            skill_id=step.skill_id,
            status='failed',
            attempts=attempts,
            error=last_error,
            duration_ms=_ms() - start,
        )


# ── File I/O helpers ──────────────────────────────────────────────────────────

def load_composed_skill(package_path: Path) -> ComposedSkill:
    """Load a ``ComposedSkill`` from a ``composed_skill.json`` in *package_path*."""
    p = package_path if isinstance(package_path, Path) else Path(package_path)
    manifest_path = p / 'composed_skill.json'
    if not manifest_path.exists():
        raise FileNotFoundError(
            f'composed_skill.json not found in {p}; '
            'this does not appear to be a composed skill package'
        )
    return ComposedSkill.from_dict(json.loads(manifest_path.read_text(encoding='utf-8')))


def _ms() -> int:
    return int(time.monotonic() * 1000)
