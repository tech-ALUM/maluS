# Step 2 — Persistence Layer (core off files + git)

## Objective

Make the reused core (harvest, triage, lifecycle, report) operate on the
database through a repository layer, and re-implement freeze and traceability
without git.

## Deliverables

- [ ] `src/malus/repo/` — repository classes (ReviewRepo, RidRepo, VersionRepo,
      UserRepo, AuditRepo) wrapping SQLModel sessions
- [ ] Core services refactored to consume repositories, not the filesystem:
      `harvest`, `triage`, `apply-suggs`, `report`, `lifecycle`
- [ ] Freeze = create an immutable baseline `DocumentVersion` (hash-pinned)
- [ ] Traceability = `RidChange` rows + `AuditLog`; `verify --check` equivalent
      reads the DB (accepted RID with no linked change = flagged)
- [ ] `rtd.yaml` import/export service (interchange only)
- [ ] Ported tests: the v0 fixture reviews now run through the DB

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

## Sources

v1 design session 2026-07-09; ADR 0001 (git removal).
