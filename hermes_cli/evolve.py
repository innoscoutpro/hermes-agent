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


_EVOLUTION_ENTRY = ("-m", "evolution.skills.evolve_skill")


# Path resolution candidates, in priority order. Each callable receives the
# evaluated $HOME and returns a candidate Path. The env-var lookup is handled
# separately because it is highest priority and not relative to HOME.
_FALLBACK_CANDIDATES = (
    lambda home: home / "code" / "hermes-agent-self-evolution",
    lambda home: home / "hermes-agent-self-evolution",
    lambda home: home / ".hermes" / "hermes-agent-self-evolution",
)


def venv_python(install: Path) -> Optional[Path]:
    """Return the venv's python executable path, or None if missing."""
    py = install / ".venv" / "bin" / "python"
    if py.is_file() and os.access(py, os.X_OK):
        return py
    return None


def _has_venv_python(candidate: Path) -> bool:
    """A candidate path is usable iff it contains an executable .venv/bin/python."""
    return venv_python(candidate) is not None


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

    try:
        home = Path.home()
    except RuntimeError:
        return None
    for build in _FALLBACK_CANDIDATES:
        candidate = build(home)
        if candidate.is_dir() and _has_venv_python(candidate):
            return candidate

    return None


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
        # OSError covers ENOENT / EACCES / EMFILE / ENOMEM — any failure to
        # invoke python at all means the install is unusable, which is the
        # False answer this probe produces.
        return False
    return result.returncode == 0


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
