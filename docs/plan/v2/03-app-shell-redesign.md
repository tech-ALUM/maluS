# Step 3 — App-shell redesign (organic, ALUM brand, light)

## Objective

Restyle the whole GUI as an organic ALUM-branded app shell with sidebar
navigation, so steps 4–5 land on the new skin. Zero functional change: every
route, form, and permission stays as is. Light theme only (Alberto,
2026-07-27). The alum-brand-identity skill is the source of truth for tokens,
components and logo usage.

## Files

- Modify: `src/malus/web/static/app.css` — rewritten on the extended token
  set (keeps the v1.9 vendored fonts and `--coral/--teal/--ink/...` variables,
  adds spacing/radius/shadow/motion scales and the shell layout).
- Modify: `src/malus/web/templates/base.html` — shell: fixed left sidebar
  (brand mark at top; nav: Reviews; per-review context nav: Dashboard /
  Document / Members when a review is in context; admin: Users; bottom:
  account + logout), main content column, slim mobile topbar with disclosure
  toggle at narrow widths (CSS-first, tiny inline JS for the toggle).
- Modify: all templates in `src/malus/web/templates/` — migrate to the shell
  (blocks: `{% block sidenav %}` context links, active-state class), restyle
  page headers, cards, forms, tables, badges, empty states.
- Test: existing suite (template render smoke via existing route tests).

## Design language (from the alum-brand-identity skill + design §9)

- Sidebar: ink background, coral active indicator (rounded pill), Space
  Grotesk for nav labels; content on paper background.
- Cards: 14–16 px radii, layered soft shadows, 1 px `--line` borders.
- Micro-transitions: 120–180 ms ease-out on hover/focus/enter; respects
  `prefers-reduced-motion`.
- RTD table: clickable rows (whole row → finding), reviewer color chip
  (deterministic palette shared with step 4 via `--rev-1…--rev-8` tokens),
  status pills, filter toolbar restyled compact.
- Progress-to-closure: organic ring (SVG stroke) in the dashboard metrics.
- Empty states: friendly copy + subtle illustration built from brand shapes
  (pure CSS/SVG inline, no assets fetched).

## Deliverables

- [ ] Load the alum-brand-identity skill; extract exact tokens/components.
- [ ] `base.html` shell + responsive sidebar; every template migrated
      (login stays a centered card outside the shell, brand-marked).
- [ ] `app.css` rewritten: tokens, shell, components (buttons, chips, pills,
      forms, tables, cards, popover, flash/error), reviewer palette tokens.
- [ ] Reviewer color chips in the RTD table (palette shared with step 4).
- [ ] Progress ring in dashboard metrics.
- [ ] Browser verification at desktop + mobile widths of: login, reviews
      list, new review, dashboard, members, edit-copy (old viewer still in
      place at this step), finding, implement, admin users, account password,
      delete confirm.
- [ ] Suite green; commit
      `feat(web): ALUM app-shell redesign — sidebar, organic components (v2 step 3)`.

## Definition of Done

Every page renders inside the shell with no horizontal scroll at 375 px and
1280 px; all existing tests green; no route/permission change; fonts remain
vendored; no CDN request appears in the network log.

## Out of scope

- Dark mode (explicitly deferred by Alberto).
- The document viewer itself (step 4) — edit-copy merely inherits the shell.

## Sources

- `00-design.md` §9; decision table §2 (Alberto, 2026-07-27).
- alum-brand-identity skill (`references/brand.md`); v1.9 tokens in
  `src/malus/web/static/app.css`.
