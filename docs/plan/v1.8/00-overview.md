# maluS v1.8 — Reviewer Comment Retraction + Submissions Panel Placement

Requested by Alberto Boffi, 2026-07-16 (this repo, Claude Code). A reviewer must
be able to **retract their own comment** — from the editor (delete the block and
save) or directly from the RTD table — and have it **disappear** from the table,
not linger as `withdrawn`. The dashboard **submissions panel** (v1.6) is moved to
the **top**, full-width, with readable spacing.

## Reconciling "disappear" with the harvest model

Harvest deliberately **withdraws** a vanished comment rather than deleting it
(`test_harvest.py::test_vanished_comment_becomes_withdrawn_not_deleted`;
`sync.py`: "never deleting; withdrawn is a status") — this gives idempotency,
stable ids, and reappearance. Alberto's retraction should nonetheless make a
comment truly disappear. Reconciliation (agreed 2026-07-16):

- The **pure harvest core (`build_rtd`) is unchanged** — it still withdraws; the
  core test stays green.
- At the **DB service layer**, after each harvest, RID rows that are `withdrawn`
  **and pristine** are hard-deleted. *Pristine* = the owner never engaged: no
  `disposition` / `reply` / `resolution`, not verified, no `RidChange`, and not
  part of a duplicate cluster (`master_id` unset and not a master).
- **Net effect**: a comment retracted **before the owner acted on it** is truly
  deleted (row gone); one the owner had **already disposed** stays `withdrawn`
  (its history cannot be erased — this is a formal-review tool).

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-comment-retraction.md` | Purge pristine-withdrawn RIDs (DB service); reviewer table "delete" (editor path already removes the block); submissions panel moved to the top | v1.6 (submission panel), v1.4 (editor), v1 (harvest/lifecycle) |

## Global Definition of Done

- `python -m pytest -q` green; **no schema change / no migration**.
- Deleting a pristine comment (editor save *or* the table control) removes its
  RID row — gone from the table; a comment the owner already disposed stays
  `withdrawn` when retracted.
- A reviewer can only retract **their own** comment, and only while it is `OPEN`.
- The pure harvest core test (withdraw, not delete) stays green.
- The submissions panel renders at the top, full-width, readable.

## Sources

- Design session with Alberto Boffi, 2026-07-16 (this repo, Claude Code):
  hard-delete of retracted comments, reconciled as pristine → delete /
  acted-upon → keep `withdrawn`; submissions panel to the top.
- Builds on `docs/plan/v1.6` (submission panel) and the harvest/sync model in
  `src/malus/harvest.py`, `src/malus/services/{core,sync}.py`.
