"""ETD Publisher Portal — skill package submission and review workflow.

Publishers submit a skill package path for automated review. The portal runs
``ReviewPipeline`` immediately on submission. Packages that pass all pipeline
stages and are not high-risk are auto-approved; others enter ``in_review`` for
human decision.

Submission state machine::

    submitted → in_review ──→ approved
                          ├──→ rejected
                          └──→ needs_revision → in_review (re-submit) → …

Usage::

    from marketplace.publisher_portal import PublisherPortal
    from pathlib import Path

    portal = PublisherPortal(Path('.'))
    rec = portal.submit(Path('examples/etd.pickplace.basic'), publisher='etd-lab')
    print(rec.status)       # 'approved' (auto) or 'in_review'

    portal.approve(rec.submission_id, decided_by='admin@etd')
"""
from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── State constants ───────────────────────────────────────────────────────────

STATUSES = frozenset({
    'submitted',        # created, pipeline not yet run
    'in_review',        # pipeline run, human decision pending
    'approved',         # accepted for publication
    'rejected',         # declined
    'needs_revision',   # publisher must fix and re-submit
})


# ── Submission record ─────────────────────────────────────────────────────────

@dataclass
class SubmissionRecord:
    submission_id: str
    skill_id: str
    version: str
    package_path: str
    publisher: str
    submitted_at: str
    status: str                             # one of STATUSES
    pipeline_passed: Optional[bool] = None  # None = not run yet
    human_review_required: Optional[bool] = None
    review_result: Optional[Dict[str, Any]] = None  # ReviewResult.to_dict()
    blocking_findings: List[str] = field(default_factory=list)
    decision_reason: str = ''
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SubmissionRecord':
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in allowed})


# ── Portal ────────────────────────────────────────────────────────────────────

class PublisherPortal:
    """Manage skill package submissions and their review lifecycle.

    Parameters
    ----------
    repo_root:
        Project root directory (used to locate ``marketplace/``).
    submissions_path:
        Path to the JSON submissions store. Defaults to
        ``<repo_root>/marketplace/submissions.json``.
    station_profiles_dir:
        Passed to ``ReviewPipeline`` for compat matrix stage.
    auto_approve_on_pass:
        When ``True`` (default), submissions that pass the full pipeline and do
        not require human review are automatically moved to ``approved``.
    """

    def __init__(
        self,
        repo_root: Path,
        submissions_path: Optional[Path] = None,
        station_profiles_dir: Optional[Path] = None,
        auto_approve_on_pass: bool = True,
    ) -> None:
        self._root = repo_root if isinstance(repo_root, Path) else Path(repo_root)
        self._submissions_path = submissions_path or (
            self._root / 'marketplace' / 'submissions.json'
        )
        self._station_profiles_dir = station_profiles_dir
        self._auto_approve = auto_approve_on_pass
        self._submissions: Dict[str, SubmissionRecord] = {}
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(self, package_path: Path, publisher: str) -> SubmissionRecord:
        """Submit a skill package for review.

        Runs the ``ReviewPipeline`` immediately. If all stages pass and human
        review is not required, the submission is auto-approved (when
        ``auto_approve_on_pass=True``).

        Parameters
        ----------
        package_path:
            Path to the skill package directory.
        publisher:
            Publisher identifier (e.g. ``'etd-lab'``, ``'hyundai-robotics'``).

        Returns
        -------
        ``SubmissionRecord`` with status set.
        """
        from marketplace.review_pipeline import ReviewPipeline

        p = package_path if isinstance(package_path, Path) else Path(package_path)
        now = _now()
        sid = str(uuid.uuid4())

        # Read skill metadata without full store loading
        skill_id, version = _read_skill_meta(p)

        rec = SubmissionRecord(
            submission_id=sid,
            skill_id=skill_id,
            version=version,
            package_path=str(p),
            publisher=publisher,
            submitted_at=now,
            status='submitted',
        )

        # Run pipeline
        try:
            pipeline = ReviewPipeline(
                station_profiles_dir=self._station_profiles_dir
            )
            result = pipeline.run(p)
            rec.pipeline_passed = result.passed
            rec.human_review_required = result.human_review_required
            rec.review_result = result.to_dict()
            rec.blocking_findings = result.blocking_findings

            if result.passed and not result.human_review_required and self._auto_approve:
                rec.status = 'approved'
                rec.decided_at = now
                rec.decided_by = 'auto'
                rec.decision_reason = 'all pipeline stages passed; auto-approved'
            else:
                rec.status = 'in_review'
        except Exception as exc:
            rec.status = 'in_review'
            rec.pipeline_passed = False
            rec.blocking_findings = [f'pipeline_exception: {exc}']

        self._submissions[sid] = rec
        self._save()
        return rec

    def get_submission(self, submission_id: str) -> Optional[SubmissionRecord]:
        """Return the submission record for *submission_id*, or None."""
        return self._submissions.get(submission_id)

    def list_submissions(
        self,
        publisher: Optional[str] = None,
        status: Optional[str] = None,
        skill_id: Optional[str] = None,
    ) -> List[SubmissionRecord]:
        """Return submissions filtered by optional *publisher*, *status*, *skill_id*."""
        results = list(self._submissions.values())
        if publisher is not None:
            results = [r for r in results if r.publisher == publisher]
        if status is not None:
            results = [r for r in results if r.status == status]
        if skill_id is not None:
            results = [r for r in results if r.skill_id == skill_id]
        return sorted(results, key=lambda r: r.submitted_at, reverse=True)

    def approve(
        self,
        submission_id: str,
        decided_by: str = 'admin',
        reason: str = '',
    ) -> SubmissionRecord:
        """Approve a submission. Allowed from ``in_review`` or ``needs_revision``."""
        rec = self._require(submission_id, allowed={'in_review', 'needs_revision'})
        rec.status = 'approved'
        rec.decided_at = _now()
        rec.decided_by = decided_by
        rec.decision_reason = reason or 'approved by reviewer'
        self._save()
        return rec

    def reject(
        self,
        submission_id: str,
        reason: str,
        decided_by: str = 'admin',
    ) -> SubmissionRecord:
        """Reject a submission. Allowed from ``in_review`` or ``needs_revision``."""
        rec = self._require(submission_id, allowed={'in_review', 'needs_revision'})
        rec.status = 'rejected'
        rec.decided_at = _now()
        rec.decided_by = decided_by
        rec.decision_reason = reason
        self._save()
        return rec

    def request_revision(
        self,
        submission_id: str,
        reason: str,
        decided_by: str = 'admin',
    ) -> SubmissionRecord:
        """Request changes. Moves submission to ``needs_revision``."""
        rec = self._require(submission_id, allowed={'in_review'})
        rec.status = 'needs_revision'
        rec.decided_at = _now()
        rec.decided_by = decided_by
        rec.decision_reason = reason
        self._save()
        return rec

    def resubmit(self, submission_id: str) -> SubmissionRecord:
        """Re-run the pipeline on a ``needs_revision`` submission.

        Clears the previous decision and re-runs ``ReviewPipeline``, potentially
        auto-approving if the fixes now pass.
        """
        original = self._require(submission_id, allowed={'needs_revision'})
        original.status = 'submitted'
        original.decided_at = None
        original.decided_by = None
        original.decision_reason = ''
        # Re-run pipeline via submit-like logic
        updated = self.submit(Path(original.package_path), original.publisher)
        # Keep original submission_id
        updated.submission_id = original.submission_id
        self._submissions[original.submission_id] = updated
        self._save()
        return updated

    @property
    def submission_count(self) -> int:
        return len(self._submissions)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._submissions_path.exists():
            return
        try:
            data = json.loads(self._submissions_path.read_text(encoding='utf-8'))
            for raw in data.get('submissions', []):
                try:
                    rec = SubmissionRecord.from_dict(raw)
                    self._submissions[rec.submission_id] = rec
                except Exception:
                    pass
        except Exception:
            pass

    def _save(self) -> None:
        self._submissions_path.parent.mkdir(parents=True, exist_ok=True)
        data = {'submissions': [r.to_dict() for r in self._submissions.values()]}
        self._submissions_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'
        )

    def _require(
        self, submission_id: str, allowed: set[str]
    ) -> SubmissionRecord:
        rec = self._submissions.get(submission_id)
        if rec is None:
            raise KeyError(f'submission {submission_id!r} not found')
        if rec.status not in allowed:
            raise ValueError(
                f'submission {submission_id!r} has status {rec.status!r}; '
                f'expected one of {sorted(allowed)}'
            )
        return rec


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _read_skill_meta(p: Path):
    """Extract (skill_id, version) from manifest.yaml or skill.json."""
    import yaml
    manifest_path = p / 'manifest.yaml'
    if manifest_path.exists():
        try:
            doc = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
            meta = (doc.get('metadata') or {}) if isinstance(doc, dict) else {}
            return meta.get('name', p.name), meta.get('version', '0.0.0')
        except Exception:
            pass
    skill_path = p / 'skill.json'
    if skill_path.exists():
        try:
            doc = json.loads(skill_path.read_text(encoding='utf-8'))
            return doc.get('skillId', p.name), doc.get('version', '0.0.0')
        except Exception:
            pass
    return p.name, '0.0.0'
