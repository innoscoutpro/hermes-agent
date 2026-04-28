# Delivery Backlog — LLM Operating Instructions

> Operating manual for navigating and updating the Hermes Agent fork's
> delivery backlog. Adapted from the InnoScout ecosystem standard.

---

## Backlog Location

```
BACKLOG_ROOT = docs/delivery/
```

## Structure

PBI (Product Backlog Item) folders are organised into status buckets:

```
docs/delivery/
├── 01-not-started/          # ⬜ Todo — work not yet begun
│   └── PBI-XXX-slug/
├── 02-in-progress/          # 🔄 In Progress — actively being worked
│   └── PBI-XXX-slug/
├── 03-completed/            # ✅ Done — accepted
│   └── PBI-XXX-slug/
├── 04-parked/               # ❌ Dropped / 🔒 Restricted / ⚠️ MVP-Insecure
│   └── PBI-XXX-slug/
├── archive/                 # Frozen historical plans + superseded docs
├── README.md                # Index: dependency graph + quick reference
└── BACKLOG-INSTRUCTIONS.md  # This file
```

Each PBI folder contains exactly two files:

| File | Purpose |
|------|---------|
| `prd.md` | Product Requirements Document — context, problem, acceptance criteria |
| `tasks.md` | Implementation tasks (checkbox list) + metadata table |

Some PBIs in this fork additionally reference design / implementation plan
documents that live under `plans/<slug>.md` (the upstream Hermes Agent
convention). When that is the case, `prd.md` links to those docs. The
`plans/` directory predates the delivery backlog and is left intact so
that contributions can be cleanly proposed back to upstream.

## Navigating the Backlog

- **Start with `README.md`** — it has the dependency graph (all PBIs by
  wave, with status emoji) and a quick-reference summary.
- **Browse by status** — `ls 01-not-started/` to see what's queued,
  `ls 02-in-progress/` for active work.
- **Find a specific PBI** — `ls */PBI-XXX-*` or grep inside `README.md`.
- **Historical archive** — `archive/` preserves any superseded plans.
  Do not treat it as a current source of truth.

## Creating a New PBI

1. **Pick the next available ID** in the relevant range (see Numbering).
2. **Create the folder** in the correct status bucket (usually
   `01-not-started/`):
   ```
   mkdir -p docs/delivery/01-not-started/PBI-XXX-short-slug/
   ```
3. **Create `prd.md`** with these mandatory sections:

   ```markdown
   # PBI-XXX: [Title]

   ## Problem
   [Why this work exists — what is broken, missing, or contradictory]

   ## Why it matters
   - [Bulleted impact — security, UX, drift, etc.]

   ## Files
   - [path/to/source]

   ## Acceptance Criteria
   - [ ] [Falsifiable criterion 1]
   - [ ] [Falsifiable criterion 2]
   ```

   Add **type-specific sections** as needed:

   | PBI Type | Extra Sections |
   |----------|---------------|
   | Security / Ops | Observed evidence, Attack scenario, Non-goals |
   | Production bug | Root causes, Delivered, Verified live evidence |
   | Architecture / Refactor | Decision required, Non-goals, Dependencies |
   | Content / Data | Decision required, Cleanup notes |
   | Dropped / Parked | Status badge + reason, Note |

4. **Create `tasks.md`** with a task checklist and metadata table:

   ```markdown
   # PBI-XXX: [Title] — Tasks

   ## [Phase Name, e.g. Investigation]
   - [ ] Task 1
   - [ ] Task 2

   ## [Phase Name, e.g. Implementation]
   - [ ] Task 3

   ## Verification
   - [ ] Live confirmation criterion

   ---

   ## Metadata

   | Field | Value |
   |-------|-------|
   | PBI-ID | PBI-XXX |
   | Wave | [wave number — description] |
   | Priority | P0 / P1 / P2 / P3 |
   | Status | ⬜ Todo |
   | Date | YYYY-MM-DD |
   ```

   **Metadata fields** — use what applies:

   | Field | When to Include | Example Values |
   |-------|----------------|----------------|
   | PBI-ID | Always | PBI-001, PBI-101 |
   | Wave | Always | 0 — Foundation, 1 — CLI integration |
   | Priority | Always | P0, P1, P2, P3 |
   | Status | Always | ⬜ Todo, 🔄 In Progress, ✅ Done, ❌ Dropped, ⚠️ MVP/Insecure |
   | Date | Always | 2026-04-28 |
   | Updated | When changed | 2026-04-28 |
   | Reporter | Optional | Dmitry |
   | Depends on | When blocked by another PBI | PBI-XXX |
   | Reason | Dropped / parked PBIs | Replaced by PBI-XXX |

5. **Add the PBI to `README.md`** — insert a line in the dependency
   graph under the correct wave, and update counts in the
   quick-reference section.

## Updating PBI Status

When a PBI changes status:

1. Move the folder to the new status bucket:
   ```
   mv docs/delivery/01-not-started/PBI-XXX-slug/ docs/delivery/02-in-progress/
   ```
2. **Update `tasks.md` metadata** — change the `Status` field and bump
   `Updated`.
3. **Update `README.md`** — change the status emoji on the PBI's line in
   the dependency graph, and adjust the counts in the quick-reference
   section.

All three must stay in sync.

## Numbering Convention

For this fork, ranges are organised by integration target rather than by
Palimpsest's content/UX/security domains:

| Range | Domain |
|-------|--------|
| PBI-0xx | CLI integration / hermes_cli wiring |
| PBI-1xx | Self-evolution package work (skills, fitness, constraints) |
| PBI-2xx | Plugin / hooks / slash-command surface |
| PBI-3xx | Security & dependency hygiene |
| PBI-4xx | Documentation, examples, onboarding |
| PBI-5xx–9xx | Reserved |

When adding a new wave, pick the next unused hundred-block. Numbering
collisions with upstream Hermes issue/PR numbers are coincidental and not
significant — PBIs track delivery here, GitHub issues track upstream.

## Status Legend

| Emoji | Meaning | Folder |
|-------|---------|--------|
| ⬜ | Todo / Open | `01-not-started/` |
| 🔄 | In Progress / Partially Done / Needs Verification | `02-in-progress/` |
| ✅ | Done | `03-completed/` |
| ❌ | Dropped | `04-parked/` |
| ⚠️ | MVP / Insecure (intentional shortcut, not production-grade) | `04-parked/` |
| 🔒 | Restricted access | `04-parked/` |

## Status Vocabulary

Internal status values used in `tasks.md` metadata, mapped to emoji:

| Status | Emoji | Meaning |
|--------|-------|---------|
| OPEN | ⬜ | Not started |
| IN PROGRESS | 🔄 | Actively being worked |
| NEEDS VERIFICATION | 🔄 | Code looks right, live behaviour unconfirmed |
| PARTIALLY DONE | 🔄 | Significant code exists, user-visible loop incomplete |
| DONE | ✅ | Delivered end-to-end and coherent |
| MVP / INSECURE | ⚠️ | Intentional temporary shortcut; not production-grade |
| DROPPED | ❌ | Will not be implemented |

## Rules

- **`DONE` means delivered end-to-end.** Not "code merged" — user-visible
  behaviour confirmed.
- **Acceptance criteria are falsifiable checkboxes.** Mark `[x]` only
  when verifiably met.
- **Security and contract drift are first-class backlog items**, not
  side notes.
- **One PBI = one folder.** Do not merge PBIs into a single folder or
  split a PBI across folders.
- **Never edit `README.md` without also updating the PBI's `tasks.md`**
  (and vice-versa for status changes).
- **Do not delete PBI folders.** Move them to `04-parked/` with a
  Reason in the metadata.
- **`archive/` is read-only.** It preserves historical plans; do not
  modify its contents.
- **Numbering collisions:** PBI numbers in `archive/` may coincidentally
  match active PBIs. The active bucket folders win; archive is
  historical only.
