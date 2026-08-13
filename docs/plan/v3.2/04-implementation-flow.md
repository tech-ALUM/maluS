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

- [x] The closeout editor is locked until a finding is opened for implementation
- [x] `Implement comment` on the card, of the same weight as the card's other
      actions, replacing the small `Mark implemented` control
- [x] `Close and associate change` saves the version, links the finding, marks
      it implemented, and records the resolution — one gesture
- [x] Duplicates can be attached to the same change at close time
- [x] One implementation session at a time
- [x] `python -m pytest -q` green

## Tasks

### Task 1: the session model in the viewer

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/templates/document.html`

- [x] **Step 1:** introduce one piece of state — the open session
      `{rid, startedFrom}` or null — and derive every affordance from it. No
      second source of truth: the toolbar, the textarea's `readonly`, the card
      buttons and the warning banner all read that one object.
- [x] **Step 2:** with **no session**, in phase `closeout`, the textarea is
      `readonly` and carries a hint — *pick a finding to implement*. `Render`
      and the existing version chip behave as today. The owner cannot type into
      the document by accident, which is the state Alberto asked for.
- [x] **Step 3:** with a session open, the textarea is editable and focused,
      the toolbar switches to `Edit`, and the card of the session's RID is
      pinned open.
- [x] **Step 4:** `Implement comment` on every card in `To implement` and
      `Rework requested`, rendered with the same class and position as the
      card's other actions — it replaces `cp-implement`
      (`document-viewer.js:525-536`), which is the small control Alberto is
      complaining about. While a session is open, the button on **other** cards
      is disabled with a title explaining why.
- [x] **Step 5:** the RID checkboxes (`name="rids"`) and the
      `Save version & link (N)` submit built in v3.1 are removed — the session
      replaces them. Locate them by content.
- [x] **Step 6:** manual verification, written into `## Verification`: enter
      closeout as owner → cannot type; open a finding → can type, other
      findings' buttons disabled; reload mid-session → the session is gone and
      the unsaved text with it, with a warning shown before that can happen.
- [x] **Step 7:** commit `feat(web): the closeout editor unlocks one finding at a time`.

### Task 2: close and associate

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/templates/document.html`

- [x] **Step 1:** while a session is open, the card's button reads
      **`Close and associate change`**. Pressing it opens a small panel
      carrying: the RIDs being linked, an optional `Resolution` field (the
      field v3 moved out of `dispose` and into `implement`), and the confirm.
- [x] **Step 2:** the panel lists **other findings this same change resolves** —
      duplicates of the session's RID first (they share a triage master), then
      the remaining `To implement` / `Rework requested` findings, all unchecked
      by default. This is Alberto's decision: one session at a time, but one
      change may legitimately close a cluster of duplicates.
- [x] **Step 3:** the submit posts `content` + `rids[]` (session RID first) +
      `resolution` to the closeout endpoint. Mirror the server's two refusals
      in the UI so the round-trip is not wasted: unchanged text, and no RID.
      The server stays the authority.
- [x] **Step 4:** a `Cancel` that abandons the session, warning that the typed
      text will be lost.
- [x] **Step 5:** commit `feat(web): close and associate a change to its finding`.

### Task 3: one service call, one transaction

**Files:** modify `src/malus/services/core.py`, `src/malus/web/router.py`

Today two calls do this work: `save_closeout_version` creates the version and
one `RidChange` per RID (`services/core.py:796-831`), and `implement` moves
`closed → implemented` and records the resolution, requiring ≥1 linked change
(`services/core.py:615`). The old UI made the owner perform them as two
separate gestures; the new one is a single act and must not be able to
half-succeed.

- [x] **Step 1:** add a service that performs both in **one transaction**:
      save the version, link every RID, then implement every RID with the given
      resolution. If any RID fails its guard, nothing is written.
- [x] **Step 2:** guards stay exactly where they are — owner or human global
      admin, phase `closeout`, disposition `accepted`, status `closed`,
      `is_ai` barred. This step composes existing services; it must not widen
      authority, and it must not let the owner reach `verified`.
- [x] **Step 3:** keep `implement` reachable on its own. A finding implemented
      before this release, or one whose change was saved in an older version,
      must still be markable — do not orphan legacy data.
- [x] **Step 4:** tests — happy path writes exactly one `DocumentVersion`, N
      `RidChange` rows and N findings in `implemented`; a rejected RID in the
      list aborts the whole call and leaves **no** version behind; unchanged
      text is refused; a reviewer and an AI owner are refused; the audit log
      records the act.
- [x] **Step 5:** commit `feat(svc): implementing a finding is one transaction`.

### Task 4: the queue after the change

**Files:** modify `src/malus/web/router.py`

- [x] **Step 1:** with implement folded into the close, a finding leaves
      `To implement` and appears in `Awaiting verification` immediately. Check
      the bucket rules in `_document_context` (`web/router.py:791-805`) still
      say what they mean, and that `tests/web/test_closeout_page.py` stays
      green.
- [x] **Step 2:** redirect after close → `/document?focus={rid}` (the v3.1
      convention), so the owner lands on the card they just closed and can read
      its `Changes` diff.
- [x] **Step 3:** commit `feat(web): a closed change lands in awaiting verification`.

## Definition of Done

- [x] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [x] No closeout version is written without a finding attached — asserted from
      the failure side, which is the one that matters: a session naming one
      real finding and one non-existent one leaves the document ordinal
      unmoved. (The plan said "a test that walks the versions"; a walk over
      versions cannot fail while the service refuses an empty RID list, so the
      refusal path is what got the test.)
- [x] Traceability by construction is stronger, never weaker: no path writes a
      version with no finding attached
- [x] Closure authority untouched: the owner reaches `implemented`, never
      `verified`
- [x] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Showing the diff while typing, and attributing hunks to findings — that is
  step 05, which builds on the session this step creates.
- Persisting a session across reloads. It is client state by design; the
  warning is the mitigation.

## Verification

One full session driven on the seeded server, on `DEMO-CLOSE` as owner.

**Before opening a session** — the editor is `readOnly`, the hint *"Pick a
finding in the queue and press Implement comment"* is visible, and only the one
finding in `rework` carries `Implement comment`. The findings in `awaiting` and
`noChange` carry nothing. Every v3.1 control is gone: `0` RID checkboxes, no
`Save version & link` button, no `Mark implemented`.

**Opening the session on SIN-SRS-0003** — `readOnly` false, the textarea shown
and focused, the hint hidden, and the card's button becomes
`Close and associate change` beside a `Cancel`.

**Closing it** — the panel is titled for the finding, carries an optional
resolution and would list duplicates (none here: it was the only finding in
`todo`/`rework`, which is itself the right answer).

**After the round trip:**

| | |
|---|---|
| Landed on | `/ui/reviews/DEMO-CLOSE/document?focus=SIN-SRS-0003` |
| Document version | 3 → **4**, and the new text is in it |
| Finding status | `closed` → **`implemented`** |
| Queue | `rework` → **`awaiting`** |
| Resolution | recorded from the panel |
| Rework callout | gone — the request was answered |
| Linked changes | 2 |
| Editor | locked again |

The service side is covered by `tests/web/test_implementation_flow_v32.py`:
the single gesture implements, duplicates attached at close are implemented
too, unchanged text and an empty finding list are still refused, the owner
still cannot reach `verified`, and a session naming one real finding plus one
non-existent one leaves **no version behind** — the transaction holds.

## Deviations

1. **`POST /closeout` was extended, not replaced.** The step describes a new
   service and a single gesture; it does not say whether the endpoint changes.
   It keeps its URL and its form fields, gains an optional `resolution`, and
   now calls `implement_change` instead of `save_closeout_version`. Nothing
   that posts to it had to learn a new address, and the v3.1 tests that drive
   it kept passing — with one meaning changed on purpose: a save now also
   implements, so those tests' follow-up "mark implemented" call is redundant
   rather than required.

2. **"One transaction" was checked, not assumed.** No service commits, the
   router never commits, and `get_session` commits once per request and rolls
   back on any exception (`api/deps.py:16-26`). So a finding that fails its
   guard aborts the whole session and leaves no version behind — asserted by
   `test_a_refused_finding_leaves_no_version_behind`, which posts a real RID
   together with a non-existent one and then checks the document ordinal has
   not moved.

3. **`implement` stays reachable on its own.** The step asks for it (legacy
   data), and the route `POST /rids/{rid}/implement` is untouched. What is gone
   is the *card control* that called it — `Mark implemented` — because in the
   session model the close does it.

4. **`implement` became idempotent, and that was not in the plan.** Folding it
   into the save broke **25 tests**, almost all of the same shape: save, then
   call implement, which now hit an illegal `implemented → implemented`
   transition and returned 422. Rewriting 25 fixtures to drop a call would have
   been the wrong repair — the honest reading is that `implement`'s contract is
   *"this finding is implemented"*, and asking for a state that already holds is
   not an error. It now returns the row unchanged **after running every guard**
   (AI barred, phase, a linked post-baseline change); only the transition and
   the audit entry are skipped, because nothing changed. That took 25 failures
   to 3.

5. **A session tolerates a finding it cannot legally implement.** The last
   failure was real and mine: after an admin reopens a terminated review its
   findings are `verified`, and `verified → implemented` is illegal, so *saving
   at all* became impossible in a reopened review. `implement_change` now
   transitions only the findings sitting at `closed` and merely links the
   others — exactly what saving did before this release. No guard is skipped:
   `save_closeout_version` still refuses anything that is not an accepted
   finding, and withdrawing a verdict stays the reviewer's act, never a side
   effect of the owner saving. (Point 14, in step 06, is what gives the
   reviewer the deliberate way back to `implemented`.)

6. **Four tests were updated for the new semantics, not silenced.**
   `test_closeout_page`, `test_editor` and both end-to-end tests
   (`test_v1_e2e`, `test_v3_flow`) asserted that a save leaves the finding
   `closed` and that a second gesture implements it — the exact behaviour point
   13 removes. They now assert the single gesture, and two of them additionally
   pin the idempotency above. `test_closeout_page` also had the redirect
   target, which now carries `?focus=<RID>` so the owner lands on the card they
   just closed.

   Worth naming: `tests/e2e/test_v3_flow.py` is the end-to-end written for the
   3.0.0 release **earlier in this same session**. It documented v3's two-step
   flow faithfully; v3.2 changes that flow, so it changed with it. Its audit
   assertion still holds — `implement` is logged, now from inside the save.
