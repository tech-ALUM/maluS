# maluS — General Development Plan

## Vision

A zero-cost, text-first tool that runs formal document reviews on Markdown
documents with 10+ reviewers, working identically whether the document owner
is a human or an AI. Everything is plain text (Markdown + YAML) plus one
self-contained HTML GUI; git provides history and traceability.

## Process being implemented

1. **Freeze**: DUR baseline is frozen; one copy per reviewer (git branch per reviewer).
2. **Review**: reviewers insert comment blocks only — the freeze rule forbids
   editing document text, which makes consolidation a diff-extraction, not a merge.
3. **Harvest**: parse all copies, validate insertion-only rule, emit `rtd.yaml`
   (one RID per finding, stable IDs).
4. **Triage**: cluster duplicates under master RIDs; batch-accept `{SUGG}` fixes.
5. **Disposition**: owner answers each RID (accept/reject/defer) in `gui/rtd.html`.
6. **Implementation**: owner edits the document; each commit references the RIDs it resolves.
7. **Verification**: reviewers verify and close their RIDs — the owner cannot
   self-certify. Mandatory control for the AI-owner mode.
8. **Finalize**: new baseline, review minutes, dashboard generated from `rtd.yaml`.

## Architecture

- `src/malus/` Python package, Typer CLI: `init`, `freeze`, `copies`,
  `harvest`, `triage`, `apply-suggs`, `report`, `verify`, `finalize`, `ai`.
- Canonical data: `rtd.yaml` (single file; single-writer-per-phase makes this safe).
- GUI: `gui/rtd.html`, single file, vanilla JS, YAML lib vendored inline,
  File System Access API with download fallback.
- Review instance layout (created by `malus init`):
  `reviews/<review-id>/{baseline.md, reviewers/<name>.md, rtd.yaml, report.md}`.
- Git operations via subprocess; repo hosting-agnostic.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-foundations.md` | Specs (comment syntax, RID schema, lifecycle), package + CLI skeleton | — |
| 2 | `02-harvest.md` | Freeze validation, comment parser, rtd.yaml generation | 1 |
| 3 | `03-triage.md` | Duplicate clustering, SUGG batch-apply | 2 |
| 4 | `04-gui.md` | Single-file RTD GUI | 1 (schema), 2 (data) |
| 5 | `05-lifecycle.md` | Status enforcement, verification, reporting, finalize | 2–4 |
| 6 | `06-ai-roles.md` | AI as owner / reviewer / moderator | 1–5 |
| 7 | `07-e2e.md` | End-to-end sample review, docs, packaging, v0.1.0 | all |

Each step file contains: objective, deliverables (checkboxes), detailed tasks,
Definition of Done, and out-of-scope notes. Steps are implemented strictly in
order by Claude Code; kickoff prompt in `90-claude-code-kickoff.md`.

## Global Definition of Done

- `python -m pytest -q` green at the end of every step.
- No runtime dependencies beyond PyYAML + Typer without a recorded decision.
- Every design deviation recorded in the step file and, if architectural,
  in `memory/decisions/`.

## Sources

Design session with Alberto Boffi, Claude chat, 2026-07-03: process design,
four architecture corrections (freeze rule, canonical single RTD, YAML+GUI
storage, reviewer-side closure), name selection (maluS). Recorded in
`memory/decisions/2026-07-03-architecture-decisions.md`.
