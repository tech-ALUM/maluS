# maluS v1.6 — Reviewer Draft-Save + Submission-Status Panel

Requested by Alberto Boffi, 2026-07-15 (this repo, Claude Code). Reviewers need
to comment **incrementally across sessions**: save work-in-progress without
declaring it final, see it in the RTD table immediately, and reopen their copy
another day with their prior comments intact. The review dashboard gains a
**reviewer submission panel** so everyone can see who has submitted and who is
still drafting.

## Why this is mostly wiring that already exists

- `ReviewerCopy.submitted_at` is already nullable and already the "submitted"
  signal (`reviews_page` flags "to comment" on `submitted_at is None`,
  `src/malus/web/router.py:117`). What is missing is a way to persist a copy
  **without** marking it submitted: `ReviewerCopyRepo.upsert` unconditionally
  sets `submitted_at = submitted_at or _utcnow()`
  (`src/malus/repo/repositories.py:233`), so there is no draft state in practice.
- Reopening the editor already reloads the saved copy (`_own_copy_content`), so
  "see my previous comments" works the moment content is persisted.
- `harvest` already reads **all** copies and is idempotent by finding identity:
  a removed comment becomes `WITHDRAWN`, a reappearing one flips back to `OPEN`
  (`src/malus/harvest.py:258`). So harvesting drafts repeatedly is safe.

The work is therefore: split the single *Submit* action into **Save draft**
(persist + harvest, `submitted_at = NULL`) and **Submit** (persist + harvest,
`submitted_at = now`), and add the dashboard panel + a soft "all submitted"
notice.

## What is unchanged (non-negotiable)

- The reviewer copy is still baseline + inserted `{COMM}`/`{SUGG}` blocks; the
  freeze rule is validated **server-side on every persist** (Save included) — a
  draft that edits baseline text is rejected (422), exactly like Submit.
- Harvest / triage / lifecycle core, the closure invariant, the RID/anchor
  model: untouched.
- No new runtime dependency; **no schema change / no migration**
  (`submitted_at` already exists).

## The gate is a *soft indicator* (decided with Alberto)

The dashboard shows each reviewer's state and a "waiting for N reviewers"
notice, but **blocks nothing** — the owner decides when to proceed. A consequence
made explicit: because harvest is global, **draft comments are RIDs in the
shared RTD table, visible to everyone**; if the owner disposes a draft-sourced
RID and the reviewer later edits that comment, the RID is `WITHDRAWN` and a new
`OPEN` one is created (the disposition on it is lost). The notice signals this;
it does not prevent it. This trade-off is the accepted cost of "solo indicatore".

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-save-draft-and-submission-status.md` | Save/Submit split (editor + route + service/repo); dashboard reviewer submission panel + soft all-submitted notice | v1.4 (reviewer editor), v1 Step 6 (edit-copy route) |

## Global Definition of Done

- `python -m pytest -q` green; no schema change / no migration.
- Save persists a draft (`submitted_at` NULL), harvests, and the comments appear
  in the RTD table; Submit persists + marks submitted; both enforce the freeze
  rule server-side.
- The dashboard panel shows every reviewer as not-started / draft / submitted
  with an accurate N/M count; the "all submitted" notice appears only when all
  reviewers have submitted and blocks nothing.
- No new runtime dependency; assets vendored (no CDN). JS-off still works (two
  submit buttons in one form).

## Sources

- Design session with Alberto Boffi, 2026-07-15 (this repo, Claude Code): Save
  button for incremental commenting, comments visible in the table immediately,
  prior-session comments visible on reopen; dashboard reviewer submission list;
  gate chosen as a **soft indicator** (no hard block).
- Builds on `docs/plan/v1.4` (reviewer editor) and the `edit-copy` route in
  `src/malus/web/router.py`; model in `src/malus/db/models.py` (`ReviewerCopy`).
