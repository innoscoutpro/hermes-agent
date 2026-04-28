# Hermes Agent Fork — Delivery Backlog

Local delivery backlog for the `innoscoutpro/hermes-agent` fork. The
upstream `NousResearch/hermes-agent` repo uses GitHub Issues + PRs; this
backlog tracks the integration work and follow-ups that originate from
this fork.

See [`BACKLOG-INSTRUCTIONS.md`](BACKLOG-INSTRUCTIONS.md) for the
operating manual.

---

## Quick Reference

| Status | Count |
|--------|-------|
| ⬜ Todo (`01-not-started/`) | 0 |
| 🔄 In Progress (`02-in-progress/`) | 1 |
| ✅ Done (`03-completed/`) | 0 |
| ❌ Dropped / ⚠️ MVP / 🔒 Restricted (`04-parked/`) | 0 |

---

## Dependency Graph

### Wave 0 — CLI Integration

- 🔄 [PBI-001 — `hermes evolve` subcommand](02-in-progress/PBI-001-hermes-evolve-subcommand/prd.md)
  — first-class CLI wrapper that subprocess-dispatches into the
  `hermes-agent-self-evolution` package's venv. Tasks 1–5 of 6 done +
  path migration; Task 6 (README + push) remaining.

---

## Notes

- The historical upstream-style `plans/` directory is preserved at the
  repo root. PBIs in this backlog reference design + implementation
  plan documents from `plans/` rather than duplicating them.
- Numbering: PBI-0xx is CLI integration / `hermes_cli/` wiring. See the
  table in [`BACKLOG-INSTRUCTIONS.md`](BACKLOG-INSTRUCTIONS.md#numbering-convention).
