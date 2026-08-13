# v3.2 Step 6 — Lifecycle: where a reopened finding lands, and asking for a review back

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** reopening a verified finding puts it back where it belongs, and a
terminated review can be asked back by the people who need it, not only seized
by an admin.

Feedback points **14** and **15** of the v3.2 wave.

## Deliverables

- [ ] Reopening a `verified` finding in closeout lands it in
      *Awaiting verification*, not in rework and not out of the queue
- [ ] Any member may request the reopening of a terminated review
- [ ] Owner or human global admin approves or rejects it
- [ ] While a request is pending, every member sees it
- [ ] Alembic revision, idempotent, on top of whatever `alembic heads` reports
- [ ] `python -m pytest -q` green

## Tasks

### Task 1: a reopened verified finding goes back to awaiting (point 14)

**Files:** modify `src/malus/lifecycle.py`, `src/malus/constants.py`,
`src/malus/services/core.py`

The defect is worse than the label Alberto used. `reopen_rid` sends the finding
to `OPEN` unconditionally (`lifecycle.py:115-147`, target set at line 144), and
the closeout queue has **no bucket for `open`** — it groups `closed`,
`implemented` and `verified` only (`web/router.py:797-804`). So reopening a
verified finding during closeout does not put it in rework: it removes it from
the workspace altogether.

- [ ] **Step 1:** in phase `closeout`, reopening a `verified` finding targets
      **`implemented`** — the change exists and is linked, what was withdrawn
      is the verdict on it, so the finding belongs in *Awaiting verification*.
      In phase `in_review`, reopen keeps targeting `open`, unchanged.
- [ ] **Step 2:** `TRANSITIONS` (`constants.py:70-77`) declares `VERIFIED` as
      terminal, and reopen already lives outside that graph. Decide
      deliberately whether to add `VERIFIED → IMPLEMENTED` to the graph or to
      keep reopen a documented exception, and write the reason down here —
      `docs/spec/rid-schema.md` §3 is the normative text and must agree with
      whatever is chosen.
- [ ] **Step 3:** authority is unchanged: reopen belongs to the finding's
      reviewer, or a moderator / human global admin on their behalf. The owner
      never reopens their way out of a verdict.
- [ ] **Step 4:** the reason keeps being recorded exactly as today (appended to
      the reply, in the timeline). Do **not** route it into the rework columns
      added in step 03 — this is not a request for changes, and the queue must
      not show it as one.
- [ ] **Step 5:** tests — reopen a `verified` finding in closeout → status
      `implemented`, and it appears in the `awaiting` bucket; reopen in
      `in_review` → `open`, unchanged; owner and AI refused; the reason lands
      in the timeline.
- [ ] **Step 6:** commit `fix(lifecycle): a reopened verified finding awaits verification again`.

### Task 2: the request to reopen a terminated review (point 15)

**Files:** modify `src/malus/db/models.py`, `src/malus/services/core.py`,
`src/malus/web/router.py`, `src/malus/web/templates/review.html`,
`src/malus/web/templates/reviews.html`,
`src/malus/web/templates/document.html`; create
`src/alembic/versions/<rev>_review_reopen_request.py`

v3.1 gave a human global admin `reopen_finalized` — an instant, unilateral
`finalized → closeout` (`services/core.py:900-924`). Nobody else has any way to
say the review needs to come back. The pattern to copy already exists one level
down: a reviewer requests their submitted copy back with
`ReviewerCopy.reopen_requested_at` (`db/models.py:156`,
`services/core.py:203-249`), and the owner approves.

- [ ] **Step 1:** add to `reviews`: `reopen_requested_at`,
      `reopen_requested_by_id` (FK `users.id`), `reopen_reason`.
- [ ] **Step 2:** the Alembic revision — run `alembic heads` and branch from
      what it reports (step 03 adds a revision too; whichever lands second
      must chain, not fork). Inspect before every DDL operation per
      `CLAUDE.md`; no backfill is needed, the columns start null.
- [ ] **Step 3:** `request_reopen_finalized` — **any member** of the review,
      phase `finalized`, reason required, audit-logged. Refuse a second request
      while one is pending rather than overwriting the first requester.
- [ ] **Step 4:** `approve_reopen_finalized` — **owner or human global admin**,
      moves `finalized → closeout` and clears the request. `reject_reopen_finalized`
      — same authority, clears the request and keeps the phase, recording the
      rejection in the audit log so the asker can see it happened.
- [ ] **Step 5:** `is_ai` stays absolute: an AI principal neither approves nor
      rejects. `reopen_finalized` (the v3.1 instant admin path) is kept
      untouched as the emergency valve.
- [ ] **Step 6:** UI — the request uses the **same UI as `Terminate review`**
      (Alberto's words): same placement, same weight, same double confirm, with
      the reason field added. While a request is pending, **every member** sees
      a banner naming the requester and the reason, on the review dashboard, in
      the reviews list row and in the document view; owner and admin see
      `Approve` and `Reject` in it.
- [ ] **Step 7:** tests — authz matrix (member requests 303, non-member 403,
      owner approves 303, reviewer approving 403, AI admin 403, wrong phase
      409); a second request while one is pending is refused; the banner
      renders for every member and the buttons only for those who may act;
      approval lands the review in `closeout`.
- [ ] **Step 8:** commit `feat(db): a terminated review can be asked back`,
      `feat(svc): request, approve and reject a reopening`,
      `feat(web): the pending reopen request is visible to everyone`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] `alembic upgrade head` succeeds on a fresh database and on a copy of a
      pre-step one, and is a no-op run twice
- [ ] `tests/db/test_db_migration.py::test_migrations_match_the_models_exactly`
      green — a model change without a revision is a bug
- [ ] Closure authority untouched; `is_ai` absolute on both new decisions
- [ ] `docs/spec/rid-schema.md` agrees with the reopen target chosen in Task 1
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Notifying anyone by mail or any other channel. The banner is the mechanism.
- Reopening a review that was never terminated — that is the existing
  admin `closeout → in_review` valve and it is unchanged.

## Verification

_Filled in during implementation._

## Deviations

_None yet._
