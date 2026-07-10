# Step 5 — Web GUI: Dashboard & RTD

## Objective

The browser front end for login and for the disposition/verification cycle,
built on the Step-3 API. Carries over the v0 `rtd.html` logic into a served,
multi-user app with ALUM branding.

## Deliverables

- [x] Login / logout pages; session-aware navigation
- [x] Review list (the reviews the user can see, by role)
- [x] Review dashboard: counts by status/severity, progress
- [x] RTD table: sort + filter by status/reviewer/type/severity/disposition
- [x] Finding detail: comment, threaded reply, disposition + resolution editing
      (owner), verify/reopen (reviewer/moderator) — actions gated by role
- [x] Status transitions mirror the server rules (no client-only authority)
- [x] Consistent ALUM styling (coral #FF6F61, teal #0E7C86, ink #15181D;
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

## Deviations

Details in `memory/decisions/2026-07-10-v1-step-05-decisions.md`.

- **Server-rendered forms + vendored HTMX (`hx-boost`)**: the flow works with
  JavaScript disabled (plain forms); htmx is vendored (no runtime CDN) and only
  smooths navigation. Saves are per-action forms (functionally the small,
  auditable saves the plan calls for) rather than per-field PATCH-in-place.
- **Fonts** are named (Space Grotesk / Inter / JetBrains Mono) with robust system
  fallbacks; the woff2 files are not vendored in-repo (added at deploy) — no CDN
  is referenced.
- **Dashboard** shows status counts + a closed-progress metric; **severity** is a
  filter on the RTD table rather than a separate count tile. The RTD table
  filters by status/reviewer/type/severity/disposition; rows are in document
  order (interactive column sort deferred — filtering covers the DoD).
- **"Threaded reply"** is the single owner `reply` field plus reopen-appended
  notes (the v0 RID model), not a multi-message thread.
- The GUI is a presentation layer over the **same services + authorization** as
  the API (no second authority). `/ui/*` pages redirect to `/ui/login` when
  anonymous (the JSON API returns 401). Review creation/harvest have no GUI page
  in Step 5 (seeded via API/admin; the editor arrives in Step 6).

## Sources

v1 design session 2026-07-09; v0 GUI behavior (`gui/rtd.html`).
