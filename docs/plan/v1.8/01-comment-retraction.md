# Step 1 — Reviewer comment retraction (hard-delete pristine) + panel placement

## Objective

Let a reviewer retract their own `OPEN` comment — from the editor (already
removes the block on save) or via a new **delete** control in the RTD table — and
have it disappear: a pristine comment's RID row is hard-deleted, while one the
owner already disposed is kept as `withdrawn`. Move the submissions panel to the
top.

## Deliverables

### Purge pristine-withdrawn RIDs (the reconciliation)

- [x] **`_purge_retracted` in the harvest service** (`services/core.py`): after
      `sync_rtd_to_review`, hard-delete RID rows where `status == withdrawn` **and
      pristine** — `disposition`/`reply`/`resolution` all null, `verified_by_id`
      null, no `RidChange`, `master_id` null, and not referenced as a master by
      any other RID. Runs on every `harvest` (reviewer save, API, moderator).
- [x] The pure `harvest.build_rtd` is **unchanged** (still withdraws); the purge
      lives only in the DB service.

### Table "delete" control (reviewer, own OPEN comment)

- [x] **`retract_comment` service** (`services/core.py`): parse the reviewer's
      copy (`malus.parser.scan`), find the block whose identity (kind + type +
      severity + text, or SUGG old→new) matches the RID, remove that span from the
      copy content, save the copy (preserving `submitted_at`), then `harvest`
      (→ withdraw → purge). Exported via `malus.services`.
- [x] **Route** `POST /ui/reviews/{id}/rids/{rid}/retract` (reviewer-only): 403
      unless the caller is a reviewer whose `display_name == rid.reviewer`; 409 if
      the RID is not `OPEN`. Redirects to the dashboard.
- [x] **GUI**: a small **delete** control in the RTD-table row, shown only on the
      current reviewer's **own** `OPEN` comments.

### Submissions panel placement (c)

- [x] **`review.html`**: move the submissions panel out of the right-hand column
      to a **full-width band at the top** (below the header/actions, above the
      metrics/filters/table); reviewers laid out as a readable row of state chips.
      Drop the two-column `.rtd-layout`; adjust `app.css` spacing.

### Tests

- [x] Purge: a pristine vanished comment → its RID row is **gone** from the DB
      after harvest; an *acted-upon* vanished comment (disposition set) → stays
      `withdrawn` (row kept).
- [x] Editor path (a): remove a comment from the copy + submit → the RID is gone
      from `GET /rids`.
- [x] Table path (b): a reviewer retracts their own OPEN comment → 303, the block
      is gone from their copy and the RID row is gone; retracting **another
      reviewer's** comment → 403; retracting a **disposed** comment → 409 (and the
      RID survives).
- [x] The pure harvest core test (`test_vanished_comment_becomes_withdrawn_not_deleted`)
      stays green.
- [x] Dashboard: the submissions panel renders at the top (before the RTD table).

## Key behaviors

- Retraction's single source of truth stays the reviewer's copy: both paths
  remove the block from the copy, then harvest + purge. The table control never
  bypasses the copy (so a later harvest can't resurrect the comment).
- Only pristine (never-engaged) comments are hard-deleted; anything the owner
  disposed keeps a `withdrawn` trace. Reviewers act only on their own OPEN items.

## Definition of Done

A reviewer deletes a comment (editor or table) and it disappears from the RTD
table; a disposed comment retracted stays `withdrawn`; cross-reviewer / non-open
retraction is refused; the pure harvest test stays green; the submissions panel
sits at the top; suite green; no migration.

## Out of scope

- Owner/moderator deleting a reviewer's comment (retraction is reviewer-only).
- Bulk retraction; undo of a hard-deleted comment (re-add it in the editor).
- Any change to the pure harvest reconciliation (withdraw) or to closure.

## Deviations

Recorded in `memory/decisions/2026-07-16-v1.8-comment-retraction.md`.

- **Purge is a DB-service cleanup, the pure core is untouched.** `_purge_retracted`
  runs at the end of the `harvest` service (so every harvest — reviewer save, API,
  moderator — reconciles); `harvest.build_rtd` still only withdraws, keeping
  `test_vanished_comment_becomes_withdrawn_not_deleted` green.
- **Both delete paths funnel through the copy.** The table `retract_comment`
  service parses the reviewer's copy (`parser.scan`), matches the block to the RID
  by identity (`_block_matches` + `_sugg_repr`, mirroring `harvest._render_sugg`),
  cuts its span, re-saves the copy (preserving `submitted_at`), then harvests —
  so a later harvest can't resurrect it. The editor path already removes the block.
- **Submissions panel** moved from the right-hand `.rtd-layout` column to a
  full-width band at the top; chips laid out as a wrapping row (`app.css`).
- **Live check note**: the preview renderer reports `innerWidth: 0`, which
  collapses every column — verified the layout after forcing a 1280×800 viewport
  (panel full-width above the table, chips in one row) and exercised the retract
  control end-to-end (own OPEN row only → hard-deleted). No schema change / no
  migration. Full suite green (255).

## Sources

- Design session with Alberto Boffi, 2026-07-16 (this repo, Claude Code).
- Verified in code: `src/malus/harvest.py:258` (withdraw loop),
  `src/malus/services/{core,sync}.py`, `src/malus/parser.py` (`scan`),
  `src/malus/web/{router.py,templates/review.html,static/app.css}`,
  `tests/test_harvest.py:139` (the withdraw-not-delete core test to preserve).
