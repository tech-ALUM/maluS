# Step 6 — Polish, docs, logo prompt, release v2.0.0

## Objective

Close the release: brand deliverable (logo prompt), normative docs updated,
ADR for the vendored front-end libs, changelog + version bump, final full
verification pass.

## Files

- Create: `docs/brand/logo-prompt.md` — the ready-to-paste ChatGPT prompt,
  verbatim from `00-design.md` §10.
- Create: `docs/adr/0003-vendored-frontend-libs.md` — records the no-CDN
  rule and the three vendored libs (htmx, marked v12, DOMPurify + version),
  rationale and update procedure.
- Modify: `docs/spec/rid-schema.md` — normative `anchor.offset` note (if not
  already done in step 4a; verify).
- Modify: `README.md` — v2 feature summary (viewer, transfer, redesign);
  screenshots optional (skip if stale-prone).
- Modify: `CHANGELOG.md` — v2.0.0 section: the six workstreams, the perf
  fix numbers (before/after from the step-1 guard), breaking UI changes
  (edit-copy and finding URLs now redirect).
- Modify: `pyproject.toml` + `src/malus/__init__.py` → `2.0.0`.
- Modify: `CLAUDE.md` — GUI description updated (document viewer replaces
  gui/rtd.html vocabulary if stale).

## Deliverables

- [ ] `docs/brand/logo-prompt.md` written (English prompt, ALUM palette
      hex, mark + lockup variants, light/ink backgrounds, 24 px legibility,
      SVG-friendly).
- [ ] ADR 0003 committed.
- [ ] Spec/README/CHANGELOG/CLAUDE.md updated; version bumped to 2.0.0.
- [ ] Full `python -m pytest -q` green from a clean checkout state.
- [ ] Final browser pass across the whole flow (login → create review →
      comment as two reviewers → transfer ownership → dispose inline →
      implement → verify → focus links) on the dev preview.
- [ ] Commit `chore(release): v2.0.0` and tag `v2.0.0`.

## Definition of Done

Tagged v2.0.0 with green suite, updated docs, and the logo prompt available
to paste into ChatGPT.

## Out of scope

- Generating the logo image itself (done by Alberto in ChatGPT with the
  prompt).
- Data migrations (none needed in v2).

## Sources

- `00-design.md` §10, §12–13; repo release convention (`chore(release):`
  commits, e.g. `b31f7ff`, `56a52d2`).
