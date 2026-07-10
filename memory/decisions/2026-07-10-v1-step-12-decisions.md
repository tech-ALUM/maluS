---
title: v1 Step 12 — GUI Review Creation + Login Feedback Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-12-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- gui
---

# v1 Step 12 — GUI Review Creation + Login Feedback Decisions

Post-v1.0.0 (requested by Alberto 2026-07-10): the browser could log in and run
the review cycle but a review still had to be created via the API; and a failed
login gave no visible feedback under hx-boost.

## Observations

- [decision] Added /ui/reviews/new (GET form + POST): the creating user becomes owner and the supplied baseline is frozen in one action; linked from the review list. Reviewers/moderators are added afterwards from the Members page (Step 10). Any authenticated user may create a review, matching the API #new-review
- [decision] Duplicate review id is checked before create and re-renders the form with an error (409); route declared before /ui/reviews/{review_id} so `new` is not captured as an id #new-review
- [decision] Login feedback: the server already re-rendered login with an error (401), but hx-boost ignores non-2xx responses; a global htmx:beforeSwap handler in base.html now renders 4xx bodies so the message shows. The no-JS native submit already rendered the 401 body #login
- [context] 182 tests pass; create-from-GUI (listed + baseline frozen), duplicate-id error, and login wrong-credentials message are covered (TestClient asserts the server render; the JS swap is not unit-tested) #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 11 — Caddy in docker-compose Decisions]]
- extends [[v1 Step 5 — Web GUI (Dashboard & RTD) Decisions]] and [[v1 Step 10 — Account Management GUI Decisions]]

## Sources
- docs/plan/v1/12-gui-review-creation.md
- Implementation: src/malus/web/router.py (/ui/reviews/new), templates/new_review.html, base.html (beforeSwap), reviews.html
- Claude Code session with Alberto Boffi, 2026-07-10
