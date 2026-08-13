# v3.2 Step 2 — Viewer chrome: travel, collapse, overlap, CTA, the leave dialog

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** the five chrome defects Alberto hit while reading a review. None of
them changes a workflow; all of them are in the way of one.

Feedback points **2, 3, 4, 5, 6** of the v3.2 wave.

## Deliverables

- [ ] Clicking a comment carries the reader to its marker in the document
- [ ] The left sidebar collapses, and stays collapsed across page loads
- [ ] `Save draft` is never covered by the sidebar, at any width
- [ ] The reviewer banner on the RTD table is one button
- [ ] Saving a draft never raises the browser's "leave site?" dialog
- [ ] `python -m pytest -q` green

## The repo has no JavaScript test harness

Three of these five tasks are JS-only. The automated assertions available are
server-side (rendered template, route behaviour, `#viewer-data` payload); the
rest carries a **manual verification block** that must be executed and its
result written down. Do not introduce a JS test framework to satisfy a task —
that is the v3.1 convention and it holds here.

## Tasks

### Task 1: clicking a comment travels to it (point 2)

**Files:** modify `src/malus/web/static/document-viewer.js`

The cause is known. `setFocus` scrolls the marker with
`scrollIntoView({behavior:"smooth", block:"center"})` and then, two lines
below, scrolls the card with `scrollIntoView({block:"nearest"})`
(`document-viewer.js:702-706`). The second call is instantaneous and acts on
the scrolling element that the first call is still animating, so the smooth
scroll is cancelled mid-flight: the dot lights up, the page does not move.

- [ ] **Step 1:** bring the card into view **without touching page scroll** —
      set `scrollTop` on `.comments-panel`, which is its own scroll container
      (`app.css:357`, `max-height: calc(100vh - 2rem); overflow-y: auto`),
      computing the offset from the card's `offsetTop` relative to the panel.
      Leave the marker's smooth `scrollIntoView` and its flash exactly as they
      are.
- [ ] **Step 2:** guard the case where the marker does not exist — in
      `closeout` the sheet renders the latest version **without markers**
      (v3.1 decision), so `sheet.querySelector('.marker[...]')` is legitimately
      null and only the panel scroll must happen.
- [ ] **Step 3:** manual verification, written into `## Verification` below:
      in `in_review`, with the document long enough to scroll, click a card
      whose marker is off-screen → the sheet travels to the marker, the marker
      flashes, the card is visible in the panel; click a marker → same;
      `?focus=RID` deep link → same on load; in `closeout`, clicking a card
      does not throw and the panel scrolls.
- [ ] **Step 4:** commit `fix(web): clicking a comment travels to its marker`.

### Task 2: the sidebar collapses (point 3)

**Files:** modify `src/malus/web/templates/base.html`,
`src/malus/web/static/app.css`; a small inline script or
`src/malus/web/static/document-viewer.js` is the wrong home — the sidebar
exists on every page, so the toggle belongs with the shell.

The shell is `.shell` flex with a sticky sidebar of `232px`
(`app.css:69-76`). Below `900px` the sidebar is `position: fixed; z-index: 80`
with its own mobile behaviour (`app.css:105-114`) — **that branch is not
touched by this task**.

- [ ] **Step 1:** a toggle button in the sidebar header, with
      `aria-expanded` and an accessible label, that toggles
      `.nav-collapsed` on the shell root.
- [ ] **Step 2:** CSS for the collapsed state: `232px → 56px`, labels hidden,
      icons and the brand mark centred, `title` attributes so a collapsed item
      is still identifiable. The main column takes the freed width — the
      `.workbench` grid (`app.css:250`) must reflow, not overflow.
- [ ] **Step 3:** persist the state in `localStorage` and apply it **before
      first paint** to avoid a flash of expanded sidebar; the key is
      app-scoped, e.g. `malus.nav.collapsed`.
- [ ] **Step 4:** manual verification: collapse, navigate to another page →
      still collapsed; expand → still expanded after reload; at `≤900px` the
      mobile branch behaves exactly as before; keyboard: the toggle is
      reachable by Tab and operable by Enter and Space.
- [ ] **Step 5:** commit `feat(web): the workspace sidebar collapses`.

### Task 3: Save draft is never covered (point 4)

**Files:** modify `src/malus/web/static/app.css`

`.rev-actions` (`app.css:296`) is a plain flex row with no stacking context;
the sidebar is `position: fixed; z-index: 80` below `900px`
(`app.css:106`). At those widths the actions row can end up beneath it.

- [ ] **Step 1:** reproduce at 375 px, 768 px and exactly 900 px **before**
      changing anything, and record which widths actually overlap. Fix the
      geometry if the row is simply too wide; only raise a stacking context if
      the elements genuinely overlap. Do not paper over a layout bug with
      `z-index`.
- [ ] **Step 2:** verify again at 375 / 768 / 900 / 1280 px, with the sidebar
      both expanded and collapsed (Task 2 changes the widths in play).
- [ ] **Step 3:** commit `fix(web): the draft actions clear the mobile sidebar`.

### Task 4: the reviewer banner becomes a button (point 5)

**Files:** modify `src/malus/web/templates/review.html`

`review.html:12-17` renders, for `role == 'reviewer'`, a `.cta-banner` holding
a sentence — *"You're a reviewer on this document — add your comments in the
document view."* — and a button *"Add your comments"*.

- [ ] **Step 1:** delete the sentence. Keep the link, relabel it
      **`Go to document editor`**, left-aligned in the position the banner
      occupied. Decide from the rendered result whether `.cta-banner` still
      earns its box: if a bare button reads better, drop the wrapper and its
      now-unused CSS rule rather than leaving a dead class behind.
- [ ] **Step 2:** a test asserting the dashboard renders the button for a
      reviewer and no longer contains the banner sentence.
- [ ] **Step 3:** commit `feat(web): the reviewer CTA is one button`.

### Task 5: no leave-site dialog on save (point 6)

**Files:** modify `src/malus/web/static/document-viewer.js`

**Reproduce before fixing** — REQUIRED SUB-SKILL: superpowers:systematic-debugging.

What the code says today (`document-viewer.js:816-829`): the `beforeunload`
guard is registered only for a reviewer and fires while `dirty` is true;
`dirty` is set on any comment add or delete, and cleared on submit **only in
the `else` branch**, i.e. only when the client-side freeze pre-check passes. If
that check fails the handler calls `preventDefault()`, reveals `#freeze-warning`
and leaves `dirty` armed. The leading hypothesis is therefore that Alberto's
copy fails the pre-check; a second candidate is a submit path that does not go
through this listener at all.

- [ ] **Step 1:** reproduce with a real reviewer copy and record which branch
      runs. Do not fix anything until the reproduction is in hand and written
      into `## Verification`.
- [ ] **Step 2:** fix the cause found. If it is the branch above: clear
      `dirty` for **every** submit of `#rev-form`, whatever the pre-check
      decides, because a form submit is maluS's own navigation and never a
      case of losing work. The guard against closing the tab with genuinely
      unsaved comments **stays** — Alberto asked for the dialog on save to
      disappear, not for the protection to be removed.
- [ ] **Step 3:** manual verification: add a comment → `Save draft` → no
      dialog, the draft is saved; add a comment → `Submit` → no dialog; add a
      comment → close the tab → the browser still warns; trip the freeze
      warning deliberately → the warning shows and, once the page is left
      afterwards, no second dialog.
- [ ] **Step 4:** commit `fix(web): saving a draft no longer warns about leaving`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] Each of the five points verified against a running server, with the
      result written under `## Verification`
- [ ] No new vendored front-end library (ADR 0003), no new runtime dependency
- [ ] No JS test framework introduced
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Moving the side panel to the left. Considered and rejected in v3.1 —
  `.workbench` is shared by every role and every phase.
- Restyling the role banners inside the document viewer (`document.html:7-57`).
  Point 5 is about the RTD table's CTA banner only.

## Verification

_Filled in during implementation._

## Deviations

_None yet._
