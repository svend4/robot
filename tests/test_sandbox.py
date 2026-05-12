"""Tests for ETD package sandbox: static checker and runtime import blocker."""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.sandbox import (
    FORBIDDEN_BUILTINS,
    FORBIDDEN_MODULES,
    FORBIDDEN_OS_ATTRS,
    SandboxChecker,
    SandboxImportError,
    SandboxReport,
    SandboxViolation,
    SkillSandbox,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write files into a fresh package directory and return its path."""
    pkg = tmp_path / "etd.test.sandbox"
    pkg.mkdir(exist_ok=True)
    for rel, content in files.items():
        f = pkg / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(textwrap.dedent(content), encoding="utf-8")
    return pkg


# ── SandboxViolation ──────────────────────────────────────────────────────────

class TestSandboxViolation:
    def test_str_contains_file_line_kind_detail(self):
        v = SandboxViolation(file="foo.py", line=5, kind="forbidden_import", detail="import subprocess")
        s = str(v)
        assert "foo.py" in s
        assert "5" in s
        assert "forbidden_import" in s
        assert "import subprocess" in s


# ── SandboxReport ─────────────────────────────────────────────────────────────

class TestSandboxReport:
    def test_passed_when_no_violations(self):
        r = SandboxReport(package_path="/pkg")
        assert r.passed is True

    def test_failed_when_violations(self):
        r = SandboxReport(package_path="/pkg", violations=[
            SandboxViolation(file="a.py", line=1, kind="forbidden_import", detail="x")
        ])
        assert r.passed is False

    def test_summary_contains_package_path(self):
        r = SandboxReport(package_path="/my/pkg")
        assert "/my/pkg" in r.summary()

    def test_summary_shows_pass(self):
        r = SandboxReport(package_path="/pkg")
        assert "PASS" in r.summary()

    def test_summary_shows_fail_when_violations(self):
        r = SandboxReport(package_path="/pkg", violations=[
            SandboxViolation(file="a.py", line=1, kind="forbidden_import", detail="x")
        ])
        assert "FAIL" in r.summary()

    def test_to_dict_keys(self):
        r = SandboxReport(package_path="/pkg")
        d = r.to_dict()
        for k in ("package_path", "passed", "python_files", "violations", "notes"):
            assert k in d

    def test_to_dict_violations_are_dicts(self):
        v = SandboxViolation(file="a.py", line=1, kind="forbidden_import", detail="detail")
        r = SandboxReport(package_path="/pkg", violations=[v])
        d = r.to_dict()
        assert isinstance(d["violations"][0], dict)
        assert d["violations"][0]["kind"] == "forbidden_import"

    def test_to_dict_is_json_serialisable(self):
        r = SandboxReport(package_path="/pkg", notes=["no python files"])
        json.dumps(r.to_dict())  # must not raise


# ── SandboxChecker — config-only packages ─────────────────────────────────────

class TestCheckerConfigOnly:
    def test_no_python_files_passes(self, tmp_path):
        pkg = _pkg(tmp_path, {"manifest.yaml": "apiVersion: etd/v1\n"})
        report = SandboxChecker().check(pkg)
        assert report.passed is True
        assert report.python_files == []
        assert any("configuration-only" in n for n in report.notes)

    def test_real_example_packages_pass(self):
        for name in ["etd.pickplace.basic", "etd.hyundai.wia_welding"]:
            pkg = ROOT / "examples" / name
            if not pkg.exists():
                continue
            report = SandboxChecker().check(pkg)
            assert report.passed, f"{name}: {report.violations}"


# ── SandboxChecker — forbidden imports ───────────────────────────────────────

class TestCheckerForbiddenImports:
    def _check(self, tmp_path, source: str):
        pkg = _pkg(tmp_path, {"skill.py": source})
        return SandboxChecker().check(pkg)

    def test_import_subprocess_fails(self, tmp_path):
        r = self._check(tmp_path, "import subprocess\n")
        assert not r.passed
        assert any(v.kind == "forbidden_import" for v in r.violations)
        assert any("subprocess" in v.detail for v in r.violations)

    def test_import_socket_fails(self, tmp_path):
        r = self._check(tmp_path, "import socket\n")
        assert not r.passed
        assert any("socket" in v.detail for v in r.violations)

    def test_from_subprocess_import_fails(self, tmp_path):
        r = self._check(tmp_path, "from subprocess import run\n")
        assert not r.passed

    def test_import_requests_fails(self, tmp_path):
        r = self._check(tmp_path, "import requests\n")
        assert not r.passed

    def test_import_pickle_fails(self, tmp_path):
        r = self._check(tmp_path, "import pickle\n")
        assert not r.passed

    def test_import_ctypes_fails(self, tmp_path):
        r = self._check(tmp_path, "import ctypes\n")
        assert not r.passed

    def test_import_multiprocessing_fails(self, tmp_path):
        r = self._check(tmp_path, "import multiprocessing\n")
        assert not r.passed

    def test_import_importlib_fails(self, tmp_path):
        r = self._check(tmp_path, "import importlib\n")
        assert not r.passed

    def test_import_threading_fails(self, tmp_path):
        r = self._check(tmp_path, "import threading\n")
        assert not r.passed

    def test_import_os_allowed(self, tmp_path):
        r = self._check(tmp_path, "import os\n")
        assert r.passed  # os itself is allowed; specific attrs are checked at call sites

    def test_import_json_allowed(self, tmp_path):
        r = self._check(tmp_path, "import json\n")
        assert r.passed

    def test_import_pathlib_allowed(self, tmp_path):
        r = self._check(tmp_path, "from pathlib import Path\n")
        assert r.passed

    def test_clean_file_passes(self, tmp_path):
        r = self._check(tmp_path, "x = 1 + 2\nprint(x)\n")
        assert r.passed

    def test_violation_has_correct_line_number(self, tmp_path):
        source = "x = 1\nimport subprocess\n"
        r = self._check(tmp_path, source)
        assert r.violations[0].line == 2


# ── SandboxChecker — forbidden OS calls ──────────────────────────────────────

class TestCheckerForbiddenOSCalls:
    def _check(self, tmp_path, source: str):
        pkg = _pkg(tmp_path, {"adapter.py": source})
        return SandboxChecker().check(pkg)

    def test_os_system_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.system('ls')\n")
        assert not r.passed
        assert any(v.kind == "forbidden_os_call" for v in r.violations)

    def test_os_popen_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.popen('cat /etc/passwd')\n")
        assert not r.passed

    def test_os_fork_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.fork()\n")
        assert not r.passed

    def test_os_kill_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.kill(1234, 9)\n")
        assert not r.passed

    def test_os_execv_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.execv('/bin/sh', ['/bin/sh'])\n")
        assert not r.passed

    def test_os_remove_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.remove('data.db')\n")
        assert not r.passed

    def test_os_makedirs_fails(self, tmp_path):
        r = self._check(tmp_path, "import os\nos.makedirs('new/dir')\n")
        assert not r.passed

    def test_os_path_join_allowed(self, tmp_path):
        r = self._check(tmp_path, "import os\np = os.path.join('a', 'b')\n")
        assert r.passed

    def test_os_path_exists_allowed(self, tmp_path):
        r = self._check(tmp_path, "import os\nok = os.path.exists('/tmp')\n")
        assert r.passed


# ── SandboxChecker — forbidden builtins ──────────────────────────────────────

class TestCheckerForbiddenBuiltins:
    def _check(self, tmp_path, source: str):
        pkg = _pkg(tmp_path, {"helper.py": source})
        return SandboxChecker().check(pkg)

    def test_eval_fails(self, tmp_path):
        r = self._check(tmp_path, "result = eval('1+1')\n")
        assert not r.passed
        assert any(v.kind == "forbidden_builtin" for v in r.violations)
        assert any("eval" in v.detail for v in r.violations)

    def test_exec_fails(self, tmp_path):
        r = self._check(tmp_path, "exec('x=1')\n")
        assert not r.passed

    def test_compile_fails(self, tmp_path):
        r = self._check(tmp_path, "compile('x=1', '<str>', 'exec')\n")
        assert not r.passed

    def test_dunder_import_fails(self, tmp_path):
        r = self._check(tmp_path, "__import__('subprocess')\n")
        assert not r.passed

    def test_breakpoint_fails(self, tmp_path):
        r = self._check(tmp_path, "breakpoint()\n")
        assert not r.passed

    def test_print_allowed(self, tmp_path):
        r = self._check(tmp_path, "print('hello')\n")
        assert r.passed


# ── SandboxChecker — open() write outside telemetry ──────────────────────────

class TestCheckerOpenWrite:
    def _check(self, tmp_path, source: str):
        pkg = _pkg(tmp_path, {"writer.py": source})
        return SandboxChecker().check(pkg)

    def test_open_write_outside_telemetry_fails(self, tmp_path):
        r = self._check(tmp_path, "open('/etc/shadow', 'w')\n")
        assert not r.passed
        assert any(v.kind == "unrestricted_write" for v in r.violations)

    def test_open_write_in_telemetry_passes(self, tmp_path):
        r = self._check(tmp_path, "open('telemetry/events.log', 'w')\n")
        assert r.passed

    def test_open_read_passes(self, tmp_path):
        r = self._check(tmp_path, "open('/etc/hosts', 'r')\n")
        assert r.passed

    def test_open_no_mode_passes(self, tmp_path):
        r = self._check(tmp_path, "open('config.json')\n")
        assert r.passed

    def test_open_append_outside_telemetry_fails(self, tmp_path):
        r = self._check(tmp_path, "open('output.db', 'a')\n")
        assert not r.passed


# ── SandboxChecker — multiple files ──────────────────────────────────────────

class TestCheckerMultipleFiles:
    def test_violations_from_multiple_files_collected(self, tmp_path):
        pkg = _pkg(tmp_path, {
            "adapter.py": "import subprocess\n",
            "util.py": "import socket\n",
        })
        r = SandboxChecker().check(pkg)
        assert not r.passed
        assert len(r.violations) == 2
        files = {v.file for v in r.violations}
        assert "adapter.py" in files
        assert "util.py" in files

    def test_python_files_list_populated(self, tmp_path):
        pkg = _pkg(tmp_path, {
            "a.py": "x = 1\n",
            "b.py": "y = 2\n",
        })
        r = SandboxChecker().check(pkg)
        assert len(r.python_files) == 2

    def test_pycache_files_excluded(self, tmp_path):
        pkg = tmp_path / "etd.test.pycache"
        pkg.mkdir()
        (pkg / "good.py").write_text("x = 1\n", encoding="utf-8")
        pycache = pkg / "__pycache__"
        pycache.mkdir()
        (pycache / "bad.cpython-311.py").write_text("import subprocess\n", encoding="utf-8")
        r = SandboxChecker().check(pkg)
        assert all("__pycache__" not in f for f in r.python_files)

    def test_syntax_error_reported_as_violation(self, tmp_path):
        pkg = _pkg(tmp_path, {"broken.py": "def f(\n"})  # unterminated
        r = SandboxChecker().check(pkg)
        assert not r.passed
        assert any(v.kind == "syntax_error" for v in r.violations)


# ── SkillSandbox — runtime blocker ───────────────────────────────────────────

class TestSkillSandbox:
    def test_blocks_subprocess_import(self):
        # Evict from cache so the import machinery consults meta_path finders
        saved = sys.modules.pop('subprocess', None)
        try:
            with SkillSandbox():
                with pytest.raises(SandboxImportError):
                    import subprocess  # noqa: F401
        finally:
            if saved is not None:
                sys.modules['subprocess'] = saved

    def test_blocks_socket_import(self):
        saved = sys.modules.pop('socket', None)
        try:
            with SkillSandbox():
                with pytest.raises(SandboxImportError):
                    import socket  # noqa: F401
        finally:
            if saved is not None:
                sys.modules['socket'] = saved

    def test_allows_json_import(self):
        with SkillSandbox():
            import json  # should not raise  # noqa: F401

    def test_allows_pathlib_import(self):
        with SkillSandbox():
            from pathlib import Path  # should not raise  # noqa: F401

    def test_sandbox_removed_after_exit(self):
        sandbox = SkillSandbox()
        with sandbox:
            pass
        # After context, importing subprocess should not raise SandboxImportError
        # (it may or may not be available, but no sandbox error)
        import subprocess  # noqa: F401

    def test_extra_forbidden_modules_blocked(self):
        with SkillSandbox(extra_forbidden=frozenset({'yaml'})):
            # yaml is not normally blocked, but now it should be
            # We can only test the finder is installed
            from marketplace.sandbox import _BlockingFinder
            # Verify finder is in sys.meta_path
            assert any(isinstance(f, _BlockingFinder) for f in sys.meta_path)

    def test_finder_removed_on_exception(self):
        from marketplace.sandbox import _BlockingFinder
        try:
            with SkillSandbox():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert not any(isinstance(f, _BlockingFinder) for f in sys.meta_path)

    def test_sandbox_import_error_is_import_error(self):
        assert issubclass(SandboxImportError, ImportError)


# ── ReviewPipeline integration (sandbox stage) ────────────────────────────────

class TestReviewPipelineSandboxStage:
    def test_config_only_package_sandbox_passes(self, tmp_path):
        from marketplace.review_pipeline import ReviewPipeline
        import yaml as _yaml
        pkg = tmp_path / "etd.test"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(_yaml.dump({
            "apiVersion": "etd/v1", "kind": "SkillPackage",
            "metadata": {"name": "etd.test", "version": "1.0.0"},
        }), encoding="utf-8")
        (pkg / "capabilities.json").write_text(
            json.dumps({"write": ["command.skill_intent"]}), encoding="utf-8"
        )
        result = ReviewPipeline().run(pkg)
        sandbox_stage = next(s for s in result.stages if s.name == 'sandbox_check')
        assert sandbox_stage.passed is True

    def test_package_with_forbidden_import_sandbox_fails(self, tmp_path):
        from marketplace.review_pipeline import ReviewPipeline
        import yaml as _yaml
        pkg = tmp_path / "etd.bad"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(_yaml.dump({
            "apiVersion": "etd/v1", "kind": "SkillPackage",
            "metadata": {"name": "etd.bad", "version": "1.0.0"},
        }), encoding="utf-8")
        (pkg / "capabilities.json").write_text(
            json.dumps({"write": ["command.skill_intent"]}), encoding="utf-8"
        )
        (pkg / "adapter.py").write_text("import subprocess\n", encoding="utf-8")
        result = ReviewPipeline().run(pkg)
        sandbox_stage = next(s for s in result.stages if s.name == 'sandbox_check')
        assert sandbox_stage.passed is False
        assert result.human_review_required is True

    def test_sandbox_stage_is_first(self, tmp_path):
        from marketplace.review_pipeline import ReviewPipeline
        import yaml as _yaml
        pkg = tmp_path / "etd.first"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(_yaml.dump({
            "apiVersion": "etd/v1", "kind": "SkillPackage",
            "metadata": {"name": "etd.first", "version": "1.0.0"},
        }), encoding="utf-8")
        (pkg / "capabilities.json").write_text(
            json.dumps({"write": ["command.skill_intent"]}), encoding="utf-8"
        )
        result = ReviewPipeline().run(pkg)
        assert result.stages[0].name == 'sandbox_check'

    def test_real_packages_sandbox_stage_passes(self):
        from marketplace.review_pipeline import ReviewPipeline
        for name in ["etd.pickplace.basic", "etd.hyundai.wia_welding"]:
            pkg = ROOT / "examples" / name
            if not pkg.exists():
                continue
            result = ReviewPipeline().run(pkg)
            sandbox_stage = next(s for s in result.stages if s.name == 'sandbox_check')
            assert sandbox_stage.passed, f"{name} sandbox stage failed: {sandbox_stage.findings}"


# ── CLI sandbox-check command ─────────────────────────────────────────────────

class TestSandboxCheckCLI:
    def test_clean_package_exits_zero(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("etd.pickplace.basic not present")
        runner = CliRunner()
        result = runner.invoke(cli, ["sandbox-check", str(pkg)])
        assert result.exit_code == 0

    def test_clean_package_json_output(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("etd.pickplace.basic not present")
        runner = CliRunner()
        result = runner.invoke(cli, ["sandbox-check", "--json", str(pkg)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "passed" in data
        assert data["passed"] is True

    def test_nonexistent_package_exits_one(self):
        from click.testing import CliRunner
        from etd_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["sandbox-check", "/nonexistent/path"])
        assert result.exit_code == 1

    def test_forbidden_import_package_exits_one(self, tmp_path):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = _pkg(tmp_path, {"bad.py": "import subprocess\n"})
        runner = CliRunner()
        result = runner.invoke(cli, ["sandbox-check", str(pkg)])
        assert result.exit_code == 1

    def test_output_mentions_sandbox(self):
        from click.testing import CliRunner
        from etd_cli import cli
        pkg = ROOT / "examples" / "etd.pickplace.basic"
        if not pkg.exists():
            pytest.skip("etd.pickplace.basic not present")
        runner = CliRunner()
        result = runner.invoke(cli, ["sandbox-check", str(pkg)])
        assert "Sandbox" in result.output or "sandbox" in result.output.lower()
