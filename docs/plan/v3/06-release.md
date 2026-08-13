# v3 Step 6 — Release 3.0.0

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ship v3.0.0 — breaking workflow release (Verify → Accept disposition,
mandatory closeout phase).

## Deliverables

- [x] E2E test of the full v3 flow
- [x] CHANGELOG + README updated
- [x] Version bump 3.0.0 (tag + push are Task 3 Step 3, not done here)
- [ ] Open Brain record (on Alberto's confirmation)

---

### Task 1: E2E flow test

**Files:**
- Create: `tests/e2e/test_v3_flow.py` (model on the existing `tests/e2e` style)

- [x] **Step 1:** one test driving the whole lifecycle through the web routes with
  three users (owner, reviewer, admin): create+freeze (phase `in_review`) →
  reviewer submits a copy with 2 comments → harvest → owner disposes one
  `accepted`, one `rejected` → reviewer accepts both dispositions (`closed`) →
  owner starts closeout → closeout save linked to the accepted RID → mark
  implemented → reviewer requests changes (back to `closed`, reason in reply) →
  owner re-saves + re-marks → reviewer verifies → owner finalizes → downloads:
  `final.md` matches the edited content; `report.md` 200; `review.pdf` 200 when
  `PDF_AVAILABLE` else 404 (assert both branches via the flag, not the env).
  Assert the phase after every transition and that the rejected RID never
  appears in the closeout queue.
- [x] **Step 2:** `python -m pytest tests/e2e -q` → PASS. Commit:
  `test(e2e): full v3 review→closeout→verify→finalize flow`.

### Task 2: docs

**Files:**
- Modify: `CHANGELOG.md`, `README.md`

- [x] **Step 1:** CHANGELOG `## 3.0.0` — Breaking: `answered→verified` removed;
  Verify button is now Accept disposition (review phase); verification moved to
  the closeout phase; new RID status `closed`; review phases
  `draft/in_review/closeout/finalized` (`active` dropped, auto-backfilled).
  Added: closeout workspace, per-RID diffs, full-diff page, finalize GUI,
  downloads (final MD / RTD report / archived PDF), print fallback, extra
  `malus[pdf]` (ADR 0004) — **no signing claim, see Deviations below**.
  README: update the workflow section to the v3 process, add the extras
  install matrix (Pango note for weasyprint).
- [x] **Step 2:** commit `docs: v3.0.0 changelog + README workflow/extras`.

### Task 3: version, tag, push

- [x] **Step 1:** bump `pyproject.toml:7` and `src/malus/__init__.py:8` to `3.0.0`.
- [x] **Step 2:** `python -m pytest -q` → green. Commit `chore: bump version to 3.0.0`.
- [ ] **Step 3:** `git tag v3.0.0 && git push && git push --tags` (confirm remote
  with Alberto if the push target is ambiguous). **Not done by this worker —
  reserved for the orchestrator per its task boundaries.**

### Task 4: Open Brain

- [ ] **Step 1:** propose to Alberto the distilled release record (cassetto
  openbrain-alum, tags ALUM + maluS, source claude-code:maluS): v3.0.0 scope,
  the new lifecycle semantics, extras/flags, and any Deviations recorded in the
  step files. **Save only after his explicit confirmation** (global Open Brain
  rule); search for an existing v3 thought first to avoid duplicates.

## Definition of Done

- [ ] Suite green on the tagged commit; tag pushed; CHANGELOG/README accurate;
  Open Brain updated (or explicitly declined).

## Deviations

- **Task 2 Step 1 — no digital-signature claim.** The plan text prescribed a
  CHANGELOG line mentioning "extras `malus[pdf]` + `malus[sign]` (ADR 0004),
  optional PAdES signing (`MALUS_SIGNING=1`)" and a README link to
  `docs/how-to/signing-ca.md`. Verified before writing anything:
  `grep -rn "MALUS_SIGNING" src/` finds no such flag anywhere in `src/malus/`
  (the only hits are in this plan file and in `docs/plan/v3/05-signing.md`
  itself), `docs/plan/v3/05-signing.md` is at 0 of 19 checkboxes, and
  `docs/how-to/signing-ca.md` does not exist. Digital signing was never
  implemented. CHANGELOG and README for 3.0.0 therefore mention only the
  `malus[pdf]` extra (WeasyPrint + Pango) and its print fallback, with no
  `malus[sign]` row and no link to a how-to that doesn't exist. Agreed with
  Alberto Boffi ahead of time; recorded here per the house style used in
  `docs/plan/v3.1/*.md`.
- **Task 3 Step 3 (tag + push) not run by this worker** — reserved for the
  orchestrator; this session stopped after the version-bump commit as
  instructed.
