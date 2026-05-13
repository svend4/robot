"""ETD Skill A/B Testing Framework.

Allows comparing two or more versions of a skill in production by routing
executions to variants according to configured weights, then analysing results
using the TelemetryStore.

Architecture
------------
::

    ABExperimentStore  ──▶  ABExperiment  ──▶  ABVariant
          (JSON)              route()
                                │
                         TelemetryStore  ──▶  ABAnalyzer
                                               compare() / recommend_winner()

Key abstractions
----------------
``ABVariant``
    One arm of an experiment: a ``skill_id``, ``version``, routing ``weight``
    (0.0–1.0, normalised to 1.0 across variants), and a human-readable
    ``label`` (e.g. ``'control'``, ``'treatment'``).

``ABExperiment``
    A named experiment consisting of ≥ 2 variants.  Status lifecycle:
    ``active`` → ``paused`` | ``concluded``.  ``route()`` performs weighted
    random selection and returns the chosen ``ABVariant``.

``ABExperimentStore``
    JSON-backed persistence for experiments.  One JSON file stores all
    experiments as a dict keyed by ``experiment_id``.

``ABAnalyzer``
    Reads ``TelemetryStore`` to compare variants on ``success_rate`` and
    ``mean_duration_ms``.  ``recommend_winner()`` scores each variant and
    returns the label of the best performer.

Usage::

    from marketplace.ab_testing import (
        ABExperiment, ABVariant, ABExperimentStore, ABAnalyzer,
    )
    from marketplace.telemetry_analytics import TelemetryStore
    from pathlib import Path

    exp_store = ABExperimentStore(Path('ab/experiments.json'))
    exp = ABExperiment.make(
        name='pickplace speed trial',
        variants=[
            ABVariant('etd.pickplace.basic', '0.1.0', 0.5, 'control'),
            ABVariant('etd.pickplace.basic', '0.2.0', 0.5, 'treatment'),
        ],
    )
    exp_store.save(exp)

    chosen = exp.route()
    print(f'Route to: {chosen.skill_id} v{chosen.version} [{chosen.label}]')

    tel_store = TelemetryStore(Path('telemetry/executions.jsonl'))
    analyzer  = ABAnalyzer(tel_store)
    results   = analyzer.compare(exp)
    winner    = analyzer.recommend_winner(exp)
"""
from __future__ import annotations

import datetime
import json
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _new_id() -> str:
    return str(uuid.uuid4())


# ── ABVariant ─────────────────────────────────────────────────────────────────

@dataclass
class ABVariant:
    """One arm of an A/B experiment."""
    skill_id: str
    version: str
    weight: float       # unnormalised; route() normalises across siblings
    label: str = ''     # e.g. 'control', 'treatment'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'version': self.version,
            'weight': self.weight,
            'label': self.label,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ABVariant':
        return cls(
            skill_id=d['skill_id'],
            version=d['version'],
            weight=float(d.get('weight', 1.0)),
            label=d.get('label', ''),
        )


# ── ABExperiment ──────────────────────────────────────────────────────────────

_VALID_STATUSES = frozenset({'active', 'paused', 'concluded'})


@dataclass
class ABExperiment:
    """A named experiment containing ≥ 2 variants."""
    experiment_id: str
    name: str
    variants: List[ABVariant]
    status: str = 'active'          # 'active' | 'paused' | 'concluded'
    created_at: str = field(default_factory=_utcnow)
    concluded_at: Optional[str] = None
    winner_label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── routing ───────────────────────────────────────────────────────────────

    def route(self) -> ABVariant:
        """Return a variant chosen by normalised weighted random selection.

        Raises ``ValueError`` if the experiment is not active or has no
        variants with positive weight.
        """
        if self.status != 'active':
            raise ValueError(
                f'Experiment {self.experiment_id!r} is {self.status!r}; '
                'cannot route.'
            )
        pool = [v for v in self.variants if v.weight > 0]
        if not pool:
            raise ValueError('No variants with positive weight.')
        total = sum(v.weight for v in pool)
        r = random.random() * total
        cumulative = 0.0
        for v in pool:
            cumulative += v.weight
            if r <= cumulative:
                return v
        return pool[-1]

    # ── variant lookup ────────────────────────────────────────────────────────

    def get_variant(self, label: str) -> Optional[ABVariant]:
        for v in self.variants:
            if v.label == label:
                return v
        return None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def pause(self) -> None:
        if self.status != 'active':
            raise ValueError(f'Cannot pause experiment with status {self.status!r}.')
        self.status = 'paused'

    def resume(self) -> None:
        if self.status != 'paused':
            raise ValueError(f'Cannot resume experiment with status {self.status!r}.')
        self.status = 'active'

    def conclude(self, winner_label: Optional[str] = None) -> None:
        if self.status == 'concluded':
            raise ValueError('Experiment is already concluded.')
        self.status = 'concluded'
        self.concluded_at = _utcnow()
        self.winner_label = winner_label

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            'experiment_id': self.experiment_id,
            'name': self.name,
            'variants': [v.to_dict() for v in self.variants],
            'status': self.status,
            'created_at': self.created_at,
            'concluded_at': self.concluded_at,
            'winner_label': self.winner_label,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ABExperiment':
        return cls(
            experiment_id=d['experiment_id'],
            name=d['name'],
            variants=[ABVariant.from_dict(v) for v in d.get('variants', [])],
            status=d.get('status', 'active'),
            created_at=d.get('created_at', _utcnow()),
            concluded_at=d.get('concluded_at'),
            winner_label=d.get('winner_label'),
            metadata=dict(d.get('metadata', {})),
        )

    @classmethod
    def make(
        cls,
        name: str,
        variants: List[ABVariant],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> 'ABExperiment':
        """Convenience factory — fills in ID and timestamp."""
        return cls(
            experiment_id=_new_id(),
            name=name,
            variants=variants,
            metadata=metadata or {},
        )


# ── ABExperimentStore ─────────────────────────────────────────────────────────

class ABExperimentStore:
    """JSON-backed store for AB experiments.

    All experiments are stored as a single JSON object keyed by
    ``experiment_id``.  Reads load the full object; writes serialise the
    full object (experiments are typically few and small).

    Parameters
    ----------
    store_path:
        Path to the ``.json`` file.  Created (with parent dirs) on first
        write if absent.
    """

    def __init__(self, store_path: Path) -> None:
        self._path = Path(store_path)
        self._experiments: Dict[str, ABExperiment] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding='utf-8'))
            self._experiments = {
                k: ABExperiment.from_dict(v)
                for k, v in data.items()
            }
        except Exception:
            self._experiments = {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {k: v.to_dict() for k, v in self._experiments.items()},
                indent=2,
            ),
            encoding='utf-8',
        )

    def save(self, experiment: ABExperiment) -> None:
        """Insert or update an experiment."""
        self._experiments[experiment.experiment_id] = experiment
        self._flush()

    def get(self, experiment_id: str) -> Optional[ABExperiment]:
        return self._experiments.get(experiment_id)

    def list_experiments(
        self,
        status: Optional[str] = None,
    ) -> List[ABExperiment]:
        result = list(self._experiments.values())
        if status:
            result = [e for e in result if e.status == status]
        result.sort(key=lambda e: e.created_at, reverse=True)
        return result

    def delete(self, experiment_id: str) -> bool:
        if experiment_id not in self._experiments:
            return False
        del self._experiments[experiment_id]
        self._flush()
        return True

    @property
    def experiment_count(self) -> int:
        return len(self._experiments)


# ── ABAnalyzer ────────────────────────────────────────────────────────────────

@dataclass
class VariantResult:
    """Stats for one variant gathered from the telemetry store."""
    label: str
    skill_id: str
    version: str
    execution_count: int
    success_count: int
    success_rate: float
    mean_duration_ms: float
    p95_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label,
            'skill_id': self.skill_id,
            'version': self.version,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'success_rate': round(self.success_rate, 4),
            'mean_duration_ms': round(self.mean_duration_ms, 1),
            'p95_ms': round(self.p95_ms, 1),
        }


class ABAnalyzer:
    """Compare experiment variants using data from a ``TelemetryStore``.

    Matching is done on ``skill_id`` only (version filtering is not supported
    by the telemetry store query interface).  The analyzer therefore looks at
    all executions for each variant's ``skill_id`` and returns what it finds.
    For accurate per-version comparison, record executions with the version
    embedded in a custom ``skill_id`` suffix (e.g. ``etd.pick@0.2.0``).
    """

    def __init__(self, telemetry_store: Any) -> None:
        self._store = telemetry_store

    def _variant_result(self, variant: ABVariant) -> VariantResult:
        from marketplace.telemetry_analytics import TelemetryAnalyzer, _percentile
        import statistics as _stats

        records = self._store.query(skill_id=variant.skill_id)
        if not records:
            return VariantResult(
                label=variant.label,
                skill_id=variant.skill_id,
                version=variant.version,
                execution_count=0,
                success_count=0,
                success_rate=0.0,
                mean_duration_ms=0.0,
                p95_ms=0.0,
            )
        n_ok = sum(1 for r in records if r.status == 'success')
        durations = sorted(float(r.total_duration_ms) for r in records
                           if r.total_duration_ms > 0)
        mean_dur = _stats.mean(durations) if durations else 0.0
        p95 = _percentile(durations, 95)
        return VariantResult(
            label=variant.label,
            skill_id=variant.skill_id,
            version=variant.version,
            execution_count=len(records),
            success_count=n_ok,
            success_rate=n_ok / len(records),
            mean_duration_ms=mean_dur,
            p95_ms=p95,
        )

    def compare(self, experiment: ABExperiment) -> Dict[str, Any]:
        """Return a comparison dict for all variants in the experiment."""
        results = [self._variant_result(v) for v in experiment.variants]
        return {
            'experiment_id': experiment.experiment_id,
            'name': experiment.name,
            'status': experiment.status,
            'variants': [r.to_dict() for r in results],
            'winner_label': experiment.winner_label,
        }

    def recommend_winner(self, experiment: ABExperiment) -> Optional[str]:
        """Return the label of the recommended winning variant, or None.

        Scoring: ``success_rate`` (higher = better) is the primary key;
        ``mean_duration_ms`` (lower = better) breaks ties.  Returns None
        when no variant has any executions.
        """
        results = [self._variant_result(v) for v in experiment.variants]
        with_data = [r for r in results if r.execution_count > 0]
        if not with_data:
            return None
        best = max(
            with_data,
            key=lambda r: (r.success_rate, -r.mean_duration_ms),
        )
        return best.label or best.skill_id
