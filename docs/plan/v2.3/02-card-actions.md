# v2.3 Step 2 — Card actions + reviewer-color focus/hover

## Files
- Modify: `document-viewer.js` — dispose toggle only when status == open
  (label "Dispose…" / "Review AI draft…"); card Withdraw (admin, posts to
  retract) + Purge (admin) as equal-weight buttons; own-reviewer retract
  removed from the card (local editor delete remains).
- Modify: `review.html` — table control relabeled "✕ withdraw".
- Modify: `app.css` — `button.warn` (amber); hover border, active ring and
  focus glow use `var(--rev-color)`; remove teal focus ring and `.sugg`
  teal border-left override.
- Test: extend `tests/web/test_document_viewer.py` (payload: canPurge only
  admin; no server change for dispose visibility — client-side).

## Deliverables (TDD)
- [ ] Tests adjusted; implement; browser verification (hover keeps reviewer
      color, focus glows with reviewer color, no pink/teal; answered card
      has no Dispose; admin sees Withdraw+Purge, owner neither).
- [ ] Suite green.

## DoD
No foreign color ever appears on a comment; disposed findings are changed
only via reopen; destructive card actions are admin-only and visually paired.
