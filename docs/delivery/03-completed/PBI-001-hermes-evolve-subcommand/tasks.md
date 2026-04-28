# PBI-001: `hermes evolve` Subcommand — Tasks

## Brainstorming + Design

- [x] Inventory existing CLI structure (`hermes_cli/main.py`,
  subparser pattern at line ~9725, `_SUBCOMMANDS` set at line ~7305,
  plugin system in `plugins/`).
- [x] Confirm fork has write access (remotes: `fork →
  innoscoutpro/hermes-agent`, `forgejo` private, `origin →
  NousResearch`).
- [x] Choose scope: A (minimal subprocess wrapper). B (full reviewer
  workflow) and C (plugin hooks) deferred.
- [x] Choose dispatch mechanism: A (subprocess into self-evolution
  venv). B (in-process import) rejected due to dep bloat.
- [x] Write design doc → `plans/hermes-evolve-subcommand.md`.
- [x] Write implementation plan →
  `plans/2026-04-28-hermes-evolve-subcommand-impl.md`.
- [x] Commit design + impl plan to feature branch.

## Implementation (TDD)

- [x] Task 1: `resolve_evolution_home` + `venv_python` +
  `verify_package_importable` (10 tests, then code-review fixes for
  `Path.home()` and dedup → +1 test).
- [x] Task 2: `build_argv` with idempotent `--skill` rewrite (6 tests).
- [x] Task 3: `--where` and `--version` helper flags
  (`handle_helper_flag`) + `_read_version` regex parse of pyproject.toml
  (4 tests).
- [x] Task 4: `run_evolve` orchestrator with distinct exit codes
  (5 tests + 1 follow-up: symmetric `--version` short-circuit test).
- [x] Task 4 follow-up: HOME isolation in TestRunEvolve fixtures
  (caught + fixed when un-mocked `os.execvp` clobbered the pytest
  worker on a machine with a real install at a fallback path).
- [x] Task 5: Wire subparser into `hermes_cli/main.py` (`_SUBCOMMANDS`
  entry, subparser registration with `add_help=False` + REMAINDER,
  `cmd_evolve` dispatcher, plus an early-intercept block that bypasses
  argparse for the `evolve` subcommand because `argparse.REMAINDER`
  does not in fact capture leading `--flags` cleanly).
- [x] Path migration: relocated self-evolution checkout from
  `~/code/hermes-agent-self-evolution` to
  `~/Code/hermes-agent-self-evolution` (capital C — matches user's
  workspace convention). Recreated venv (.venv shebangs were baked to
  the old absolute path). Updated resolver to check `~/Code/` first,
  with `~/code/` retained as a portability fallback.

## Documentation

- [x] Add a `hermes evolve` section to repo `README.md` documenting
  the subcommand, the `HERMES_EVOLUTION_HOME` env var, the path
  resolution order, the wrapper-only flags (`--where` / `--version`),
  the exit codes (64 / 65 / 66), and the install prerequisite
  (`git clone … ~/Code/hermes-agent-self-evolution && cd … &&
  python -m venv .venv && .venv/bin/pip install -e '.[dev]'`).
- [x] Cross-link from `plans/` design doc to this PBI.

## Verification

- [x] All 29 unit tests in `tests/hermes_cli/test_evolve.py` pass.
- [x] Smoke `hermes evolve --where` returns the resolved path
  (currently `/home/inno/Code/hermes-agent-self-evolution`).
- [x] Smoke `hermes evolve --version` returns
  `hermes-agent-self-evolution 0.1.0 (<path>)`.
- [x] Smoke `hermes evolve github-code-review --dry-run` produces the
  underlying CLI's dry-run banner ("Loaded ... DRY RUN — setup
  validated successfully").
- [x] Branch pushed to `fork (innoscoutpro/hermes-agent)` →
  https://github.com/innoscoutpro/hermes-agent/pull/new/innoscout/feat-hermes-evolve-subcommand
- [ ] (Optional) PR opened against `origin (NousResearch/hermes-agent)`
  — deferred, decision left to operator.

## Final Code Review

- [ ] Dispatch a final code-review subagent over the full diff range
  (`origin/main..innoscout/feat-hermes-evolve-subcommand`) — deferred,
  decision left to operator. Each task already had spec + quality
  reviews during subagent-driven implementation.

---

## Metadata

| Field | Value |
|-------|-------|
| PBI-ID | PBI-001 |
| Wave | 0 — CLI Integration |
| Priority | P2 |
| Status | ✅ Done |
| Date | 2026-04-28 |
| Updated | 2026-04-28 |
| Reporter | Dmitry (innoscoutpro) |
| Branch | `innoscout/feat-hermes-evolve-subcommand` |
| Related | upstream issue NousResearch/hermes-agent-self-evolution#18 |
