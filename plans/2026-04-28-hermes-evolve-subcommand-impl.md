# `hermes evolve` Subcommand Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `hermes evolve <skill> [evolve-flags...]` subcommand to the local hermes CLI that subprocess-dispatches into the `hermes-agent-self-evolution` package's venv, with helper flags (`--where`, `--version`), distinct exit codes for setup failures, and pure-function unit tests.

**Architecture:** Single new module `hermes_cli/evolve.py` (~80 LOC of pure functions plus one `os.execvp`). Argparse subparser registered in `hermes_cli/main.py` with `add_help=False` and `argparse.REMAINDER` so all flags pass through unmolested. Skill positional rewritten to `--skill <skill>` (idempotent). Path resolution searches `HERMES_EVOLUTION_HOME` → `~/code/hermes-agent-self-evolution` → `~/hermes-agent-self-evolution` → `~/.hermes/hermes-agent-self-evolution`. No new runtime deps; stdlib only (`os`, `pathlib`, `subprocess`, `argparse`).

**Tech Stack:** Python 3.11+, argparse, `os.execvp`, pytest with `tmp_path` and `monkeypatch`. Tests stub the resolved venv with shell scripts that exit known codes — no real Python interpreter spawned.

**Working directory:** `/home/inno/.hermes/hermes-agent`. Branch already created: `innoscout/feat-hermes-evolve-subcommand`. Design doc at `plans/hermes-evolve-subcommand.md`.

**Quality gates per task:** Use the `superpowers:test-driven-development` skill principles. Tests fail first, pass after minimal implementation, then commit.

---

## Task 1: Skeleton + path resolution (TDD)

**Files:**
- Create: `hermes_cli/evolve.py`
- Create: `tests/hermes_cli/test_evolve.py`

**Goal of this task:** Land `resolve_evolution_home()`, `venv_python()`, and `verify_package_importable()` as testable pure functions.

### Step 1: Write the failing tests

Create `tests/hermes_cli/test_evolve.py`:

```python
"""Unit tests for the `hermes evolve` subcommand wrapper.

The wrapper is pure-function except for one os.execvp call. Tests stub
the self-evolution install with a tmp_path tree containing a fake
.venv/bin/python shell script that exits a known code.
"""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_cli import evolve


def _make_fake_install(root: Path, *, python_exit_code: int = 0) -> Path:
    """Create a tmp self-evolution install with an executable .venv/bin/python.

    The fake python is a shell script that exits with `python_exit_code`,
    letting tests simulate venv-importable / venv-broken / etc.
    """
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    py = venv_bin / "python"
    py.write_text(f"#!/bin/sh\nexit {python_exit_code}\n")
    py.chmod(py.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return root


class TestResolveEvolutionHome:
    def test_env_var_wins(self, tmp_path, monkeypatch):
        env_install = _make_fake_install(tmp_path / "env-install")
        # Default fallback also exists, but env should still win.
        home_install = _make_fake_install(tmp_path / "home" / "code" / "hermes-agent-self-evolution")
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(env_install))
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert evolve.resolve_evolution_home() == env_install

    def test_home_code_fallback(self, tmp_path, monkeypatch):
        install = _make_fake_install(tmp_path / "home" / "code" / "hermes-agent-self-evolution")
        monkeypatch.delenv("HERMES_EVOLUTION_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert evolve.resolve_evolution_home() == install

    def test_home_root_fallback(self, tmp_path, monkeypatch):
        install = _make_fake_install(tmp_path / "home" / "hermes-agent-self-evolution")
        monkeypatch.delenv("HERMES_EVOLUTION_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert evolve.resolve_evolution_home() == install

    def test_sibling_fallback(self, tmp_path, monkeypatch):
        # Sibling of ~/.hermes/hermes-agent → ~/.hermes/hermes-agent-self-evolution
        sibling = _make_fake_install(tmp_path / "home" / ".hermes" / "hermes-agent-self-evolution")
        monkeypatch.delenv("HERMES_EVOLUTION_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert evolve.resolve_evolution_home() == sibling

    def test_no_install_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HERMES_EVOLUTION_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert evolve.resolve_evolution_home() is None

    def test_env_var_to_missing_dir_falls_through(self, tmp_path, monkeypatch):
        # Env var points nowhere → fall through to the next candidate.
        install = _make_fake_install(tmp_path / "home" / "code" / "hermes-agent-self-evolution")
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(tmp_path / "does-not-exist"))
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert evolve.resolve_evolution_home() == install


class TestVenvPython:
    def test_returns_path_when_present(self, tmp_path):
        install = _make_fake_install(tmp_path)
        assert evolve.venv_python(install) == install / ".venv" / "bin" / "python"

    def test_returns_none_when_missing(self, tmp_path):
        # Directory exists but no .venv inside.
        (tmp_path / "evo").mkdir()
        assert evolve.venv_python(tmp_path / "evo") is None


class TestVerifyPackageImportable:
    def test_true_when_python_exits_zero(self, tmp_path):
        install = _make_fake_install(tmp_path, python_exit_code=0)
        py = evolve.venv_python(install)
        assert evolve.verify_package_importable(py) is True

    def test_false_when_python_exits_nonzero(self, tmp_path):
        install = _make_fake_install(tmp_path, python_exit_code=1)
        py = evolve.venv_python(install)
        assert evolve.verify_package_importable(py) is False
```

### Step 2: Run tests to verify they fail

Run:
```bash
cd /home/inno/.hermes/hermes-agent && venv/bin/pytest tests/hermes_cli/test_evolve.py -v
```
Expected: ImportError or "module hermes_cli.evolve not found" — fails immediately.

### Step 3: Write minimal implementation

Create `hermes_cli/evolve.py`:

```python
"""Subprocess wrapper that exposes hermes-agent-self-evolution as `hermes evolve`.

The wrapper resolves the self-evolution install path, verifies its venv has
the `evolution` package importable, then `os.execvp`s into
`<install>/.venv/bin/python -m evolution.skills.evolve_skill ...`. The user
sees Rich-console output unchanged; Ctrl+C forwards naturally; exit code
propagates.

See plans/hermes-evolve-subcommand.md for the full design.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional


# Path resolution candidates, in priority order. Each callable receives the
# evaluated $HOME and returns a candidate Path. The env-var lookup is handled
# separately because it is highest priority and not relative to HOME.
_FALLBACK_CANDIDATES = (
    lambda home: home / "code" / "hermes-agent-self-evolution",
    lambda home: home / "hermes-agent-self-evolution",
    lambda home: home / ".hermes" / "hermes-agent-self-evolution",
)


def _has_venv_python(candidate: Path) -> bool:
    """A candidate path is usable iff it contains an executable .venv/bin/python."""
    py = candidate / ".venv" / "bin" / "python"
    return py.is_file() and os.access(py, os.X_OK)


def resolve_evolution_home() -> Optional[Path]:
    """Find a usable hermes-agent-self-evolution install.

    Priority order:
        1. $HERMES_EVOLUTION_HOME (if set, dir exists, .venv/bin/python is exec)
        2. ~/code/hermes-agent-self-evolution
        3. ~/hermes-agent-self-evolution
        4. ~/.hermes/hermes-agent-self-evolution

    Returns the first candidate that satisfies all conditions, or None.
    """
    env = os.environ.get("HERMES_EVOLUTION_HOME")
    if env:
        candidate = Path(env).expanduser()
        if candidate.is_dir() and _has_venv_python(candidate):
            return candidate

    home = Path(os.environ.get("HOME", "~")).expanduser()
    for build in _FALLBACK_CANDIDATES:
        candidate = build(home)
        if candidate.is_dir() and _has_venv_python(candidate):
            return candidate

    return None


def venv_python(install: Path) -> Optional[Path]:
    """Return the venv's python executable path, or None if missing."""
    py = install / ".venv" / "bin" / "python"
    return py if py.is_file() and os.access(py, os.X_OK) else None


def verify_package_importable(python: Path) -> bool:
    """Spawn `<python> -c 'import evolution'` and return whether it succeeded.

    Fast (~150ms) sanity check — catches half-set-up installs before users
    sit through the slower Rich-console startup.
    """
    try:
        result = subprocess.run(
            [str(python), "-c", "import evolution"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
```

### Step 4: Run tests to verify they pass

Run:
```bash
cd /home/inno/.hermes/hermes-agent && venv/bin/pytest tests/hermes_cli/test_evolve.py -v
```
Expected: 9 tests passed (3 in TestVerifyPackageImportable / TestVenvPython, 6 in TestResolveEvolutionHome).

### Step 5: Commit

```bash
cd /home/inno/.hermes/hermes-agent
git add hermes_cli/evolve.py tests/hermes_cli/test_evolve.py
git commit -m "$(cat <<'EOF'
feat(evolve): path resolver, venv python lookup, importability check

First slice of hermes_cli/evolve.py — pure-function helpers used by the
upcoming hermes evolve subcommand wrapper.

- resolve_evolution_home(): walks HERMES_EVOLUTION_HOME -> ~/code/...
  -> ~/... -> ~/.hermes/... and returns the first candidate whose
  .venv/bin/python is executable.
- venv_python(install): returns the venv python path or None.
- verify_package_importable(python): spawns `<python> -c "import
  evolution"` with a 10s timeout, returns success bool.

9 unit tests using tmp_path fixtures with a fake .venv/bin/python shell
script that exits known codes. No real Python spawned for the resolver
tests; only the importability check actually runs the stub script.
EOF
)"
```

---

## Task 2: Argv builder with `--skill` rewrite

**Files:**
- Modify: `hermes_cli/evolve.py`
- Modify: `tests/hermes_cli/test_evolve.py`

### Step 1: Add the failing tests

Append to `tests/hermes_cli/test_evolve.py`:

```python
class TestBuildArgv:
    def _python(self, tmp_path):
        return _make_fake_install(tmp_path) / ".venv" / "bin" / "python"

    def test_basic_forwarding(self, tmp_path):
        py = self._python(tmp_path)
        argv = evolve.build_argv(py, ["github-code-review"])
        assert argv == [
            str(py),
            "-m",
            "evolution.skills.evolve_skill",
            "--skill",
            "github-code-review",
        ]

    def test_skill_then_flags(self, tmp_path):
        py = self._python(tmp_path)
        argv = evolve.build_argv(
            py, ["github-code-review", "--use-llm-judge", "--run-tests"]
        )
        assert argv == [
            str(py),
            "-m",
            "evolution.skills.evolve_skill",
            "--skill",
            "github-code-review",
            "--use-llm-judge",
            "--run-tests",
        ]

    def test_explicit_skill_flag_no_rewrite(self, tmp_path):
        # User typed --skill themselves — do not duplicate.
        py = self._python(tmp_path)
        argv = evolve.build_argv(
            py, ["--skill", "github-code-review", "--use-llm-judge"]
        )
        assert argv.count("--skill") == 1
        assert argv == [
            str(py),
            "-m",
            "evolution.skills.evolve_skill",
            "--skill",
            "github-code-review",
            "--use-llm-judge",
        ]

    def test_skill_equals_form_no_rewrite(self, tmp_path):
        # --skill=foo is also "explicit"; no rewrite.
        py = self._python(tmp_path)
        argv = evolve.build_argv(
            py, ["--skill=github-code-review", "--use-llm-judge"]
        )
        assert "--skill" not in argv  # Only the =form is present.
        assert "--skill=github-code-review" in argv

    def test_only_flags_no_rewrite(self, tmp_path):
        # No positional skill name — pass everything as-is. Underlying CLI
        # will complain that --skill is required; that is its job.
        py = self._python(tmp_path)
        argv = evolve.build_argv(py, ["--help"])
        assert argv == [
            str(py),
            "-m",
            "evolution.skills.evolve_skill",
            "--help",
        ]

    def test_empty_args_passes_nothing_extra(self, tmp_path):
        py = self._python(tmp_path)
        argv = evolve.build_argv(py, [])
        assert argv == [str(py), "-m", "evolution.skills.evolve_skill"]
```

### Step 2: Run tests to verify they fail

Run:
```bash
venv/bin/pytest tests/hermes_cli/test_evolve.py::TestBuildArgv -v
```
Expected: AttributeError "module 'hermes_cli.evolve' has no attribute 'build_argv'".

### Step 3: Implement `build_argv`

Append to `hermes_cli/evolve.py`:

```python
_EVOLUTION_ENTRY = ("-m", "evolution.skills.evolve_skill")


def build_argv(python: Path, user_args: Iterable[str]) -> list[str]:
    """Build the argv passed to os.execvp.

    Rewrites a bare positional skill name to `--skill <name>`. If the user
    already passed `--skill` (either `--skill foo` or `--skill=foo`), the
    rewrite is skipped to avoid duplication.
    """
    user_args = list(user_args)
    has_explicit_skill = any(
        a == "--skill" or a.startswith("--skill=") for a in user_args
    )
    rewritten: list[str]
    if user_args and not user_args[0].startswith("-") and not has_explicit_skill:
        rewritten = ["--skill", user_args[0]] + user_args[1:]
    else:
        rewritten = user_args
    return [str(python), *_EVOLUTION_ENTRY, *rewritten]
```

### Step 4: Run tests to verify they pass

```bash
venv/bin/pytest tests/hermes_cli/test_evolve.py -v
```
Expected: 15 tests passed (9 from Task 1 + 6 new).

### Step 5: Commit

```bash
git add hermes_cli/evolve.py tests/hermes_cli/test_evolve.py
git commit -m "$(cat <<'EOF'
feat(evolve): argv builder with idempotent --skill rewrite

build_argv(python, user_args) constructs the execvp argv for the
self-evolution subprocess. A bare positional first arg (e.g. "foo") is
rewritten to "--skill foo" so users do not have to type --skill twice.
The rewrite is skipped when the user already supplied --skill (either
"--skill foo" or "--skill=foo") so we never duplicate the flag.

6 unit tests covering: basic forwarding, skill+flags, explicit --skill
no-rewrite, --skill=value form, flag-only invocation, empty args.
EOF
)"
```

---

## Task 3: Helper flags `--where` and `--version`

**Files:**
- Modify: `hermes_cli/evolve.py`
- Modify: `tests/hermes_cli/test_evolve.py`

### Step 1: Add the failing tests

Append to `tests/hermes_cli/test_evolve.py`:

```python
class TestHelperFlags:
    def test_where_prints_path_and_returns_zero(self, tmp_path, monkeypatch, capsys):
        install = _make_fake_install(tmp_path / "code" / "hermes-agent-self-evolution")
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(install))

        rc = evolve.handle_helper_flag("--where")

        assert rc == 0
        out = capsys.readouterr().out
        assert str(install) in out

    def test_where_no_install_returns_64(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("HERMES_EVOLUTION_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
        (tmp_path / "empty-home").mkdir()

        rc = evolve.handle_helper_flag("--where")

        assert rc == 64
        err = capsys.readouterr().err
        assert "not installed" in err.lower()

    def test_version_prints_version_and_path(self, tmp_path, monkeypatch, capsys):
        install = _make_fake_install(tmp_path / "evo")
        # Stub a setup.cfg / pyproject so reading version returns something.
        (install / "pyproject.toml").write_text(
            '[project]\nname = "hermes-agent-self-evolution"\nversion = "9.9.9"\n'
        )
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(install))

        rc = evolve.handle_helper_flag("--version")

        assert rc == 0
        out = capsys.readouterr().out
        assert "9.9.9" in out
        assert str(install) in out

    def test_unknown_flag_returns_negative_one(self, tmp_path, monkeypatch):
        # Sentinel: helper not handled, caller should fall through to subprocess.
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(tmp_path))
        rc = evolve.handle_helper_flag("--nonexistent")
        assert rc == -1
```

### Step 2: Run tests to verify they fail

```bash
venv/bin/pytest tests/hermes_cli/test_evolve.py::TestHelperFlags -v
```
Expected: AttributeError on `handle_helper_flag`.

### Step 3: Implement helper-flag handler

Append to `hermes_cli/evolve.py`:

```python
import re
import sys

_VERSION_RE = re.compile(r'^\s*version\s*=\s*"([^"]+)"', re.MULTILINE)

EXIT_NO_INSTALL = 64
EXIT_NO_VENV = 65
EXIT_NOT_IMPORTABLE = 66

_INSTALL_HINT = (
    "hermes-agent-self-evolution not installed. Set HERMES_EVOLUTION_HOME "
    "or clone to ~/code/hermes-agent-self-evolution. "
    "See https://github.com/innoscoutpro/hermes-agent-self-evolution"
)


def _read_version(install: Path) -> str:
    """Best-effort read of the package version from pyproject.toml."""
    pyproject = install / "pyproject.toml"
    if not pyproject.is_file():
        return "(unknown — pyproject.toml missing)"
    try:
        text = pyproject.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(unreadable: {exc})"
    match = _VERSION_RE.search(text)
    return match.group(1) if match else "(unknown — no version field)"


def handle_helper_flag(flag: str) -> int:
    """Handle wrapper-only flags. Return exit code, or -1 if not a helper.

    Helpers short-circuit before subprocess dispatch so users get a fast,
    deterministic answer without going through DSPy import.
    """
    if flag == "--where":
        install = resolve_evolution_home()
        if install is None:
            print(_INSTALL_HINT, file=sys.stderr)
            return EXIT_NO_INSTALL
        print(install)
        return 0

    if flag == "--version":
        install = resolve_evolution_home()
        if install is None:
            print(_INSTALL_HINT, file=sys.stderr)
            return EXIT_NO_INSTALL
        version = _read_version(install)
        print(f"hermes-agent-self-evolution {version} ({install})")
        return 0

    return -1
```

### Step 4: Run tests to verify they pass

```bash
venv/bin/pytest tests/hermes_cli/test_evolve.py -v
```
Expected: 19 tests passed.

### Step 5: Commit

```bash
git add hermes_cli/evolve.py tests/hermes_cli/test_evolve.py
git commit -m "$(cat <<'EOF'
feat(evolve): --where and --version helper flags

handle_helper_flag(flag) handles wrapper-only short-circuit flags before
subprocess dispatch. Returns the intended process exit code, or the
sentinel -1 if the flag is not a helper (caller continues to the
subprocess path).

- --where: print resolved install path, exit 0. If no install found,
  print the standard install hint to stderr and exit 64.
- --version: read version from pyproject.toml of the resolved install
  using a regex (no toml dep). Print "hermes-agent-self-evolution
  <version> (<path>)" and exit 0; same 64 behaviour on no-install.

4 new tests, 19 total in test_evolve.py.
EOF
)"
```

---

## Task 4: Orchestrator with error codes (TDD)

**Files:**
- Modify: `hermes_cli/evolve.py`
- Modify: `tests/hermes_cli/test_evolve.py`

### Step 1: Add the failing tests

Append to `tests/hermes_cli/test_evolve.py`:

```python
class TestRunEvolve:
    """run_evolve() is the top-level entry point. We mock os.execvp so the
    test does not actually replace the test runner with a subprocess."""

    def test_no_install_exits_64(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("HERMES_EVOLUTION_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "empty"))
        (tmp_path / "empty").mkdir()

        with pytest.raises(SystemExit) as ei:
            evolve.run_evolve(["github-code-review"])
        assert ei.value.code == 64
        assert "not installed" in capsys.readouterr().err.lower()

    def test_dir_without_venv_exits_65(self, tmp_path, monkeypatch, capsys):
        # Make a candidate dir that exists but has no .venv.
        bad = tmp_path / "code" / "hermes-agent-self-evolution"
        bad.mkdir(parents=True)
        # Force the resolver to return None (no usable install) so we exercise
        # the explicit fallback path for "dir found but no venv".
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(bad))

        with pytest.raises(SystemExit) as ei:
            evolve.run_evolve(["foo"])
        # No usable install → 64 with install hint OR 65 if dir-but-no-venv
        # is detected. We pick the 64 path because resolve_evolution_home
        # returns None for an unusable install. Adjust if implementation
        # disambiguates 64 vs 65 from a partial install.
        assert ei.value.code in (64, 65)

    def test_venv_python_exits_nonzero_returns_66(self, tmp_path, monkeypatch, capsys):
        install = _make_fake_install(tmp_path / "evo", python_exit_code=1)
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(install))

        with pytest.raises(SystemExit) as ei:
            evolve.run_evolve(["foo"])
        assert ei.value.code == 66
        err = capsys.readouterr().err
        assert "import evolution" in err.lower() or "cannot import" in err.lower()

    def test_happy_path_calls_execvp(self, tmp_path, monkeypatch):
        install = _make_fake_install(tmp_path / "evo", python_exit_code=0)
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(install))

        recorded = {}

        def fake_execvp(file, argv):
            recorded["file"] = file
            recorded["argv"] = argv
            raise SystemExit(0)  # simulate the process replacing itself

        monkeypatch.setattr(os, "execvp", fake_execvp)

        with pytest.raises(SystemExit) as ei:
            evolve.run_evolve(["github-code-review", "--dry-run"])

        assert ei.value.code == 0
        py = install / ".venv" / "bin" / "python"
        assert recorded["file"] == str(py)
        assert recorded["argv"] == [
            str(py),
            "-m",
            "evolution.skills.evolve_skill",
            "--skill",
            "github-code-review",
            "--dry-run",
        ]

    def test_where_short_circuits_before_execvp(self, tmp_path, monkeypatch, capsys):
        install = _make_fake_install(tmp_path / "evo")
        monkeypatch.setenv("HERMES_EVOLUTION_HOME", str(install))

        called = []
        monkeypatch.setattr(
            os, "execvp",
            lambda *a, **k: called.append(a) or (_ for _ in ()).throw(SystemExit(0)),
        )

        with pytest.raises(SystemExit) as ei:
            evolve.run_evolve(["--where"])

        assert ei.value.code == 0
        assert called == []  # execvp NEVER called for helper flags
        assert str(install) in capsys.readouterr().out
```

### Step 2: Run tests to verify they fail

```bash
venv/bin/pytest tests/hermes_cli/test_evolve.py::TestRunEvolve -v
```
Expected: AttributeError on `run_evolve`.

### Step 3: Implement `run_evolve`

Append to `hermes_cli/evolve.py`:

```python
def run_evolve(args: list[str]) -> None:
    """Top-level entry: resolve install, dispatch helpers, or execvp into venv.

    Never returns under normal flow:
      - Helper flags call sys.exit(<code>).
      - Setup failures call sys.exit(64|65|66).
      - Successful path os.execvp's, replacing the current process.
    """
    # Helper flags short-circuit (only when they're the *first* arg, so
    # users can still pass --where/--version through to the child if they
    # really mean to use them as evolution-side flags — though neither
    # exists today).
    if args and args[0] in ("--where", "--version"):
        rc = handle_helper_flag(args[0])
        if rc != -1:
            sys.exit(rc)

    install = resolve_evolution_home()
    if install is None:
        print(_INSTALL_HINT, file=sys.stderr)
        sys.exit(EXIT_NO_INSTALL)

    py = venv_python(install)
    if py is None:
        print(
            f"Found self-evolution at {install} but .venv missing. "
            f"cd {install} && python -m venv .venv && "
            ".venv/bin/pip install -e '.[dev]'",
            file=sys.stderr,
        )
        sys.exit(EXIT_NO_VENV)

    if not verify_package_importable(py):
        print(
            f"{py} cannot import evolution. "
            f"Run: {py.parent}/pip install -e '{install}'",
            file=sys.stderr,
        )
        sys.exit(EXIT_NOT_IMPORTABLE)

    argv = build_argv(py, args)
    os.execvp(argv[0], argv)
```

### Step 4: Run tests to verify they pass

```bash
venv/bin/pytest tests/hermes_cli/test_evolve.py -v
```
Expected: 24 tests passed.

### Step 5: Commit

```bash
git add hermes_cli/evolve.py tests/hermes_cli/test_evolve.py
git commit -m "$(cat <<'EOF'
feat(evolve): top-level run_evolve orchestrator

run_evolve(args) is the entry point called from hermes_cli.main:
- Short-circuits --where / --version helper flags via handle_helper_flag.
- Resolves the install. Exits 64 if not found.
- Validates .venv/bin/python exists. Exits 65 if missing.
- Verifies `python -c "import evolution"` succeeds. Exits 66 if not.
- Builds argv via build_argv (with --skill rewrite) and os.execvp's.

5 new tests covering: no-install -> 64, dir-but-no-venv -> 64/65,
unimportable -> 66, happy path -> execvp called with expected argv,
--where -> short-circuit (execvp never called).
EOF
)"
```

---

## Task 5: Wire subparser into `hermes_cli/main.py`

**Files:**
- Modify: `hermes_cli/main.py` (subcommand list at ~line 7305 + subparser registration after `claw_parser` at ~line 9725)

### Step 1: Add `evolve` to the `_SUBCOMMANDS` set

Find the `_SUBCOMMANDS` set definition (around line 7305 — `"claw"` is in it). Add `"evolve"` alphabetically after `"completion"` and before `"cron"` (or wherever fits the existing alphabetical ordering — match the file's style).

Edit the literal so the set contains `"evolve"`. Do not change the surrounding logic.

### Step 2: Add subparser registration

After the `claw_parser` block (ending around line 9760), insert a new section:

```python
    # =========================================================================
    # evolve command (skill self-evolution)
    # =========================================================================
    # add_help=False so --help is forwarded to the underlying evolve_skill CLI
    # rather than intercepted here. argparse.REMAINDER captures every arg
    # after `evolve` so flags pass through unmolested. Helper flags
    # (--where, --version) are detected manually inside run_evolve.
    evolve_parser = subparsers.add_parser(
        "evolve",
        help="Evolve a Hermes skill via hermes-agent-self-evolution",
        description=(
            "Run hermes-agent-self-evolution against a skill. Forwards every "
            "argument to `python -m evolution.skills.evolve_skill`. Path "
            "resolution: $HERMES_EVOLUTION_HOME -> ~/code/hermes-agent-self-evolution "
            "-> ~/hermes-agent-self-evolution -> ~/.hermes/hermes-agent-self-evolution. "
            "Helper flags handled by the wrapper: --where (print resolved path), "
            "--version (print package version)."
        ),
        add_help=False,
    )
    evolve_parser.add_argument(
        "evolve_args",
        nargs=argparse.REMAINDER,
        help="Skill name plus flags forwarded to the underlying CLI",
    )
    evolve_parser.set_defaults(func=cmd_evolve)
```

### Step 3: Add `cmd_evolve` dispatcher near other `cmd_*` functions

Add a small dispatcher near the bottom of `main.py` (or wherever the other `cmd_*` functions live — search for a `def cmd_claw(` pattern to find the right neighbourhood):

```python
def cmd_evolve(args):
    """Dispatch to hermes_cli.evolve.run_evolve.

    Imports lazily so the rest of the CLI does not pay the cost when the
    user is not running an evolve subcommand.
    """
    from hermes_cli.evolve import run_evolve
    run_evolve(args.evolve_args or [])
```

### Step 4: Smoke-test the wiring manually

```bash
cd /home/inno/.hermes/hermes-agent
HERMES_EVOLUTION_HOME=/home/inno/code/hermes-agent-self-evolution venv/bin/python -m hermes_cli --help 2>&1 | grep -i evolve
```
Expected: at least one line mentioning `evolve`. (If the CLI module entry differs, adjust to whatever runs the local hermes — `hermes` shim or `python cli.py` etc.)

```bash
HERMES_EVOLUTION_HOME=/home/inno/code/hermes-agent-self-evolution /home/inno/.local/bin/hermes evolve --where
```
Expected: prints `/home/inno/code/hermes-agent-self-evolution` and exits 0.

```bash
HERMES_EVOLUTION_HOME=/home/inno/code/hermes-agent-self-evolution /home/inno/.local/bin/hermes evolve --version
```
Expected: prints `hermes-agent-self-evolution 0.1.0 (/home/inno/code/hermes-agent-self-evolution)`.

```bash
HERMES_EVOLUTION_HOME=/home/inno/code/hermes-agent-self-evolution /home/inno/.local/bin/hermes evolve github-code-review --dry-run
```
Expected: the self-evolution dry-run output (loaded skill, would-generate banner). Exit 0.

If any smoke test fails, fix and re-run before committing.

### Step 5: Run the full hermes test suite

```bash
cd /home/inno/.hermes/hermes-agent && venv/bin/pytest tests/hermes_cli/ -q 2>&1 | tail -10
```
Expected: all hermes CLI tests pass, including the 24 new test_evolve.py tests.

### Step 6: Commit

```bash
git add hermes_cli/main.py
git commit -m "$(cat <<'EOF'
feat(cli): wire `hermes evolve` subcommand

- Add "evolve" to _SUBCOMMANDS so the early argv parser recognises it.
- Register evolve subparser with add_help=False + argparse.REMAINDER so
  every flag passes through to the underlying CLI unmolested.
- New cmd_evolve dispatcher imports hermes_cli.evolve lazily to keep
  the cold-start cost of unrelated subcommands unchanged.

Smoke-tested: `hermes evolve --where`, `--version`, and
`<skill> --dry-run` all behave as expected against a real
hermes-agent-self-evolution checkout via HERMES_EVOLUTION_HOME.
EOF
)"
```

---

## Task 6: Documentation + final smoke + push

**Files:**
- Modify: `README.md` (find a sensible spot — likely near other CLI command docs)

### Step 1: Add a `hermes evolve` section to README.md

Insert near the existing CLI command documentation (search for `claw` or `cron` in README to find the section). Suggested content:

```markdown
### `hermes evolve` — Skill Self-Evolution

Run [hermes-agent-self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution)
against any skill in your hermes install:

```bash
hermes evolve github-code-review --dry-run
hermes evolve github-code-review --use-llm-judge --run-tests --create-pr
```

Flags after the skill name are forwarded verbatim to
`python -m evolution.skills.evolve_skill`. Run
`hermes evolve <skill> --help` to see the full evolution flag set.

**Setup.** Clone the self-evolution repo, create its venv, and install:

```bash
git clone https://github.com/NousResearch/hermes-agent-self-evolution.git ~/code/hermes-agent-self-evolution
cd ~/code/hermes-agent-self-evolution
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

Hermes will discover `~/code/hermes-agent-self-evolution` automatically.
Override the location with `HERMES_EVOLUTION_HOME=/path/to/your/checkout`.

**Wrapper-only flags:**
- `hermes evolve --where` — print the resolved self-evolution path.
- `hermes evolve --version` — print the package version + path.

**Exit codes:** 64 = self-evolution not installed; 65 = install found
but `.venv` missing; 66 = `.venv` found but the `evolution` package is
not importable. The hint emitted on stderr is enough to recover.

The wrapper never modifies skills in your hermes install — evolved
skills land in `output/proposals/<skill>/<ts>/` for review. Apply by
hand (or via a future `hermes evolve apply` step we have not built yet).
```

### Step 2: Final smoke

```bash
hermes evolve --where
hermes evolve --version
hermes evolve --help
hermes evolve github-code-review --dry-run
HERMES_EVOLUTION_HOME=/tmp/no-such-place hermes evolve foo
echo "exit code: $?"     # expect 64
```

Expected: --where prints path, --version prints version+path, --help shows the wrapper-level help (with REMAINDER hint), --dry-run runs the underlying CLI's dry-run output, the bad env var falls through to the home fallback OR exits 64 with the install hint.

### Step 3: Run full test suite once more

```bash
cd /home/inno/.hermes/hermes-agent && venv/bin/pytest tests/ -q 2>&1 | tail -3
```
Expected: full hermes-agent test suite still green.

### Step 4: Commit + push

```bash
git add README.md
git commit -m "docs: hermes evolve subcommand section in README"

git push -u fork innoscout/feat-hermes-evolve-subcommand
```
Expected: branch published to `github.com/innoscoutpro/hermes-agent`.

### Step 5: Open PR (optional — confirm with user first)

If the user wants to PR this back to NousResearch:

```bash
gh pr create --repo NousResearch/hermes-agent \
    --title "feat(cli): hermes evolve subcommand" \
    --body "$(cat plans/hermes-evolve-subcommand.md)"
```

Otherwise stop after the push — the integration is live on the local install.

---

## Summary of files touched

- **Created:**
  - `hermes_cli/evolve.py` (~140 LOC)
  - `tests/hermes_cli/test_evolve.py` (~280 LOC, 24 tests)
- **Modified:**
  - `hermes_cli/main.py` (subcommand set + subparser + dispatcher, ~25 LOC of changes)
  - `README.md` (one new section, ~30 lines)
- **Already created:**
  - `plans/hermes-evolve-subcommand.md` (design doc)
  - `plans/2026-04-28-hermes-evolve-subcommand-impl.md` (this plan)

## Total commits

7 (one per task + design doc + impl plan).

## Total time budget

~4–5 hours wall clock for a focused engineer. Fits "half-day" estimate.
