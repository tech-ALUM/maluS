---
title: v1 Step 5 — Web GUI (Dashboard & RTD) Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-05-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- gui
---

# v1 Step 5 — Web GUI (Dashboard & RTD) Decisions

The browser front end for login and the disposition/verification cycle
(docs/plan/v1/05-gui-dashboard-rtd.md), built on the Step-3/4 API.

## Observations

- [decision] Server-rendered Jinja pages under /ui/*, mounted alongside the JSON API; a StaticFiles mount at /static. Plain HTML forms are the primary mechanism (work with JS disabled); htmx is vendored (no runtime CDN) and applied via hx-boost for smoother navigation #gui
- [decision] The GUI is a presentation layer over the SAME services + malus.api.authz as the API — no client-only authority. The owner is never rendered a verify control, and the server refuses a forged owner-verify (403). /ui/* redirect to /ui/login when anonymous (API returns 401) #authority
- [decision] ALUM styling in one vendored CSS: coral #FF6F61, teal #0E7C86, ink #15181D; fonts named Space Grotesk/Inter/JetBrains Mono with system fallbacks (woff2 vendored at deploy, no CDN) #styling
- [decision] Pages: login, review list (with the caller's role per review), review dashboard (status counts + closed-progress) + filterable RTD table (status/reviewer/type/severity/disposition), and a finding page with an owner disposition form and a reviewer/moderator verify+reopen form #pages
- [context] Deviations: per-action forms rather than per-field PATCH-in-place; severity is a filter not a count tile; RTD rows in document order (column sort deferred); reply is the single owner field + reopen notes (not a multi-message thread); review creation/harvest have no GUI page in Step 5 (API/admin seeds them; editor is Step 6) #deviations
- [context] Deps added: jinja2, python-multipart. 149 tests pass; the disposition+verification cycle is exercised end-to-end in the browser via TestClient, with audit-actor asserted #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 4 — Authentication & Roles Decisions]]

## Sources
- docs/plan/v1/05-gui-dashboard-rtd.md
- Implementation: src/malus/web/ (router, templates, static/app.css, vendored htmx); static mount + web router in api/app.py
- Claude Code session with Alberto Boffi, 2026-07-10
