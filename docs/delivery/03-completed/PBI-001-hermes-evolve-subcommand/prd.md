# PBI-001: `hermes evolve` Subcommand

## Problem

`hermes-agent-self-evolution` is a separate Python package that lives in
its own checkout with its own venv. Today, running it requires the user
to:

1. Know where the checkout lives (`~/Code/hermes-agent-self-evolution`).
2. Manually activate that venv (`. .venv/bin/activate`).
3. Run `python -m evolution.skills.evolve_skill --skill <name> ...`.

There is zero CLI integration with the running `hermes` binary. The
"is the self-evolution project integrated into hermes-agent?" question
in upstream Issue #18 has no first-class answer beyond "they discover
each other by convention."

## Why it matters

- **Discoverability.** Users who installed hermes via the standard
  installer have no signal that self-evolution exists or where to
  invoke it.
- **Friction.** Manual venv activation + remembering the entry-module
  path is enough overhead to deter opportunistic use during a
  debugging session.
- **Consistency.** Every other Hermes capability (claw, cron, gateway,
  acp) is reachable as `hermes <subcommand>`. Evolution should not be
  the lone exception.

## Design

A thin subprocess-dispatching wrapper at `hermes_cli/evolve.py`
registers an argparse subparser in `hermes_cli/main.py`. The wrapper:

1. Resolves the self-evolution install via `$HERMES_EVOLUTION_HOME` →
   `~/Code/hermes-agent-self-evolution` → `~/code/...` →
   `~/hermes-agent-self-evolution` → `~/.hermes/hermes-agent-self-evolution`.
2. Verifies `<install>/.venv/bin/python` exists and `import evolution`
   succeeds.
3. Builds argv with a bare positional skill name rewritten to
   `--skill <name>` (idempotent — no rewrite if user already typed
   `--skill`).
4. `os.execvp`s into the venv's python with all flags forwarded.

Two helper flags handled by the wrapper itself: `--where`, `--version`.
Distinct exit codes (64 / 65 / 66) for setup failures so users get
actionable messages without going through DSPy's slow startup.

Full design: [`plans/hermes-evolve-subcommand.md`](../../../../plans/hermes-evolve-subcommand.md)
Implementation plan: [`plans/2026-04-28-hermes-evolve-subcommand-impl.md`](../../../../plans/2026-04-28-hermes-evolve-subcommand-impl.md)

## Files

- `hermes_cli/evolve.py` (new, ~140 LOC)
- `tests/hermes_cli/test_evolve.py` (new, 29 tests)
- `hermes_cli/main.py` (modified — `_SUBCOMMANDS` set, subparser
  registration, `cmd_evolve` dispatcher, early `evolve` intercept that
  bypasses argparse so leading `--flags` reach the child)
- `plans/hermes-evolve-subcommand.md` (design doc, this PBI)
- `plans/2026-04-28-hermes-evolve-subcommand-impl.md` (impl plan, this PBI)
- `README.md` (pending — Task 6)

## Acceptance Criteria

- [x] `hermes evolve --where` prints the resolved install path, exit 0.
  When no install is found, prints install hint to stderr and exits 64.
- [x] `hermes evolve --version` prints
  `hermes-agent-self-evolution <version> (<path>)`, exit 0. Same 64
  behaviour on no-install.
- [x] `hermes evolve <skill>` rewrites bare `<skill>` to
  `--skill <skill>`. Idempotent — does not duplicate when user already
  passed `--skill foo` or `--skill=foo`.
- [x] `hermes evolve <skill> --dry-run` runs the underlying CLI's
  dry-run output unchanged.
- [x] `hermes evolve --help` shows wrapper-level help; `hermes evolve
  <skill> --help` forwards to underlying CLI.
- [x] Distinct exit codes: 64 = no install; 65 = install but no
  `.venv/bin/python`; 66 = venv exists but `import evolution` fails.
- [x] Resolver checks `~/Code/` (capital C) before `~/code/` (lowercase).
- [x] `os.execvp` is used (not `subprocess.run`) so signal forwarding
  and stdout/stderr inheritance are kernel-default.
- [x] Skill name input is rejected if it contains path separators or
  shell metacharacters (defence-in-depth — the underlying resolver
  already enforces this in `evolution/skills/skill_module.py`).
- [x] All 29 unit tests pass; 12 pre-existing hermes_cli failures
  unrelated to this work remain unchanged.
- [x] `README.md` documents the subcommand, the env var, and the
  install prerequisite (new section "Skill Self-Evolution (fork
  addition)" between "Migrating from OpenClaw" and "Contributing").
- [x] Branch `innoscout/feat-hermes-evolve-subcommand` pushed to
  `fork (innoscoutpro/hermes-agent)` — see
  https://github.com/innoscoutpro/hermes-agent/pull/new/innoscout/feat-hermes-evolve-subcommand

## Non-goals

- **Reviewer workflow.** `hermes evolve list/show/apply/reject` is
  out of scope for this PBI. Future PBI if value warrants it.
- **Plugin / slash-command integration.** Adding `/evolve` as a chat
  slash command is deferred to a future PBI.
- **Automatic deployment.** The wrapper never modifies skills in the
  hermes install. Evolved skills land in
  `output/proposals/<skill>/<ts>/` for manual review (proposal
  workflow lives in `hermes-agent-self-evolution`, not here).
- **Deps changes.** No new runtime deps in `pyproject.toml`. Wrapper
  uses only stdlib (`os`, `pathlib`, `argparse`, `subprocess`).
- **Upstream PR.** Whether to PR this back to NousResearch is a
  follow-up decision; not blocking on this PBI's `DONE`.
