# v3.2 Step 7 — Downloads that download, and a PDF that always exists

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** on a terminated review, every artefact downloads as a file, the
download row is readable, and the PDF is the PDF — not a browser print dialog.

Feedback point **16** of the v3.2 wave.

## Deliverables

- [ ] Every download arrives as a file, proven by a test on the response
- [ ] The downloads row sits on its own line, below `Full diff`
- [ ] `Print view` is gone from the interface
- [ ] A terminated review always yields `review.pdf`
- [ ] `python -m pytest -q` green

## What is already true

All five routes already send `Content-Disposition: attachment`
(`web/router.py:1169-1252`): `baseline.md`, `final.md`, `diff.html`,
`report.md`, `review.pdf`. So "the downloads open instead of downloading" is
**not** explained by the headers, and the most likely cause is the one visible
in the markup: when no PDF artifact exists the interface offers `Print view`
(`review.html:117-118`, `reviews.html:35-36`), which is a page, and it renders
inline because it is meant to. Confirm that before changing anything else.

## Tasks

### Task 1: confirm what actually opens inline

**Files:** none yet — this is a reproduction

- [ ] **Step 1:** on a terminated review, exercise all five links plus
      `Print view` and record which ones open in a tab instead of downloading.
      Write the result under `## Verification`. If a real download route does
      render inline, that is a different defect from point 16's third sentence
      and gets its own fix here.
- [ ] **Step 2:** add the `download` attribute to the anchors regardless — it
      costs nothing and states the intent in the markup — and a test that
      asserts `Content-Disposition: attachment` on each of the five routes, so
      a regression cannot come back silently.
- [ ] **Step 3:** commit `test(web): every finalized download is an attachment`.

### Task 2: the downloads row gets its own line

**Files:** modify `src/malus/web/templates/review.html`

`Full diff` and the five downloads currently share one `<p class="actions">`
(`review.html:103-120`).

- [ ] **Step 1:** `Full diff` stays where it is; the `Downloads:` label and its
      buttons move to their own line below it.
- [ ] **Step 2:** check the `⋯` menu on finalized rows of `/ui/reviews`
      (`reviews.html:22-39`) still lists the same set — the two entry points
      must not drift apart.
- [ ] **Step 3:** commit `feat(web): the downloads row stands on its own line`.

### Task 3: the PDF always exists

**Files:** modify `src/malus/web/router.py`, `src/malus/services/core.py`,
`src/malus/web/templates/review.html`, `src/malus/web/templates/reviews.html`;
delete `src/malus/web/templates/print.html` and its route

v3 generates the PDF once at finalize and archives it in `review_artifacts`;
when the `malus[pdf]` extra was absent at that moment, no artifact exists and
the interface degrades to `Print view` (ADR 0004).

- [ ] **Step 1:** on a request for `review.pdf` with no archived artifact,
      **generate it then, archive it, and serve it** — same pipeline, same
      storage, so the second request is a plain read. The artifact table
      already orders `created desc` and the newest wins.
- [ ] **Step 2:** remove `Print view` and the `/print` route and template. The
      button is gone from `review.html` and from the `⋯` menu in
      `reviews.html`.
- [ ] **Step 3:** **the honest failure mode.** If `malus[pdf]` is not installed,
      on-demand generation cannot work either. The PDF entry must then say why
      in the interface — extra not installed on this server — instead of
      returning 404 or a broken download. Do not pretend the button works.
- [ ] **Step 4 — ANSWERED 2026-08-13 by reading the image, not by asking.**
      The ALUM server **cannot** render a PDF today: `Dockerfile:14` installs
      `pip install ".[mcp]"` only, and the image carries none of the system
      libraries WeasyPrint needs (Pango, cairo, gdk-pixbuf). That is the whole
      explanation for the `Print view` Alberto sees in production — the PDF was
      never generated at finalize because `PDF_AVAILABLE` is False there.

      So this is a change to make, not a question to ask:

      - add the runtime system libraries to the image (`libpango-1.0-0`,
        `libpangoft2-1.0-0`, `libgdk-pixbuf-2.0-0`, `libcairo2` and the fonts
        WeasyPrint falls back to) in one `apt-get` layer, cleaned in the same
        `RUN`;
      - install `".[mcp,pdf]"`;
      - verify in the built image that `malus.pdfgen.PDF_AVAILABLE` is True —
        a test that asserts the extra is *importable* proves nothing about the
        image, so this check belongs to the build, not to pytest;
      - note in `docs/ops/runbook.md` that upgrading to this release needs a
        `docker compose build`, because the image gained system packages.

      The image grows by roughly the size of the Pango stack. If that trade is
      unwanted, the alternative is to keep the PDF optional and say so in the
      UI — but that contradicts point 16, so it is not the default.
- [ ] **Step 5:** tests — `review.pdf` with no artifact and the extra available
      → 200, and an artifact now exists; with the extra unavailable → the
      documented refusal, not a 500; the `/print` route is gone; no template
      references it. Existing tests `tests/web/test_finalize_downloads.py` and
      `tests/web/test_reviews_list_downloads.py` cover the current behaviour
      and will need updating — update them, do not delete them.
- [ ] **Step 6:** commit `feat(web): a terminated review always yields its PDF`
      and `refactor(web): the browser print fallback is retired`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] All five downloads verified by hand on a terminated review, on a real
      server, and the result written under `## Verification`
- [ ] No reference to `print.html` or `/print` left anywhere
- [ ] The `malus[pdf]` status of the ALUM server is recorded in this file
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Changing the PDF's layout, cover or signature page.
- Digital signing — never implemented, deferred past 3.0.0
  (`docs/plan/v3/05-signing.md`).

## Verification

_Filled in during implementation._

## Deviations

_None yet._
