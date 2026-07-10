# Step 5 — Web GUI: Dashboard & RTD

## Objective

The browser front end for login and for the disposition/verification cycle,
built on the Step-3 API. Carries over the v0 `rtd.html` logic into a served,
multi-user app with ALUM branding.

## Deliverables

- [ ] Login / logout pages; session-aware navigation
- [ ] Review list (the reviews the user can see, by role)
- [ ] Review dashboard: counts by status/severity, progress
- [ ] RTD table: sort + filter by status/reviewer/type/severity/disposition
- [ ] Finding detail: comment, threaded reply, disposition + resolution editing
      (owner), verify/reopen (reviewer/moderator) — actions gated by role
- [ ] Status transitions mirror the server rules (no client-only authority)
- [ ] Consistent ALUM styling (coral #FF6F61, teal #0E7C86, ink #15181D;
      Space Grotesk / Inter / JetBrains Mono)

## Key behaviors

- Server-rendered pages (Jinja) with HTMX for in-place updates; assets vendored
  (no runtime CDN). CodeMirror is introduced in Step 6.
- The GUI only ever calls the Step-3 API; it holds no authority the server
  doesn't also enforce (the *verified* action is simply absent for the owner).
- Saves are per-field (PATCH), keeping changes small and auditable.

## Definition of Done

A full disposition + verification pass on a seeded review is done entirely in the
browser by the appropriate roles; an owner never sees a usable verify control;
the audit log reflects every action; suite green (view/route tests).

## Out of scope

The Markdown editor and reviewer commenting flow (Step 6). Deployment (Step 8).

## Sources

v1 design session 2026-07-09; v0 GUI behavior (`gui/rtd.html`).
