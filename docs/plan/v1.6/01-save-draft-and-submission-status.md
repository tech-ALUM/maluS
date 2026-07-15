# Step 1 — Save draft / Submit split + reviewer submission panel

## Objective

Let a reviewer **save** their copy as a work-in-progress draft (persisted +
harvested, not marked submitted) as many times as they like, and **submit** it
when done. Give the review dashboard a right-hand **reviewer submission panel**
with each reviewer's state and a soft "all submitted" notice that blocks nothing.

## Deliverables

### Save vs Submit

- [x] **Repo**: `ReviewerCopyRepo.upsert` stops forcing `submitted_at` to now —
      it sets `submitted_at` to exactly the value passed (default `None`), so a
      draft can be persisted with `submitted_at = NULL`
      (`src/malus/repo/repositories.py:233`).
- [x] **Service**: `add_reviewer_copy(..., submitted: bool = True)` computes
      `submitted_at = now if submitted else None`. Default `True` preserves every
      existing caller (legacy import, API `put_copy`/`submit_copy`, tests).
- [x] **GUI route** `POST /ui/reviews/{id}/edit-copy` gains `action: str =
      Form("submit")`; validates the freeze rule for **both** actions; persists
      with `submitted=(action == "submit")`; harvests in both cases. Redirects:
      Submit → dashboard; Save → back to the editor with a `?saved=1` flash.
- [x] **Editor** `edit_copy.html`: two `type="submit"` buttons in the one form,
      `name="action"` with values `save` (secondary) and `submit` (primary); a
      status line showing the copy state (Not saved / Draft, saved &lt;when&gt; /
      Submitted &lt;when&gt;) and a "Saved ✓" flash after a Save. Works with JS off.
- [x] **API parity**: `PUT /reviews/{id}/copies/{user}` saves a **draft**
      (`add_reviewer_copy(..., submitted=False)`); `POST
      /reviews/{id}/copies/{user}/submit` marks **submitted** (`submitted=True`,
      explicit). Mirrors the GUI Save/Submit split at the `submitted_at` level.
      PUT keeps its current no-harvest / no-extra-validation contract (the
      pipeline harvests separately — every caller already does), so no existing
      API caller regresses.

### Dashboard submission panel (soft indicator)

- [x] **`review_page`** builds `reviewer_status`: the roster of members with the
      **reviewer** role (via `ReviewRepo.members`), each mapped to `not_started`
      (no `ReviewerCopy`) / `draft` (`submitted_at` NULL) / `submitted`
      (`submitted_at` set), plus `submitted`/`total` counts and `all_submitted`.
- [x] **`review.html`**: a right-hand `<aside>` (two-column layout like the
      editor `.workbench`; stacks under on mobile) listing each reviewer with a
      state pill and a header "Reviewers — N/M submitted"; a soft notice —
      "Waiting for N reviewer(s)." while pending, or "All reviewers have
      submitted — you can proceed with disposition." when complete. **No block.**
- [x] **CSS** in `app.css` for the panel + the three state pills, following the
      existing `.st` / `.role` / `.badge` conventions.

### Tests

- [x] Service: `add_reviewer_copy(submitted=False)` → `submitted_at is None`;
      `submitted=True` → timestamp; a Save after a Submit reverts the copy to
      draft (`submitted_at` back to `None`).
- [x] Route: `action=save` → copy saved as draft + harvest ran (RID visible via
      export) + redirect to the editor; `action=submit` → `submitted_at` set +
      redirect to dashboard; a Save that edits baseline text → 422.
- [x] Dashboard: the panel renders the correct state per reviewer and an accurate
      N/M count; the "all submitted" notice shows only when all reviewers are
      submitted; nothing is blocked (owner disposition still reachable regardless
      of submission state).
- [x] API: `PUT /copies/{user}` leaves `submitted_at` NULL (draft); `POST
      /copies/{user}/submit` sets it; the full-pipeline test (PUT → harvest)
      still passes unchanged.

## Key behaviors

- **Save = work-in-progress, Submit = done.** Reopening the editor after a Submit
  and pressing Save reverts the copy to draft (until re-Submitted); this is
  intentional and harmless under the soft gate.
- Save keeps the reviewer **in the editor** (flash confirmation) so incremental
  commenting is uninterrupted; the harvested comments are visible on the shared
  RTD table the moment they navigate to it.
- The freeze rule is authoritative server-side for **both** actions; the client
  pre-check in `reviewer-editor.js` needs no change (its `submit` listener
  already runs for any form submit — two buttons in one form need no JS change).

## Definition of Done

A reviewer saves a draft, sees it in the RTD table, reopens the editor another
session with prior comments intact, and later submits; the dashboard shows every
reviewer's state with an accurate count and a soft all-submitted notice that
blocks nothing; the freeze rule is enforced on Save and Submit; suite green; no
migration.

## Out of scope

- Autosave (explicit buttons only, as requested).
- Any hard gate / phase lock / new review sub-state (the gate is a soft
  indicator — see the overview).
- Per-reviewer visibility scoping of draft comments (drafts are shared in the
  RTD table by design).

## Deviations

Recorded in `memory/decisions/2026-07-15-v1.6-save-draft.md`.

- **`ReviewerCopyRepo.upsert`** no longer forces `submitted_at = now`; it stores
  the value passed. The draft/submit policy lives in
  `add_reviewer_copy(..., submitted: bool = True)` (default keeps existing
  callers submitting).
- **The GUI editor form opts out of `hx-boost`** (`hx-boost="false"`). Found by
  live browser verification: under hx-boost (htmx 2.0.3) the submit button's
  `action` value is dropped, so "Save draft" fell back to the default and wrongly
  submitted. A native submit includes the clicked button's value (and still works
  with JS off). Guarded by `test_editor_form_opts_out_of_hx_boost`.
- **API parity**: `PUT /copies/{user}` saves a draft (`submitted=False`);
  `POST /copies/{user}/submit` submits (`submitted=True`). PUT keeps its
  no-harvest contract, so the pipeline (`test_full_pipeline_over_http`) is
  unchanged.
- Tests: `tests/db/test_services.py` (draft flag), `tests/api/test_draft_submit.py`
  (PUT vs submit), `tests/web/test_editor.py` (Save/Submit + hx-boost guard),
  `tests/web/test_submission_panel.py` (panel states/notice/soft-gate). No schema
  change / no migration. Full suite green (234).

## Sources

- Design session with Alberto Boffi, 2026-07-15 (this repo, Claude Code).
- Touch points verified in code: `src/malus/repo/repositories.py`
  (`upsert:213`, forced timestamp `:233`, `ReviewRepo.members:118`),
  `src/malus/services/core.py` (`add_reviewer_copy:114`),
  `src/malus/web/router.py` (`submit_copy:359`, `review_page:172`,
  `reviews_page:117`), `src/malus/web/templates/{edit_copy,review}.html`,
  `src/malus/web/static/reviewer-editor.js`, `src/malus/web/static/app.css`.
