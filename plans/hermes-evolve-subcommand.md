# `hermes evolve` Subcommand — Design Document

**Date:** 2026-04-28
**Status:** Approved, ready for implementation
**Scope:** Minimal (option A) — thin subprocess wrapper, no reviewer workflow

## Goal

Wire the `hermes-agent-self-evolution` package into the local hermes CLI as a
first-class `hermes evolve` subcommand. Today users run
`python -m evolution.skills.evolve_skill --skill <name>` from inside the
self-evolution venv; afterwards they will run `hermes evolve <skill>` from
anywhere.

Out of scope (deferred): reviewer workflow (`hermes evolve list/show/apply/
reject`), plugin hooks, in-process import. Those were considered as options
B and C in brainstorming and rejected for this iteration in favour of the
smallest viable change.

## Architecture

`hermes evolve` is a transparent subprocess wrapper. The subcommand lives
inside the hermes-agent fork; the self-evolution package stays untouched
in its own repo and venv.

```
~/.hermes/hermes-agent/                  ~/code/hermes-agent-self-evolution/
├── hermes_cli/                          ├── evolution/skills/evolve_skill.py
│   ├── main.py        ◄── new ───────► │   (existing CLI entry point)
│   │   subparser:                       │
│   │   "evolve"          spawns         ├── .venv/
│   │     │              ──────►         │   └── bin/python
│   │     ▼                              └── ...
│   └── evolve.py    (new, ~80 LOC)
└── venv/  (no new deps)
```

Two venvs stay decoupled. The self-evolution venv carries `dspy[optuna]`,
`litellm`, `optuna`, etc.; hermes' venv stays as it is. Self-evolution can
churn its dependency tree without dragging hermes along.

## CLI surface

The wrapper is intentionally transparent — anything after `evolve` is
forwarded verbatim to `python -m evolution.skills.evolve_skill`:

```
hermes evolve <skill>                                        # synthetic eval, deterministic metric
hermes evolve <skill> --use-llm-judge --run-tests --create-pr
hermes evolve <skill> --eval-source sessiondb --consent-external-ingest
```

Two helper flags handled by the wrapper itself (not forwarded):

- `hermes evolve --where` — print the resolved self-evolution path, exit 0,
  never spawn the child. Quick debug for "is it pointing where I think it
  is?"
- `hermes evolve --version` — print the self-evolution package version
  alongside the resolved path, exit 0.

The bare `<skill>` positional is rewritten to `--skill <skill>` before
forwarding so users don't have to type `--skill` twice. If the user passed
`--skill` themselves, the rewrite is skipped.

`hermes evolve --help` prints the wrapper-level help (path resolution
order, env vars, helper flags). For full evolution flags users run
`hermes evolve <skill> --help` which forwards to the underlying CLI.

## Path resolution

First hit wins:

1. `$HERMES_EVOLUTION_HOME` env var (if set and exists).
2. `~/code/hermes-agent-self-evolution`.
3. `~/hermes-agent-self-evolution`.
4. Sibling of `~/.hermes/hermes-agent` → `~/.hermes/hermes-agent-self-evolution`.

For each candidate the resolver checks both **the directory exists** AND
`<path>/.venv/bin/python` is executable. A candidate that fails either
check is skipped.

After resolution, a fast `<py> -c "import evolution"` (~150 ms) verifies
the package is actually installed in that venv. This catches half-set-up
installs before users wait through the longer Rich-console startup.

## Error handling — distinct exit codes

| Code | Condition | Stderr message |
|------|-----------|----------------|
| 0    | success / forwarded child exit | (passes through) |
| 64   | no candidate path exists | `hermes-agent-self-evolution not installed. Set HERMES_EVOLUTION_HOME or clone to ~/code/hermes-agent-self-evolution. See https://github.com/innoscoutpro/hermes-agent-self-evolution` |
| 65   | dir exists, no `.venv/bin/python` | `Found self-evolution at <path> but .venv missing. cd <path> && python -m venv .venv && .venv/bin/pip install -e '.[dev]'` |
| 66   | venv exists, `import evolution` fails | `<path>/.venv/bin/python cannot import evolution. Run: <path>/.venv/bin/pip install -e '<path>'` |
| (child) | subprocess exit | propagated unchanged |

Codes 64–66 are chosen to mirror sysexits.h conventions
(`EX_USAGE`/`EX_DATAERR`/`EX_NOINPUT`).

## Process model

`os.execvp` (not `subprocess.run`). The child inherits stdin/stdout/stderr
directly so the user sees the Rich console output unchanged, signal
forwarding (Ctrl+C) is automatic, and we don't waste a parent process.
After `execvp`, the wrapper code is gone — exit code is whatever the child
exits with.

The `--where` and `--version` helper flags short-circuit before `execvp`,
because they don't need to launch evolution at all.

## Components

### `hermes_cli/evolve.py` (new, ~80 LOC)

Pure-function module containing:

```python
def resolve_evolution_home() -> Path | None: ...
def venv_python(home: Path) -> Path | None: ...
def verify_package_importable(py: Path) -> bool: ...
def build_argv(home: Path, user_args: list[str]) -> list[str]: ...
def run_evolve(user_args: list[str]) -> NoReturn:  # execvp's
    ...
```

Each is testable in isolation. `run_evolve` is the only one that calls
`os.execvp`; tests replace it with a recorder.

### `hermes_cli/main.py` patch

Single new subparser registration alongside the existing ones (e.g. near
the `claw` subparser at line ~6227). Routes to `evolve.run_evolve` with
`parser.parse_known_args` so the unrecognised flags pass through to the
forwarded child rather than being rejected by argparse.

### Skill-name rewrite logic

```
user typed:  hermes evolve foo --bar
forwarded:   --skill foo --bar

user typed:  hermes evolve --skill foo --bar
forwarded:   --skill foo --bar     (no rewrite, since --skill already present)

user typed:  hermes evolve --where
forwarded:   nothing — short-circuit prints path + exits
```

## Testing

`tests/hermes_cli/test_evolve.py` (matches existing test layout under
`tests/hermes_cli/`).

| Test | Asserts |
|------|---------|
| `test_resolves_env_var_first` | `HERMES_EVOLUTION_HOME=<tmp>` (with fake `.venv/bin/python`) wins over defaults |
| `test_resolves_home_fallback` | env unset → `~/code/hermes-agent-self-evolution` if it exists |
| `test_missing_install_exits_64` | no candidate → exit 64, install hint in stderr |
| `test_missing_venv_exits_65` | dir found but no `.venv/bin/python` → exit 65 |
| `test_unimportable_package_exits_66` | venv exists but `import evolution` fails → exit 66 |
| `test_argv_forwarding` | `hermes evolve foo --bar --baz=qux` builds `[<py>, -m, evolution.skills.evolve_skill, --skill, foo, --bar, --baz=qux]` |
| `test_where_flag_no_subprocess` | `hermes evolve --where` prints path, exits 0, never `execvp`s |
| `test_version_flag` | `hermes evolve --version` reads version from resolved package, exits 0 |
| `test_skill_arg_rewrite_idempotent` | bare `<skill>` becomes `--skill <skill>` exactly once; not duplicated when user already typed `--skill` |

Test fixtures use `tmp_path` to fabricate fake self-evolution directories
with stub `.venv/bin/python` shell scripts that exit known codes. No real
Python interpreter spawned; resolver and argv builder are pure functions;
`execvp` is mocked. Target ≤1 s combined runtime.

## Documentation

- New section in hermes-agent's `README.md` (or wherever subcommands are
  documented) covering the `evolve` subcommand, env var, install
  prerequisite.
- `hermes evolve --help` self-documents path resolution and helper flags.
- Cross-link from the self-evolution `README.md` integration section to
  the `hermes evolve` invocation as the "preferred way to run from a
  hermes install".

## Non-goals

- No reviewer workflow. Proposals stay where the self-evolution package
  writes them today; user inspects and copies by hand.
- No plugin hook integration. The slash-command surface (`/evolve` in
  chat sessions) is deliberately deferred.
- No automatic discovery of which skill to evolve. User picks the skill
  name explicitly.
- No nightly cron / automation. That was option (1) in our menu and is
  separate from this option-(A) integration.
- No deps changes to hermes-agent's `pyproject.toml`. The wrapper uses
  only `os`, `pathlib`, `argparse`, and `subprocess` — all stdlib.

## Push target

Implementation lands on the hermes-agent fork (`fork →
github.com/innoscoutpro/hermes-agent`). Branch:
`innoscout/feat-hermes-evolve-subcommand`. Whether to PR upstream to
NousResearch is a follow-up decision; not blocking the local install.

## Time estimate

Half-day, including tests and README. The wrapper is ~80 LOC of pure
Python and ~9 unit tests with no real subprocess invocation.
