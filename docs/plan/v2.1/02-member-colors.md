# v2.1 Step 2 — Member colors (global default + per-review override)

## Objective

Every reviewer gets a stable color chosen by humans: admin sets a user's
global default (Users page); owner/admin overrides it per review (Members
page). Marker, cards, legend and RTD chips use the resolved color.

## Files

- Create: `alembic/versions/<rev>_member_colors.py` — add nullable
  `users.color` + `review_members.color` (VARCHAR(7), `#rrggbb`).
- Modify: `src/malus/db/models.py` — the two Optional[str] fields.
- Modify: `src/malus/web/router.py` — `_document_context` and `review_page`
  build `colors: {reviewer_name: "#hex" | null}` (member override → user
  default → null = palette fallback).
- Modify: `src/malus/web/accounts.py` — `POST
  /ui/reviews/{id}/members/{username}/color` (owner/admin; `color` form
  field, `""` resets) and `POST /ui/admin/users/{username}/color`
  (admin). Validation `^#[0-9a-fA-F]{6}$` → else 422.
- Modify: `members.html` (per-row `<input type=color>` + reset,
  auto-submit on change), `admin_users.html` (same per user),
  `review.html` (chips use resolved color via inline `--rev-color`),
  `document-viewer.js` (use `data.colors[name]` before palette),
  `app.css` (tiny picker styles).
- Test: `tests/web/test_member_colors.py` (new).

## Deliverables (TDD)

- [x] Failing tests: admin sets a user color (bad hex 422; non-admin 403);
      owner sets a member override (reviewer 403); payload `colors`
      resolves override > global > null; reset (`""`) clears the override.
- [x] Migration + models + routes + resolution.
- [x] Templates + JS consumption (marker/card/legend/chips).
- [x] Browser verification: set a global color, override it in one review,
      markers/legend/chips follow; reset restores.
- [x] Suite green (migration applied in test engines via create_all);
      commit `feat(web): per-member colors — global default + review override (v2.1 step 2)`.

## Definition of Done

Comment color == reviewer's resolved color everywhere; palette only as
fallback when nothing is set; both pickers enforce authz server-side.

## Sources

- `00-design.md` decision 4; `alembic/versions/` pattern.
