# v3.2 Step 5 — Diff views: live while typing, attributed when read

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** the owner sees what they are changing while they change it, and the
reviewers see which comment each change came from.

Feedback points **11** and **12**, plus the last sentence of point **13**.

## The shape of the idea

There is one diff, not two: **baseline → the text as it stands right now**,
including the words being typed. Everything already implemented is in it
because it is in the saved versions; the pending edit is in it because it is in
the textarea. That single view answers point 11 (implemented changes visible in
the editor, in green and red) and point 12 (a live diff while editing) without
inventing two different pictures of the same document.

Attribution rides on top: step 04 guarantees every version has exactly one
cause, so every hunk can name the finding it came from.

## Deliverables

- [ ] Toolbar `Render | Edit | Changes`
- [ ] `Changes` renders baseline → current text, live, in the existing
      green/red
- [ ] Caret **and** scroll survive every switch between the three states
- [ ] The full diff badges each hunk with the finding that caused it
- [ ] `final.md` and the PDF carry no attribution markup
- [ ] `python -m pytest -q` green

## Tasks

### Task 1: the third toolbar state

**Files:** modify `src/malus/web/templates/document.html`,
`src/malus/web/static/document-viewer.js`, `src/malus/web/static/app.css`

- [ ] **Step 1:** `Changes` joins `Render` and `Edit` in the closeout toolbar
      (built in v3.1, `document.html:72-75`). It is read-only and available to
      the same principals that may edit — a reviewer in closeout already has
      the per-finding `Changes` section and the full-diff page.
- [ ] **Step 2:** the diff renders with the classes that already carry the
      colours everywhere else — `.diff-ins`, `.diff-del`, `.diff-ctx`
      (`app.css:425-430`). Do not invent a second palette for the same idea.
- [ ] **Step 3:** **caret and scroll are preserved** across every transition,
      in both directions — Alberto's explicit requirement. Store
      `selectionStart`, `selectionEnd` and `scrollTop` of the textarea when
      leaving `Edit`, and restore them, with focus, on return; keep the sheet's
      own scroll position for `Render` and `Changes` independently.
- [ ] **Step 4:** manual verification: type in the middle of a long document,
      switch to `Changes`, switch back → the caret is where it was, the view
      has not jumped, and typing continues from that point. Repeat via
      `Render`. Repeat after a scroll without typing.
- [ ] **Step 5:** commit `feat(web): a third editor state shows the changes`.

### Task 2: the live diff endpoint

**Files:** modify `src/malus/web/router.py`, `src/malus/web/static/document-viewer.js`

- [ ] **Step 1:** one route that takes the current text and returns rendered
      diff HTML, computed by `diffing.py` — the module that already renders
      every other diff in the product. The diff algorithm stays in one place;
      no JavaScript diff implementation is written (that would duplicate the
      algorithm and drift from the authoritative one, and ADR 0003 caps the
      vendored front-end libraries at three).
- [ ] **Step 2:** guards: member of the review, phase `closeout`, and the same
      write capability the editor requires. It reads nothing it is not already
      allowed to read, but it must not become an open diff service.
- [ ] **Step 3:** debounce ~400 ms on the client, and cancel the in-flight
      request when a newer one starts, so a slow response cannot overwrite a
      newer diff. Do not fire while the `Changes` tab is not visible.
- [ ] **Step 4:** the response is HTML built server-side and already escaped by
      `diffing.py`; it still passes through DOMPurify on insertion, exactly as
      the per-finding `Changes` section does (`document-viewer.js:326-327`).
- [ ] **Step 5:** tests — authz matrix on the route (owner 200, reviewer per
      the decision in Step 2, non-member 403, wrong phase 409, AI barred where
      the editor is barred); a known input produces the expected ins/del.
- [ ] **Step 6:** commit `feat(web): live diff while the owner edits`.

### Task 3: provenance — which finding caused which hunk

**Files:** modify `src/malus/diffing.py`; tests in `tests/` beside the existing
diff tests

Step 04 makes every `DocumentVersion` the product of one implementation
session, with its RIDs on `RidChange`. That makes provenance computable:

- [ ] **Step 1:** walk the version chain from the baseline. Carry, for each
      line of the current text, the finding(s) that last wrote it and the index
      of the baseline line it descends from (or none, if it was inserted).
      `equal` opcodes propagate both; `insert` and `replace` overwrite the
      provenance with the current version's RIDs. Record separately, for each
      baseline line that a version **deleted**, which version deleted it — a
      deletion has no line left to carry a label.
- [ ] **Step 2:** render the baseline → final diff with a badge per hunk:
      insertions take the provenance of the inserted lines, deletions take the
      recorded deleter, replacements take the union. A hunk whose provenance
      cannot be established renders **without** a badge — never with a guess.
- [ ] **Step 3:** the existing `html_diff` signature is used by the per-RID
      `Changes` section, the diff page and the `diff.html` download
      (v3.1 steps 03–04). Attribution must be **opt-in** so those callers keep
      byte-identical output unless they ask for it.
- [ ] **Step 4:** tests — a three-version chain where finding A inserts,
      finding B edits A's insertion, and finding C deletes a baseline
      paragraph: each hunk carries the right badge; an unattributable hunk
      carries none; compact mode without the flag is unchanged from v3.1.
- [ ] **Step 5:** commit `feat(diff): every hunk names the finding behind it`.

### Task 4: attribution reaches the readers

**Files:** modify `src/malus/web/router.py`,
`src/malus/web/templates/diff.html`, `src/malus/web/templates/diff_download.html`

- [ ] **Step 1:** the full-diff page and the self-contained `diff.html`
      download render with attribution on. Badges are styled, not decorative
      text — the RID must be readable and, on the page, link to
      `?focus=<RID>`.
- [ ] **Step 2:** `final.md`, `report.md` and the PDF are **unchanged**:
      attribution belongs to the diff views. Assert that in a test — a
      finalized document must never carry review scaffolding.
- [ ] **Step 3:** commit `feat(web): the full diff says which comment caused what`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] Caret and scroll preservation verified by hand in both directions on a
      document long enough to scroll, and written under `## Verification`
- [ ] `final.md` byte-identical with and without the feature, proven by test
- [ ] No new vendored front-end library, no JavaScript diff implementation
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Word-level attribution inside a line. Hunk granularity is what the version
  chain can support honestly.
- Rewriting the per-finding `Changes` section, which already works.

## Verification

_Filled in during implementation._

## Deviations

_None yet._
