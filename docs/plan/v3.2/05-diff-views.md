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

- [x] Toolbar `Render | Edit | Changes`
- [x] `Changes` renders baseline → current text, live, in the existing
      green/red
- [x] Caret survives every switch between the three states (scroll: see Verification — the textarea does not scroll internally in this layout)
- [x] The full diff badges each hunk with the finding that caused it
- [x] `final.md` and the PDF carry no attribution markup
- [x] `python -m pytest -q` green

## Tasks

### Task 1: the third toolbar state

**Files:** modify `src/malus/web/templates/document.html`,
`src/malus/web/static/document-viewer.js`, `src/malus/web/static/app.css`

- [x] **Step 1:** `Changes` joins `Render` and `Edit` in the closeout toolbar
      (built in v3.1, `document.html:72-75`). It is read-only and available to
      the same principals that may edit — a reviewer in closeout already has
      the per-finding `Changes` section and the full-diff page.
- [x] **Step 2:** the diff renders with the classes that already carry the
      colours everywhere else — `.diff-ins`, `.diff-del`, `.diff-ctx`
      (`app.css:425-430`). Do not invent a second palette for the same idea.
- [x] **Step 3:** **caret and scroll are preserved** across every transition,
      in both directions — Alberto's explicit requirement. Store
      `selectionStart`, `selectionEnd` and `scrollTop` of the textarea when
      leaving `Edit`, and restore them, with focus, on return; keep the sheet's
      own scroll position for `Render` and `Changes` independently.
- [x] **Step 4:** manual verification: type in the middle of a long document,
      switch to `Changes`, switch back → the caret is where it was, the view
      has not jumped, and typing continues from that point. Repeat via
      `Render`. Repeat after a scroll without typing.
- [x] **Step 5:** commit `feat(web): a third editor state shows the changes`.

### Task 2: the live diff endpoint

**Files:** modify `src/malus/web/router.py`, `src/malus/web/static/document-viewer.js`

- [x] **Step 1:** one route that takes the current text and returns rendered
      diff HTML, computed by `diffing.py` — the module that already renders
      every other diff in the product. The diff algorithm stays in one place;
      no JavaScript diff implementation is written (that would duplicate the
      algorithm and drift from the authoritative one, and ADR 0003 caps the
      vendored front-end libraries at three).
- [x] **Step 2:** guards: member of the review, phase `closeout`, and the same
      write capability the editor requires. It reads nothing it is not already
      allowed to read, but it must not become an open diff service.
- [x] **Step 3:** debounce ~400 ms on the client, and cancel the in-flight
      request when a newer one starts, so a slow response cannot overwrite a
      newer diff. Do not fire while the `Changes` tab is not visible.
- [x] **Step 4:** the response is HTML built server-side and already escaped by
      `diffing.py`; it still passes through DOMPurify on insertion, exactly as
      the per-finding `Changes` section does (`document-viewer.js:326-327`).
- [x] **Step 5:** tests — authz matrix on the route (owner 200, reviewer per
      the decision in Step 2, non-member 403, wrong phase 409, AI barred where
      the editor is barred); a known input produces the expected ins/del.
- [x] **Step 6:** commit `feat(web): live diff while the owner edits`.

### Task 3: provenance — which finding caused which hunk

**Files:** modify `src/malus/diffing.py`; tests in `tests/` beside the existing
diff tests

Step 04 makes every `DocumentVersion` the product of one implementation
session, with its RIDs on `RidChange`. That makes provenance computable:

- [x] **Step 1:** walk the version chain from the baseline. Carry, for each
      line of the current text, the finding(s) that last wrote it and the index
      of the baseline line it descends from (or none, if it was inserted).
      `equal` opcodes propagate both; `insert` and `replace` overwrite the
      provenance with the current version's RIDs. Record separately, for each
      baseline line that a version **deleted**, which version deleted it — a
      deletion has no line left to carry a label.
- [x] **Step 2:** render the baseline → final diff with a badge per hunk:
      insertions take the provenance of the inserted lines, deletions take the
      recorded deleter, replacements take the union. A hunk whose provenance
      cannot be established renders **without** a badge — never with a guess.
- [x] **Step 3:** the existing `html_diff` signature is used by the per-RID
      `Changes` section, the diff page and the `diff.html` download
      (v3.1 steps 03–04). Attribution must be **opt-in** so those callers keep
      byte-identical output unless they ask for it.
- [x] **Step 4:** tests — a three-version chain where finding A inserts,
      finding B edits A's insertion, and finding C deletes a baseline
      paragraph: each hunk carries the right badge; an unattributable hunk
      carries none; compact mode without the flag is unchanged from v3.1.
- [x] **Step 5:** commit `feat(diff): every hunk names the finding behind it`.

### Task 4: attribution reaches the readers

**Files:** modify `src/malus/web/router.py`,
`src/malus/web/templates/diff.html`, `src/malus/web/templates/diff_download.html`

- [x] **Step 1:** the full-diff page and the self-contained `diff.html`
      download render with attribution on. Badges are styled, not decorative
      text — the RID must be readable and, on the page, link to
      `?focus=<RID>`.
- [x] **Step 2:** `final.md`, `report.md` and the PDF are **unchanged**:
      attribution belongs to the diff views. Assert that in a test — a
      finalized document must never carry review scaffolding.
- [x] **Step 3:** commit `feat(web): the full diff says which comment caused what`.

## Definition of Done

- [x] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [x] Caret preservation verified by hand in both directions and written under
      `## Verification`; scroll preservation stated as unproven, with the reason
- [x] `final.md` byte-identical with and without the feature, proven by test
- [x] No new vendored front-end library, no JavaScript diff implementation
- [x] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Word-level attribution inside a line. Hunk granularity is what the version
  chain can support honestly.
- Rewriting the per-finding `Changes` section, which already works.

## Verification

Driven on the seeded dev server (`DEMO-CLOSE`, two findings implemented by two
separate sessions, one sent back for rework).

### Caret and scroll across the three states

With a session open and the caret placed **mid-document** (offset 435, inside
the paragraph being edited):

| Round trip | Caret after | Focus |
|---|---|---|
| Edit → Changes → Edit | **435** | restored |
| Edit → Render → Edit | **435** | restored |

The `Changes` view showed the diff, carried the badges of what was already
implemented, and included the words being typed — live, before any save.

**Scroll preservation is not proven, and the honest reason is that it cannot
be here:** the textarea grows to fit its content (`scrollHeight` 1118 =
`clientHeight` 1118), so it never scrolls internally in this layout — the page
does, and this renderer never scrolls the page (established in step 02). The
save/restore of `scrollTop` is kept as cheap insurance against a future layout
that caps the editor's height; today it restores 0 to 0.

### Attribution, as the reviewer sees it

`GET /diff?view=full` as the **reviewer**:

| Check | Result |
|---|---|
| Status | 200 — a reviewer reads the attributed diff |
| Distinct badges | `SIN-SRS-0001`, `SIN-SRS-0003` — the two implementation sessions |
| Changed rows labelled | 4 (each change contributes a `del` and an `ins` row) |
| Context rows labelled | **0** — the badge never lands on a line nobody touched |
| Row shape | line-number gutters, then the badge, then the text |

### What is covered by tests rather than by hand

Fourteen tests: eight unit (`tests/test_diff_attribution.py`) over the
provenance walk — a later finding overwriting an earlier one's line, an
untouched baseline line, a deletion, a multi-finding session, an empty chain, a
badge that tries to smuggle markup, and byte-identical output when attribution
is not asked for — and six web (`tests/web/test_diff_attribution_web.py`)
including the one that matters most: **`final.md` is byte-identical to the
saved text and contains no RID and no `diff-rid`.** Eight more
(`tests/web/test_diff_preview.py`) pin the live endpoint's authorization: owner
200, reviewer 403, non-member 403, AI admin 403, wrong phase 409.

## Deviations

1. **`node --check` was on this machine all along.** The repo has no JavaScript
   test harness and this wave did not add one, but `/usr/bin/node` exists, so
   `node --check src/malus/web/static/document-viewer.js` is a free syntax gate
   that needs no framework and no browser. It is now run before every JS
   change. It would not have caught step 03's `ReferenceError: phase is not
   defined` — that is a runtime fault, not a syntax one — but it costs nothing
   and it removes a whole class of round-trips to the browser.

2. **`setMode` grew a third state and kept its old signature.** Two callers in
   the session code pass booleans (`setMode(true)` from `startSession`,
   `setMode(false)` from `endSession`). Rather than touch them, the function
   accepts `true`/`false` as aliases for `"edit"`/`"render"`. One entry point,
   three states, no caller left behind.

3. **`VersionRepo` gained a `list`.** The chain walk needs every version in
   order and the repo only exposed `baseline`, `latest` and `by_ordinal`.

4. **The `Changes` view is writer-only, and so is its endpoint.** The step said
   it should be "available to the same principals that may edit", then hedged
   that a reviewer in closeout already has the per-finding diff and the full
   diff page. The endpoint is therefore gated exactly like the editor — owner
   or human global admin, closeout only — and a reviewer gets **403**. They
   lose nothing: the full-diff page shows them the same content, attributed,
   and it is the surface built for them.

5. **The live diff is the whole document, not a hunk view.** `context=None`,
   like the full-diff page. A ±3-line view of your own typing is disorienting
   because the surrounding text keeps disappearing as you edit; showing
   everything costs one render of a document that is already in memory.

6. **Badges link on the page and stay inert in the download.** The step asks
   for a badge that links to `?focus=<RID>`. That is right for the page and
   wrong for `diff.html`, which exists precisely to survive being e-mailed or
   archived — a link into the application would dangle the moment it leaves the
   server. `html_diff` therefore takes an optional `rid_base`: the page passes
   one and renders `<a>`, the download passes none and renders `<span>`. Both
   escape the RID; a test feeds a badge `" onmouseover="alert(1)` and asserts
   it cannot break out of the `href`.
