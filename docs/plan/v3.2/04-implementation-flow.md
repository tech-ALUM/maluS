# v3.2 Step 4 — One comment at a time: implement, then close and associate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** the owner no longer edits freely and ticks findings afterwards. They
open a finding, the editor unlocks **for that finding**, they make the change,
and they close it — one change, one comment, one version.

Feedback point **13** of the v3.2 wave.

## Why this changes more than a button

Today the closeout editor is always writable and the link to findings is a set
of checkboxes submitted with the text: the owner may type anything and tick
anything, and the pairing is an assertion, not a fact. Attributing hunks of the
final diff to the comment that caused them — the second half of point 13, built
in step 05 — is only sound if each version has exactly one cause. This step
creates that guarantee at the source.

## Deliverables

- [ ] The closeout editor is locked until a finding is opened for implementation
- [ ] `Implement comment` on the card, of the same weight as the card's other
      actions, replacing the small `Mark implemented` control
- [ ] `Close and associate change` saves the version, links the finding, marks
      it implemented, and records the resolution — one gesture
- [ ] Duplicates can be attached to the same change at close time
- [ ] One implementation session at a time
- [ ] `python -m pytest -q` green

## Tasks

### Task 1: the session model in the viewer

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/templates/document.html`

- [ ] **Step 1:** introduce one piece of state — the open session
      `{rid, startedFrom}` or null — and derive every affordance from it. No
      second source of truth: the toolbar, the textarea's `readonly`, the card
      buttons and the warning banner all read that one object.
- [ ] **Step 2:** with **no session**, in phase `closeout`, the textarea is
      `readonly` and carries a hint — *pick a finding to implement*. `Render`
      and the existing version chip behave as today. The owner cannot type into
      the document by accident, which is the state Alberto asked for.
- [ ] **Step 3:** with a session open, the textarea is editable and focused,
      the toolbar switches to `Edit`, and the card of the session's RID is
      pinned open.
- [ ] **Step 4:** `Implement comment` on every card in `To implement` and
      `Rework requested`, rendered with the same class and position as the
      card's other actions — it replaces `cp-implement`
      (`document-viewer.js:525-536`), which is the small control Alberto is
      complaining about. While a session is open, the button on **other** cards
      is disabled with a title explaining why.
- [ ] **Step 5:** the RID checkboxes (`name="rids"`) and the
      `Save version & link (N)` submit built in v3.1 are removed — the session
      replaces them. Locate them by content.
- [ ] **Step 6:** manual verification, written into `## Verification`: enter
      closeout as owner → cannot type; open a finding → can type, other
      findings' buttons disabled; reload mid-session → the session is gone and
      the unsaved text with it, with a warning shown before that can happen.
- [ ] **Step 7:** commit `feat(web): the closeout editor unlocks one finding at a time`.

### Task 2: close and associate

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/templates/document.html`

- [ ] **Step 1:** while a session is open, the card's button reads
      **`Close and associate change`**. Pressing it opens a small panel
      carrying: the RIDs being linked, an optional `Resolution` field (the
      field v3 moved out of `dispose` and into `implement`), and the confirm.
- [ ] **Step 2:** the panel lists **other findings this same change resolves** —
      duplicates of the session's RID first (they share a triage master), then
      the remaining `To implement` / `Rework requested` findings, all unchecked
      by default. This is Alberto's decision: one session at a time, but one
      change may legitimately close a cluster of duplicates.
- [ ] **Step 3:** the submit posts `content` + `rids[]` (session RID first) +
      `resolution` to the closeout endpoint. Mirror the server's two refusals
      in the UI so the round-trip is not wasted: unchanged text, and no RID.
      The server stays the authority.
- [ ] **Step 4:** a `Cancel` that abandons the session, warning that the typed
      text will be lost.
- [ ] **Step 5:** commit `feat(web): close and associate a change to its finding`.

### Task 3: one service call, one transaction

**Files:** modify `src/malus/services/core.py`, `src/malus/web/router.py`

Today two calls do this work: `save_closeout_version` creates the version and
one `RidChange` per RID (`services/core.py:796-831`), and `implement` moves
`closed → implemented` and records the resolution, requiring ≥1 linked change
(`services/core.py:615`). The old UI made the owner perform them as two
separate gestures; the new one is a single act and must not be able to
half-succeed.

- [ ] **Step 1:** add a service that performs both in **one transaction**:
      save the version, link every RID, then implement every RID with the given
      resolution. If any RID fails its guard, nothing is written.
- [ ] **Step 2:** guards stay exactly where they are — owner or human global
      admin, phase `closeout`, disposition `accepted`, status `closed`,
      `is_ai` barred. This step composes existing services; it must not widen
      authority, and it must not let the owner reach `verified`.
- [ ] **Step 3:** keep `implement` reachable on its own. A finding implemented
      before this release, or one whose change was saved in an older version,
      must still be markable — do not orphan legacy data.
- [ ] **Step 4:** tests — happy path writes exactly one `DocumentVersion`, N
      `RidChange` rows and N findings in `implemented`; a rejected RID in the
      list aborts the whole call and leaves **no** version behind; unchanged
      text is refused; a reviewer and an AI owner are refused; the audit log
      records the act.
- [ ] **Step 5:** commit `feat(svc): implementing a finding is one transaction`.

### Task 4: the queue after the change

**Files:** modify `src/malus/web/router.py`

- [ ] **Step 1:** with implement folded into the close, a finding leaves
      `To implement` and appears in `Awaiting verification` immediately. Check
      the bucket rules in `_document_context` (`web/router.py:791-805`) still
      say what they mean, and that `tests/web/test_closeout_page.py` stays
      green.
- [ ] **Step 2:** redirect after close → `/document?focus={rid}` (the v3.1
      convention), so the owner lands on the card they just closed and can read
      its `Changes` diff.
- [ ] **Step 3:** commit `feat(web): a closed change lands in awaiting verification`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] Every closeout version in the database has ≥1 `RidChange` — asserted by a
      test that walks the versions created through the new path
- [ ] Traceability by construction is stronger, never weaker: no path writes a
      version with no finding attached
- [ ] Closure authority untouched: the owner reaches `implemented`, never
      `verified`
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Showing the diff while typing, and attributing hunks to findings — that is
  step 05, which builds on the session this step creates.
- Persisting a session across reloads. It is client state by design; the
  warning is the mitigation.

## Verification

_Filled in during implementation._

## Deviations

_None yet._
