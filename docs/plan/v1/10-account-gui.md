# Step 10 — Account Management GUI

Added post-v1.0.0 (requested by Alberto, 2026-07-10) to make a hosted instance
self-sufficient: account and role management from the browser, not just the API.

## Objective

Server-rendered, admin-gated account management under `/ui`: self-service
password change, admin user CRUD + activation + reset, and per-review role
assignment — consistent with the ALUM-styled GUI.

## Deliverables

- [x] Self-service "change my password" page (`/ui/account/password`)
- [x] Admin area (`/ui/admin/users`): list users; create user (username, display
      name, temporary password, kind: regular / admin / AI reviewer);
      deactivate / reactivate; reset password
- [x] Per-review role assignment (owner / reviewer / moderator) from the GUI
      (`/ui/reviews/{id}/members`)
- [x] Force password change at first login (server-side redirect until resolved)
- [x] Admin-only enforced server-side; the closure invariant is unchanged
      (an AI never verifies/closes)
- [x] An AI-reviewer account is created from this GUI (a user + the `is_ai`
      policy flag); its credentials are then used by the MCP server
- [x] ALUM styling (coral #FF6F61, teal #0E7C86, ink #15181D; Space Grotesk /
      Inter / JetBrains Mono)

## Key behaviors

- Every action goes through the existing `malus.auth` service + authorization;
  the GUI adds no authority the server does not also enforce. Admin pages return
  403 for non-admins even if the URL is guessed. While `must_change_password` is
  set, the rest of `/ui` redirects to the password page.

## Definition of Done

A user changes their own password; an admin creates users (including an AI
reviewer), deactivates/reactivates and resets passwords, and assigns per-review
roles — all in the browser; a non-admin is refused the admin pages server-side; a
freshly created user is forced to change their password before using the app;
suite green (view/route tests).

## Out of scope

Email flows / password-reset-by-token; SSO.

## Deviations

Details in `memory/decisions/2026-07-10-v1-step-10-decisions.md`.

- **Force-change** is enforced by a middleware (added before `SessionMiddleware`
  so it runs with the session populated) that redirects `/ui` pages to the
  password page until `must_change_password` clears. Scoped to the GUI — the API
  / Basic-auth path is not gated (the flag is a first-login UX control). The flag
  is mirrored in the session at login (no per-request DB hit) and cleared on change.
- **No new API endpoints** — the GUI reuses `malus.auth.service` + the
  repositories (added `ReviewRepo.set_member_role`/`members`).
- **Per-review roles**: `/ui/reviews/{id}/members` (owner or admin) can assign
  owner/reviewer/moderator; assigning `owner` to another user makes a co-owner.
- **Test fixtures** onboard users by default (the normal post-first-login state);
  the force-change behaviour is tested explicitly with `onboard=False`.

## Sources

Requested by Alberto Boffi, 2026-07-10 (post-v1.0.0 hardening for self-hosting).
