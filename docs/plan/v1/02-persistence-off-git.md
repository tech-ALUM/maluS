# Step 2 — Persistence Layer (core off files + git)

## Objective

Make the reused core (harvest, triage, lifecycle, report) operate on the
database through a repository layer, and re-implement freeze and traceability
without git.

## Deliverables

- [x] `src/malus/repo/` — repository classes (ReviewRepo, RidRepo, VersionRepo,
      UserRepo, AuditRepo) wrapping SQLModel sessions
- [x] Core services refactored to consume repositories, not the filesystem:
      `harvest`, `triage`, `apply-suggs`, `report`, `lifecycle`
- [x] Freeze = create an immutable baseline `DocumentVersion` (hash-pinned)
- [x] Traceability = `RidChange` rows + `AuditLog`; `verify --check` equivalent
      reads the DB (accepted RID with no linked change = flagged)
- [x] `rtd.yaml` import/export service (interchange only)
- [x] Ported tests: the v0 fixture reviews now run through the DB

## Key behaviors

- **Harvest** parses each `ReviewerCopy.content` (existing parser), validates
  the freeze rule against the baseline version, writes/reconciles RID rows with
  stable ids (existing reconciliation logic, keyed on reviewer + content hash).
- **Freeze** snapshots the current DUR into an immutable version; further edits
  create new versions; the baseline is never mutated.
- **Traceability**: an accepted RID cannot move to `implemented` unless a
  `RidChange` links it to a version newer than the baseline — the DB analogue of
  the commit-reference rule. Anomalies (change referencing a non-accepted RID)
  are reported.
- **Closure invariant** stays in `lifecycle.transition()` (unchanged); only the
  persistence around it moves.

## Tasks

1. Introduce the repository layer; inject sessions.
2. Rework each core service to read/write via repositories.
3. Implement version snapshots (freeze/finalize) and RID-linked changes.
4. Provide `rtd.yaml` import (seed a review) and export (produce minutes/backup).
5. Port fixtures and tests; delete the file/git code paths (or move them under
   an `import_legacy` helper).

## Definition of Done

Every v0 pipeline behavior is reproducible against the DB; the freeze immutability
and RID-traceability checks pass without any git call anywhere in `src/`; suite green.

## Out of scope

HTTP endpoints (Step 3). Real-time concerns (single-writer-per-phase still holds
at the review level; row-level DB writes are serialized by the DB).

## Deviations

Agreed with Alberto before coding; details in
`memory/decisions/2026-07-10-v1-step-02-decisions.md`.

- **Transport retired to legacy (Alberto's choice).** The v0 file/git `*_review`
  wrappers, the git helpers (`_baseline_sha`, `commits_since`,
  `check_traceability`), and `finalize_review` were removed; the `malus` CLI is
  slimmed to `--version` + `import` (v0 dir → DB); `ai.py` and the AI CLI are
  deleted (rebuilt over MCP in Step 7). File reading survives only in
  `malus/legacy/import_review_dir`.
- **Bridge, not fork.** Every mutating service does export (DB→RTD via Step-1
  `rtd_io`) → run the *unchanged* pure core → `sync_rtd_to_review` (upsert rows).
  The closure invariant stays in `lifecycle.transition`/`verify_rid`.
- **Extra services beyond the deliverable list**, needed to reproduce the full
  pipeline (owner disposition was GUI-only in v0): `answer` (open→answered),
  `implement` (answered→implemented, **traceability-gated**), `save_version`
  (owner edit), `link_change`. `ReviewerCopyRepo` added alongside the five named
  repos.
- **Traceability gate** (`implement`) requires ≥1 `RidChange` to a post-baseline
  version — the DB analogue of the commit-reference rule — enforced in the
  service, not in the pure `transition`.
- **content_hash** is sha256 of the version content; a v0 import therefore gets a
  sha256 baseline hash (not the old git SHA), which is the intended v1 identity.
- Test suite: 163 → 129 (pure-core tests kept/trimmed; git/file/AI pipeline tests
  replaced by DB service + legacy-import tests). `prompts/` package data is kept,
  orphaned until Step 7.

## Sources

v1 design session 2026-07-09; ADR 0001 (git removal).
