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

    def test_returns_none_when_python_not_executable(self, tmp_path):
        install = _make_fake_install(tmp_path)
        py = install / ".venv" / "bin" / "python"
        py.chmod(0o644)  # strip exec bit
        assert evolve.venv_python(install) is None


class TestVerifyPackageImportable:
    def test_true_when_python_exits_zero(self, tmp_path):
        install = _make_fake_install(tmp_path, python_exit_code=0)
        py = evolve.venv_python(install)
        assert evolve.verify_package_importable(py) is True

    def test_false_when_python_exits_nonzero(self, tmp_path):
        install = _make_fake_install(tmp_path, python_exit_code=1)
        py = evolve.venv_python(install)
        assert evolve.verify_package_importable(py) is False
