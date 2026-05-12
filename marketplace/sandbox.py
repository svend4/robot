"""ETD Package Sandbox — static analysis and runtime import restriction.

Skill packages may ship Python files (custom adapters, helpers). This module
provides two complementary layers of protection:

1. **SandboxChecker** — static AST analysis run at review time. Scans every
   ``.py`` file in the package tree and reports violations: forbidden imports,
   dangerous OS calls, use of ``eval``/``exec``/``compile``, and ``open()``
   calls outside the ``telemetry/`` sub-tree.

2. **SkillSandbox** — runtime `sys.meta_path` hook that blocks imports of
   forbidden modules whenever a skill's code is executing. Use it as a context
   manager around any dynamic skill loading.

Forbidden modules::

    subprocess, socket, urllib, requests, httpx, aiohttp, ftplib, smtplib,
    telnetlib, paramiko, multiprocessing, ctypes, cffi, pickle, marshal,
    shelve, importlib

Forbidden ``os`` attributes (when accessed as ``os.<attr>``)::

    system, popen, execv, execve, execvp, execvpe, spawnl, spawnle, spawnlp,
    spawnlpe, spawnv, spawnve, fork, forkpty, kill, killpg, remove, unlink,
    rmdir, makedirs, mkdir

Forbidden builtins::

    eval, exec, compile, __import__, breakpoint

Usage::

    from marketplace.sandbox import SandboxChecker, SkillSandbox
    from pathlib import Path

    # Static check at review time
    report = SandboxChecker().check(Path('examples/etd.pickplace.basic'))
    print(report.summary())

    # Runtime guard around dynamic import
    with SkillSandbox():
        import_skill_module()          # raises SandboxImportError if forbidden
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple


# ── Forbidden sets ────────────────────────────────────────────────────────────

FORBIDDEN_MODULES: frozenset[str] = frozenset({
    'subprocess',
    'socket',
    'ssl',
    'urllib',
    'urllib2',
    'urllib3',
    'requests',
    'httpx',
    'aiohttp',
    'ftplib',
    'smtplib',
    'telnetlib',
    'paramiko',
    'multiprocessing',
    'threading',
    'concurrent',
    'ctypes',
    'cffi',
    'pickle',
    'cPickle',
    'marshal',
    'shelve',
    'importlib',
    'pty',
    'tty',
    'atexit',
    'signal',
})

FORBIDDEN_OS_ATTRS: frozenset[str] = frozenset({
    'system', 'popen', 'popen2', 'popen3', 'popen4',
    'execv', 'execve', 'execvp', 'execvpe', 'execl', 'execle', 'execlp', 'execlpe',
    'spawnl', 'spawnle', 'spawnlp', 'spawnlpe', 'spawnv', 'spawnve', 'spawnvp', 'spawnvpe',
    'fork', 'forkpty', 'kill', 'killpg', 'abort',
    'remove', 'unlink', 'rmdir', 'makedirs', 'mkdir',
    'chmod', 'chown', 'chroot',
    'urandom',
})

FORBIDDEN_BUILTINS: frozenset[str] = frozenset({
    'eval', 'exec', 'compile', '__import__', 'breakpoint',
})

# Modules whose top-level import is allowed but specific attribute access is not
_CONTROLLED_MODULES: frozenset[str] = frozenset({'os', 'pathlib'})


# ── Violation record ──────────────────────────────────────────────────────────

@dataclass
class SandboxViolation:
    file: str
    line: int
    kind: str   # 'forbidden_import' | 'forbidden_os_call' | 'forbidden_builtin' | 'unrestricted_write'
    detail: str

    def __str__(self) -> str:
        return f'{self.file}:{self.line}  [{self.kind}]  {self.detail}'


# ── Sandbox report ────────────────────────────────────────────────────────────

@dataclass
class SandboxReport:
    package_path: str
    python_files: List[str] = field(default_factory=list)
    violations: List[SandboxViolation] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        status = 'PASS' if self.passed else 'FAIL'
        lines = [
            f'Sandbox: {status}  |  {self.package_path}',
            f'  Python files scanned : {len(self.python_files)}',
            f'  Violations           : {len(self.violations)}',
        ]
        for v in self.violations:
            lines.append(f'    ! {v}')
        for n in self.notes:
            lines.append(f'  ~ {n}')
        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'package_path': self.package_path,
            'passed': self.passed,
            'python_files': self.python_files,
            'violations': [
                {'file': v.file, 'line': v.line, 'kind': v.kind, 'detail': v.detail}
                for v in self.violations
            ],
            'notes': self.notes,
        }


# ── Static checker ────────────────────────────────────────────────────────────

class SandboxChecker:
    """Static AST analysis of Python files in a skill package.

    Scans every ``*.py`` file under *package_path* (excluding ``__pycache__``)
    and reports any violation of the ETD sandbox policy.
    """

    def check(self, package_path: Path) -> SandboxReport:
        p = package_path if isinstance(package_path, Path) else Path(package_path)
        report = SandboxReport(package_path=str(p))

        py_files = [
            f for f in sorted(p.rglob('*.py'))
            if '__pycache__' not in f.parts
        ]

        if not py_files:
            report.notes.append('no Python files found — configuration-only package is sandbox-safe')
            return report

        for f in py_files:
            report.python_files.append(str(f.relative_to(p)))
            try:
                source = f.read_text(encoding='utf-8')
                tree = ast.parse(source, filename=str(f))
            except SyntaxError as exc:
                report.violations.append(SandboxViolation(
                    file=str(f.relative_to(p)),
                    line=exc.lineno or 0,
                    kind='syntax_error',
                    detail=str(exc),
                ))
                continue

            report.violations.extend(self._check_imports(tree, str(f.relative_to(p))))
            report.violations.extend(self._check_calls(tree, str(f.relative_to(p)), p))

        return report

    # ── AST visitors ─────────────────────────────────────────────────────────

    def _check_imports(self, tree: ast.AST, filename: str) -> List[SandboxViolation]:
        violations: List[SandboxViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else ([node.module] if node.module else [])
                )
                for name in names:
                    if name is None:
                        continue
                    root = name.split('.')[0]
                    if root in FORBIDDEN_MODULES:
                        violations.append(SandboxViolation(
                            file=filename,
                            line=node.lineno,
                            kind='forbidden_import',
                            detail=f'import of forbidden module: {name!r}',
                        ))
        return violations

    def _check_calls(self, tree: ast.AST, filename: str, package_root: Path) -> List[SandboxViolation]:
        violations: List[SandboxViolation] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func

            # Bare name calls: eval(), exec(), compile(), __import__(), breakpoint()
            if isinstance(func, ast.Name):
                if func.id in FORBIDDEN_BUILTINS:
                    violations.append(SandboxViolation(
                        file=filename,
                        line=node.lineno,
                        kind='forbidden_builtin',
                        detail=f'call to forbidden builtin: {func.id!r}',
                    ))
                # open() with write mode
                if func.id == 'open':
                    v = self._check_open(node, filename, package_root, attr_chain='open')
                    if v:
                        violations.append(v)

            # Attribute calls: os.system(), os.popen(), etc.
            elif isinstance(func, ast.Attribute):
                obj = func.value
                attr = func.attr

                # os.<forbidden_attr>()
                if isinstance(obj, ast.Name) and obj.id == 'os' and attr in FORBIDDEN_OS_ATTRS:
                    violations.append(SandboxViolation(
                        file=filename,
                        line=node.lineno,
                        kind='forbidden_os_call',
                        detail=f'call to forbidden OS function: os.{attr!r}',
                    ))

                # os.path.join is fine; os.makedirs etc. via os.path.* chain
                # builtins.eval etc.
                if isinstance(obj, ast.Name) and obj.id == 'builtins' and attr in FORBIDDEN_BUILTINS:
                    violations.append(SandboxViolation(
                        file=filename,
                        line=node.lineno,
                        kind='forbidden_builtin',
                        detail=f'call to forbidden builtin via builtins.{attr!r}',
                    ))

        return violations

    def _check_open(
        self, node: ast.Call, filename: str, package_root: Path, attr_chain: str
    ) -> Optional[SandboxViolation]:
        """Flag ``open()`` calls that use a write mode outside ``telemetry/``."""
        # Try to determine the mode argument (positional or keyword)
        mode: Optional[str] = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = str(node.args[1].value)
        else:
            for kw in node.keywords:
                if kw.arg == 'mode' and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
                    break

        if mode is None:
            # Can't determine mode statically — flag as unresolved-mode write risk only
            # if the call doesn't look like a read (no mode or mode='r' is default).
            # When mode is absent we assume 'r' (safe).
            return None

        if 'w' in mode or 'a' in mode or 'x' in mode:
            # Check whether the path argument is constrained to telemetry/
            if node.args:
                path_arg = node.args[0]
            else:
                return None  # no path arg; ignore

            path_str: Optional[str] = None
            if isinstance(path_arg, ast.Constant):
                path_str = str(path_arg.value)
            elif isinstance(path_arg, ast.JoinedStr):
                pass  # f-string — can't resolve statically
            elif isinstance(path_arg, ast.Call):
                pass  # computed path — can't resolve statically

            if path_str is not None:
                # Only flag if clearly not within telemetry/
                p = Path(path_str)
                if 'telemetry' not in p.parts and not str(p).startswith('telemetry'):
                    return SandboxViolation(
                        file=filename,
                        line=node.lineno,
                        kind='unrestricted_write',
                        detail=f'open() with write mode {mode!r} outside telemetry/: {path_str!r}',
                    )
            else:
                # Dynamic path + write mode → warn but don't fail (can't resolve statically)
                return None

        return None


# ── Runtime sandbox ───────────────────────────────────────────────────────────

class SandboxImportError(ImportError):
    """Raised by ``SkillSandbox`` when a forbidden module import is attempted."""


class _BlockingFinder:
    """sys.meta_path hook that blocks imports of forbidden modules."""

    def __init__(self, forbidden: frozenset[str]) -> None:
        self._forbidden = forbidden

    def find_module(self, fullname: str, path: Any = None) -> Optional['_BlockingFinder']:
        root = fullname.split('.')[0]
        if root in self._forbidden:
            return self
        return None

    def load_module(self, fullname: str) -> ModuleType:
        raise SandboxImportError(
            f'import of {fullname!r} is blocked by the ETD skill sandbox'
        )

    def find_spec(self, fullname: str, path: Any, target: Any = None) -> None:
        root = fullname.split('.')[0]
        if root in self._forbidden:
            raise SandboxImportError(
                f'import of {fullname!r} is blocked by the ETD skill sandbox'
            )
        return None


class SkillSandbox:
    """Context manager that installs a runtime import blocker.

    Any attempt to import a forbidden module while the sandbox is active raises
    ``SandboxImportError``. Already-cached modules in ``sys.modules`` are NOT
    evicted — the guard only catches new import attempts.

    Parameters
    ----------
    extra_forbidden:
        Additional module root names to block beyond ``FORBIDDEN_MODULES``.

    Example::

        with SkillSandbox():
            import_and_execute_skill(pkg_path)  # subprocess import → SandboxImportError
    """

    def __init__(self, extra_forbidden: Optional[frozenset[str]] = None) -> None:
        blocked = FORBIDDEN_MODULES
        if extra_forbidden:
            blocked = blocked | extra_forbidden
        self._finder = _BlockingFinder(blocked)

    def __enter__(self) -> 'SkillSandbox':
        sys.meta_path.insert(0, self._finder)
        return self

    def __exit__(self, *_: Any) -> None:
        try:
            sys.meta_path.remove(self._finder)
        except ValueError:
            pass
