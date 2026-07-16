# CLAUDE.md — maluS

## What this project is

maluS manages formal reviews of Markdown documents using a RID
(Review Item Discrepancy) workflow: frozen baseline → per-reviewer copies
with inline comment blocks → harvest to `rtd.yaml` → triage → owner
disposition (single-file HTML GUI) → RID-referenced implementation →
reviewer-side verification → finalized document + minutes.

Key vocabulary: **DUR** (Document Under Review), **RTD** (Revision Tracking
Document, the canonical `rtd.yaml`), **RID** (one tracked finding),
**disposition** (owner decision: accepted/rejected/deferred).

Three roles — owner, reviewer, moderator — each fillable by a human or an AI.
Invariant: **closure authority belongs to reviewers — plus a moderator or a
global admin acting on their behalf — never the owner, and never an AI
principal** (the `is_ai` guard is absolute; a global admin is a superuser over
every review, incl. closure, since v1.10).

## How to work in this repo

- The development plan is in `docs/plan/`. `00-general-plan.md` is the index;
  each step has its own detailed file with deliverables and a Definition of Done.
- Implement **one step at a time**, in order. Do not start the next step
  without explicit instruction.
- Update the checkboxes in the step file as you complete deliverables.
  Record agreed deviations under a `## Deviations` heading in that step file.
- If a spec is ambiguous, ask before deviating. Never silently change
  a decision recorded in `docs/adr/`.
- Design rationale/ADRs live in `docs/adr/` + `docs/spec/` (authoritative); the
  distilled history is in Open Brain (openbrain-alum, tag maluS).

## Conventions

- Python 3.12+, PyYAML, Typer. GUI: single-file vanilla HTML/JS in
  `gui/rtd.html` (no build step, no CDN at runtime — vendor libraries inline).
- Tests: pytest in `tests/`, run with `python -m pytest -q`. Every step's
  DoD requires a green suite.
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
  During review implementation phases, commits touching a document must
  reference the RIDs they resolve (e.g. `fix(doc): clarify timing — SIN-SRS-0042`).
- No third-party runtime dependencies beyond PyYAML and Typer without
  a recorded decision.

## Layout

- `src/malus/` — package; CLI entry point `malus`
- `gui/rtd.html` — RTD GUI (loads/saves `rtd.yaml` via File System Access API)
- `tests/` — pytest suite with fixture documents under `tests/fixtures/`
- `docs/plan/` — the plan; `docs/adr/` + `docs/spec/` — decisions & specs

## Memory — Open Brain
- Le regole generali di comportamento Open Brain sono nel mio ~/.claude/CLAUDE.md globale (cassetti, segregazione, salva solo su richiesta, delete per ID, cerca prima di scrivere). NON ripeterle qui.
- Cassetto di questo progetto: openbrain-alum
- Tag da usare per capture/search: ALUM + maluS
- source dei ricordi: claude-code:maluS
