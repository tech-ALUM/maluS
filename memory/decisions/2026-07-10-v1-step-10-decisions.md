---
title: v1 Step 10 — Account Management GUI Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-10-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- gui
- accounts
---

# v1 Step 10 — Account Management GUI Decisions

Post-v1.0.0 hardening (requested by Alberto 2026-07-10): manage accounts and
per-review roles from the browser, not just the API (docs/plan/v1/10-account-gui.md).

## Observations

- [decision] src/malus/web/accounts.py adds server-rendered, admin-gated pages: /ui/account/password (self-service), /ui/admin/users (list, create with kind regular/admin/AI-reviewer, deactivate/reactivate, reset), /ui/reviews/{id}/members (assign owner/reviewer/moderator; owner or admin). Reuses malus.auth.service + repos; no new API endpoints #gui
- [decision] Force password change at first login: a BaseHTTPMiddleware (added before SessionMiddleware so the session is populated) redirects /ui pages to the password page while must_change_password is set. The flag is mirrored into the session at login and cleared on change — no per-request DB hit. Scoped to the GUI; the API/Basic path is not gated #force-change
- [decision] Admin-only enforced server-side (403 for non-admins even if the URL is guessed); an admin cannot deactivate their own account. The closure invariant is untouched — an AI reviewer is just a user with is_ai, created here, whose credentials the MCP server then uses #authz
- [decision] Added ReviewRepo.set_member_role (upsert) + members(); per-review roles assignable from the GUI, co-owners allowed #roles
- [context] Shared test mkuser fixtures onboard users by default (clear must_change_password = normal post-first-login state); force-change tested with onboard=False. 174 tests pass #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 9 — E2E, Migration & Release v1.0.0 Decisions]]
- extends [[v1 Step 4 — Authentication & Roles Decisions]] and [[v1 Step 5 — Web GUI (Dashboard & RTD) Decisions]]

## Sources
- docs/plan/v1/10-account-gui.md
- Implementation: src/malus/web/accounts.py + templates (account_password, admin_users, admin_user_new, members); force-change middleware in api/app.py; ReviewRepo.set_member_role
- Claude Code session with Alberto Boffi, 2026-07-10
