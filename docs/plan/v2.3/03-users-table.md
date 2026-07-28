# v2.3 Step 3 — Users page fits the viewport

## Files
- Modify: `admin_users.html` — columns: Account (name + @username stacked),
  Status (pills), Color, Actions (compact; reset-password in a "⋯" menu).
- Modify: `app.css` — stacked cells, compact actions.
- Test: extend `tests/web/test_accounts.py` or new asserts (structure: menu
  present in row, no bare reset input at top level).

## Deliverables (TDD)
- [ ] Tests; implement; browser verification at 1280 and 1024 px: no
      horizontal scroll.
- [ ] Suite green.

## DoD
document.documentElement.scrollWidth <= innerWidth on /ui/admin/users at
1024px with several users.
