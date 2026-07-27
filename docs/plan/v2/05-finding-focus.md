# Step 5 — Finding focus mode (dual panel, always)

## Objective

Opening a comment — from the dashboard RTD table or by URL — always shows
the dual panel: the rendered document on the left auto-scrolled to the
comment's anchor (its marker highlighted, others dimmed) and the full
finding detail with disposition/verify forms on the right. Implemented as a
focus mode of the step-4 viewer, not a separate page.

## Files

- Modify: `src/malus/web/router.py` — `/ui/reviews/{id}/document` accepts
  `?focus=<RID>` (validated: unknown RID → 404); the old finding route
  `GET /ui/reviews/{id}/rids/{rid}` → 303 to `/document?focus=<rid>`.
  Post-action redirects (`dispose`, `verify`, `reopen`, `discard-draft`)
  land back on `/document?focus=<rid>`.
- Modify: `src/malus/web/static/document-viewer.js` — focus mode: on load,
  scroll to the focused marker, expand its card (full detail: anchor
  section/line, verified-by, reply, resolution, all forms), dim other
  markers; an ✕ on the card exits focus (back to plain `/document`).
- Modify: `src/malus/web/templates/review.html` — RTD table rows link to
  focus mode.
- Delete: `src/malus/web/templates/finding.html` (superseded).
- Test: extend `tests/test_document_viewer.py`.

## Deliverables (TDD)

- [ ] Failing tests: `/rids/{rid}` redirects 303 to `/document?focus=...`;
      focus with unknown RID → 404; dispose/verify/reopen redirect back to
      focus mode; template payload marks the focused RID.
- [ ] Implement; delete `finding.html`; wire dashboard links.
- [ ] Browser verification: click a row in the RTD table → document scrolls
      to the anchor, card expanded; dispose from focus; verify from focus;
      deep-link URL works cold.
- [ ] Suite green; commit
      `feat(web): finding focus mode — dual panel everywhere (v2 step 5)`.

## Definition of Done

No route ever shows a finding without the document beside it; old URLs
redirect; suite green.

## Out of scope

- Side-by-side diff of SUGG old/new against the document (future idea).

## Sources

- `00-design.md` §7; step 4 viewer interfaces.
