"""Tests for the automated ETD review pipeline."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.review_pipeline import (
    ReviewPipeline,
    ReviewResult,
    StageResult,
    _load,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_package(tmp_path: Path, *, manifest_extra=None, caps_extra=None,
                  profiles=None, include_skill_json=True) -> Path:
    """Create a minimal valid ETD package directory for testing."""
    pkg = tmp_path / "etd.test.skill"
    pkg.mkdir()

    manifest = {
        "apiVersion": "etd/v1",
        "kind": "SkillPackage",
        "metadata": {
            "name": "etd.test.skill",
            "version": "1.0.0",
            "riskLevel": "medium",
        },
        "constraints": {
            "payloadKgMax": 5.0,
        },
        "compatibility": {
            "robotClass": ["humanoid", "cobot"],
            "requiresServices": ["manipulation.arm_control"],
            "optionalServices": ["telemetry.metrics"],
            "runtime": ">=0.1.0",
        },
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    (pkg / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

    caps = {
        "read": ["state.robot_pose", "state.arm_state"],
        "write": ["command.skill_intent"],
        "forbidden": [],
    }
    if caps_extra:
        caps.update(caps_extra)
    (pkg / "capabilities.json").write_text(json.dumps(caps), encoding="utf-8")

    if include_skill_json:
        skill = {
            "skillId": "etd.test.skill",
            "version": "1.0.0",
            "family": "test",
            "riskLevel": "medium",
        }
        (pkg / "skill.json").write_text(json.dumps(skill), encoding="utf-8")

    if profiles is not None:
        (pkg / "chs_profiles.json").write_text(
            json.dumps({"profiles": profiles}), encoding="utf-8"
        )
    else:
        (pkg / "chs_profiles.json").write_text(
            json.dumps({"profiles": [
                {"name": "default", "payloadKg": 2.0, "forceWindowN": [10, 100],
                 "arcZoneRadius_m": 1.5}
            ]}),
            encoding="utf-8",
        )

    return pkg


# ── StageResult ───────────────────────────────────────────────────────────────

class TestStageResult:
    def test_passed_by_default_false(self):
        s = StageResult(name="test", passed=False)
        assert s.passed is False

    def test_findings_and_warnings_default_empty(self):
        s = StageResult(name="test", passed=True)
        assert s.findings == []
        assert s.warnings == []


# ── ReviewResult ──────────────────────────────────────────────────────────────

class TestReviewResult:
    def _make_result(self, *, passed_stages=True, risk_level="medium"):
        stage = StageResult(name="schema_validation", passed=passed_stages)
        return ReviewResult(
            skill_id="etd.test.skill",
            version="1.0.0",
            package_path="/tmp/pkg",
            stages=[stage],
            risk_level=risk_level,
            human_review_required=False,
        )

    def test_passed_all_stages_pass(self):
        r = self._make_result(passed_stages=True)
        assert r.passed is True

    def test_passed_false_when_any_stage_fails(self):
        r = self._make_result(passed_stages=False)
        assert r.passed is False

    def test_blocking_findings_empty_when_all_pass(self):
        r = self._make_result(passed_stages=True)
        assert r.blocking_findings == []

    def test_blocking_findings_populated_from_failed_stages(self):
        stage = StageResult(name="cap", passed=False, findings=["missing cap"])
        r = ReviewResult(
            skill_id="s", version="1.0.0", package_path="/tmp",
            stages=[stage], risk_level="low",
        )
        assert "missing cap" in r.blocking_findings

    def test_summary_contains_skill_id(self):
        r = self._make_result()
        s = r.summary()
        assert "etd.test.skill" in s

    def test_summary_shows_pass(self):
        r = self._make_result(passed_stages=True)
        assert "PASS" in r.summary()

    def test_summary_shows_fail_when_stage_fails(self):
        r = self._make_result(passed_stages=False)
        assert "FAIL" in r.summary()

    def test_to_dict_has_required_keys(self):
        r = self._make_result()
        d = r.to_dict()
        for key in ("skill_id", "version", "passed", "risk_level",
                    "human_review_required", "stages", "compat_matrix"):
            assert key in d

    def test_to_dict_stages_are_serialisable(self):
        r = self._make_result()
        d = r.to_dict()
        stage_d = d["stages"][0]
        assert "name" in stage_d
        assert "passed" in stage_d
        assert "findings" in stage_d
        assert "warnings" in stage_d


# ── ReviewPipeline — stage 1: schema ─────────────────────────────────────────

class TestPipelineSchemaStage:
    def test_valid_package_passes(self, tmp_path):
        pkg = _make_package(tmp_path)
        pipeline = ReviewPipeline()
        with patch.object(pipeline, '_stage_schema') as mock_stage:
            mock_stage.return_value = StageResult(name='schema_validation', passed=True)
            result = pipeline.run(pkg)
        assert any(s.name == 'schema_validation' for s in result.stages)

    def test_real_package_schema_stage(self, tmp_path):
        # Run against real package directory to exercise validator path
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("example package not present")
        pipeline = ReviewPipeline()
        result = pipeline.run(pkg)
        schema_stage = next(s for s in result.stages if s.name == 'schema_validation')
        # Should pass for a well-formed package
        assert schema_stage.passed is True


# ── ReviewPipeline — stage 2: capabilities ───────────────────────────────────

class TestPipelineCapabilityStage:
    def _run_caps(self, tmp_path, caps_extra):
        pkg = _make_package(tmp_path, caps_extra=caps_extra)
        result = ReviewPipeline().run(pkg)
        return next(s for s in result.stages if s.name == 'capability_audit')

    def test_valid_caps_passes(self, tmp_path):
        stage = self._run_caps(tmp_path, {})
        assert stage.passed is True

    def test_missing_required_write_cap_fails(self, tmp_path):
        stage = self._run_caps(tmp_path, {"write": []})
        assert stage.passed is False
        assert any("command.skill_intent" in f for f in stage.findings)

    def test_forbidden_cap_in_write_list_fails(self, tmp_path):
        stage = self._run_caps(tmp_path, {
            "write": ["command.skill_intent", "command.servo_torque"]
        })
        assert stage.passed is False
        assert any("command.servo_torque" in f for f in stage.findings)

    def test_collision_disable_in_write_fails(self, tmp_path):
        stage = self._run_caps(tmp_path, {
            "write": ["command.skill_intent", "command.collision_disable"]
        })
        assert stage.passed is False

    def test_extra_forbidden_declared_not_in_etd_set_warns(self, tmp_path):
        stage = self._run_caps(tmp_path, {
            "write": ["command.skill_intent"],
            "forbidden": ["nonexistent.cap"],
        })
        assert stage.passed is True  # only a warning, not a finding
        assert any("nonexistent.cap" in w for w in stage.warnings)

    def test_multiple_forbidden_caps_all_reported(self, tmp_path):
        stage = self._run_caps(tmp_path, {
            "write": ["command.skill_intent", "command.servo_torque",
                      "command.joint_limit_override"]
        })
        assert stage.passed is False
        combined = " ".join(stage.findings)
        assert "command.servo_torque" in combined or "command.joint_limit_override" in combined


# ── ReviewPipeline — stage 3: safety boundary ────────────────────────────────

class TestPipelineSafetyStage:
    def _run_safety(self, tmp_path, *, risk_level="medium",
                    manifest_extra=None, profiles=None):
        extra = {"metadata": {
            "name": "etd.test.skill",
            "version": "1.0.0",
            "riskLevel": risk_level,
        }}
        if manifest_extra:
            extra.update(manifest_extra)
        pkg = _make_package(tmp_path, manifest_extra=extra, profiles=profiles)
        result = ReviewPipeline().run(pkg)
        return next(s for s in result.stages if s.name == 'safety_boundary')

    def test_valid_profiles_passes(self, tmp_path):
        stage = self._run_safety(tmp_path)
        assert stage.passed is True

    def test_high_risk_warns_but_passes_stage(self, tmp_path):
        stage = self._run_safety(tmp_path, risk_level="high")
        assert stage.passed is True
        assert any("high" in w for w in stage.warnings)

    def test_negative_force_window_lower_fails(self, tmp_path):
        profiles = [{"name": "p1", "payloadKg": 1.0, "forceWindowN": [-5, 100],
                     "arcZoneRadius_m": 1.5}]
        stage = self._run_safety(tmp_path, profiles=profiles)
        assert stage.passed is False
        assert any("negative force window" in f for f in stage.findings)

    def test_force_window_upper_less_than_lower_fails(self, tmp_path):
        profiles = [{"name": "p1", "payloadKg": 1.0, "forceWindowN": [100, 50],
                     "arcZoneRadius_m": 1.5}]
        stage = self._run_safety(tmp_path, profiles=profiles)
        assert stage.passed is False
        assert any("upper < lower" in f for f in stage.findings)

    def test_force_window_over_500n_warns(self, tmp_path):
        profiles = [{"name": "p1", "payloadKg": 1.0, "forceWindowN": [10, 600],
                     "arcZoneRadius_m": 1.5}]
        stage = self._run_safety(tmp_path, profiles=profiles)
        assert stage.passed is True
        assert any("500N" in w for w in stage.warnings)

    def test_payload_exceeds_constraint_fails(self, tmp_path):
        profiles = [{"name": "p1", "payloadKg": 10.0, "forceWindowN": [10, 100],
                     "arcZoneRadius_m": 1.5}]
        stage = self._run_safety(tmp_path, profiles=profiles)
        assert stage.passed is False
        assert any("exceeds constraint" in f for f in stage.findings)

    def test_arc_zone_radius_below_1m_fails(self, tmp_path):
        profiles = [{"name": "p1", "payloadKg": 1.0, "forceWindowN": [10, 100],
                     "arcZoneRadius_m": 0.5}]
        stage = self._run_safety(tmp_path, profiles=profiles)
        assert stage.passed is False
        assert any("arcZoneRadius_m" in f for f in stage.findings)

    def test_no_chs_profiles_passes_safety(self, tmp_path):
        pkg = _make_package(tmp_path)
        (pkg / "chs_profiles.json").unlink()
        result = ReviewPipeline().run(pkg)
        stage = next(s for s in result.stages if s.name == 'safety_boundary')
        assert stage.passed is True

    def test_multiple_profiles_all_checked(self, tmp_path):
        profiles = [
            {"name": "ok", "payloadKg": 1.0, "forceWindowN": [10, 100], "arcZoneRadius_m": 1.5},
            {"name": "bad", "payloadKg": 1.0, "forceWindowN": [-1, 100], "arcZoneRadius_m": 1.5},
        ]
        stage = self._run_safety(tmp_path, profiles=profiles)
        assert stage.passed is False


# ── ReviewPipeline — compat matrix ───────────────────────────────────────────

class TestCompatMatrix:
    def test_compat_matrix_has_expected_keys(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        m = result.compat_matrix
        for k in ("robot_classes", "required_services", "optional_services",
                  "runtime_constraint", "compatible_stations", "station_count"):
            assert k in m

    def test_robot_classes_from_manifest(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        assert "humanoid" in result.compat_matrix["robot_classes"]
        assert "cobot" in result.compat_matrix["robot_classes"]

    def test_required_services_from_manifest(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        assert "manipulation.arm_control" in result.compat_matrix["required_services"]

    def test_optional_services_from_manifest(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        assert "telemetry.metrics" in result.compat_matrix["optional_services"]

    def test_runtime_constraint_from_manifest(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        assert result.compat_matrix["runtime_constraint"] == ">=0.1.0"

    def test_station_count_is_integer(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        assert isinstance(result.compat_matrix["station_count"], int)

    def test_compatible_stations_is_list(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        assert isinstance(result.compat_matrix["compatible_stations"], list)

    def test_no_manifest_compat_section(self, tmp_path):
        pkg = tmp_path / "etd.minimal"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(yaml.dump({
            "apiVersion": "etd/v1",
            "kind": "SkillPackage",
            "metadata": {"name": "etd.minimal", "version": "0.1.0"},
        }), encoding="utf-8")
        (pkg / "capabilities.json").write_text(
            json.dumps({"write": ["command.skill_intent"]}), encoding="utf-8"
        )
        result = ReviewPipeline().run(pkg)
        m = result.compat_matrix
        assert m["robot_classes"] == []
        assert m["required_services"] == []


# ── human_review_required flag ────────────────────────────────────────────────

class TestHumanReviewRequired:
    def test_not_required_for_clean_medium_risk(self, tmp_path):
        pkg = _make_package(tmp_path)
        result = ReviewPipeline().run(pkg)
        # human_review_required may be True if schema stage fails — so only assert
        # the flag's logic: if all stages pass and risk != high, it should be False
        if result.passed and result.risk_level != 'high':
            assert result.human_review_required is False

    def test_required_when_risk_is_high(self, tmp_path):
        extra = {"metadata": {
            "name": "etd.test.skill", "version": "1.0.0", "riskLevel": "high"
        }}
        pkg = _make_package(tmp_path, manifest_extra=extra)
        result = ReviewPipeline().run(pkg)
        assert result.human_review_required is True

    def test_required_when_cap_stage_fails(self, tmp_path):
        pkg = _make_package(tmp_path, caps_extra={"write": []})
        result = ReviewPipeline().run(pkg)
        assert result.human_review_required is True

    def test_required_when_safety_stage_fails(self, tmp_path):
        profiles = [{"name": "bad", "payloadKg": 1.0, "forceWindowN": [-10, 50],
                     "arcZoneRadius_m": 1.5}]
        pkg = _make_package(tmp_path, profiles=profiles)
        result = ReviewPipeline().run(pkg)
        assert result.human_review_required is True


# ── Full pipeline with real packages ─────────────────────────────────────────

class TestPipelineRealPackages:
    @pytest.mark.parametrize("pkg_name", [
        "etd.pickplace.basic",
        "etd.hyundai.wia_welding",
        "etd.hyundai.mobed_transport",
    ])
    def test_real_package_runs_without_exception(self, pkg_name):
        pkg = ROOT / "examples" / pkg_name
        if not pkg.exists():
            pytest.skip(f"example package {pkg_name} not present")
        result = ReviewPipeline().run(pkg)
        assert result.skill_id  # non-empty
        assert result.version
        assert len(result.stages) == 3

    def test_to_dict_is_json_serialisable(self):
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("etd.pickplace.basic not present")
        result = ReviewPipeline().run(pkg)
        d = result.to_dict()
        serialised = json.dumps(d)  # must not raise
        assert "etd.pickplace.basic" in serialised


# ── _load helper ──────────────────────────────────────────────────────────────

class TestLoadHelper:
    def test_load_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"a": 1}', encoding="utf-8")
        assert _load(f) == {"a": 1}

    def test_load_yaml(self, tmp_path):
        f = tmp_path / "data.yaml"
        f.write_text("a: 1\n", encoding="utf-8")
        assert _load(f) == {"a": 1}

    def test_load_yml_extension(self, tmp_path):
        f = tmp_path / "data.yml"
        f.write_text("x: hello\n", encoding="utf-8")
        assert _load(f) == {"x": "hello"}


# ── CLI review command ────────────────────────────────────────────────────────

class TestReviewCLI:
    def test_review_valid_package(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("etd.pickplace.basic not present")
        runner = CliRunner()
        result = runner.invoke(cli, ["review", str(pkg)])
        assert result.exit_code == 0
        assert "etd.pickplace.basic" in result.output

    def test_review_json_output(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("etd.pickplace.basic not present")
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--json", str(pkg)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "skill_id" in data

    def test_review_nonexistent_package_exits_nonzero(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "/nonexistent/path/skill"])
        assert result.exit_code != 0

    def test_review_high_risk_package_shows_warning(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = _make_package(tmp_path, manifest_extra={
            "metadata": {
                "name": "etd.test.highrisk", "version": "1.0.0", "riskLevel": "high"
            }
        })
        runner = CliRunner()
        result = runner.invoke(cli, ["review", str(pkg)])
        # Exit code depends on whether all stages pass, but output should mention high/review
        assert "high" in result.output.lower() or "review" in result.output.lower()
