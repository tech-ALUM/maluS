# Step 10 — Account Management GUI

Added post-v1.0.0 (requested by Alberto, 2026-07-10) to make a hosted instance
self-sufficient: account and role management from the browser, not just the API.

## Objective

Server-rendered, admin-gated account management under `/ui`: self-service
password change, admin user CRUD + activation + reset, and per-review role
assignment — consistent with the ALUM-styled GUI.

## Deliverables

- [ ] Self-service "change my password" page (`/ui/account/password`)
- [ ] Admin area (`/ui/admin/users`): list users; create user (username, display
      name, temporary password, kind: regular / admin / AI reviewer);
      deactivate / reactivate; reset password
- [ ] Per-review role assignment (owner / reviewer / moderator) from the GUI
      (`/ui/reviews/{id}/members`)
- [ ] Force password change at first login (server-side redirect until resolved)
- [ ] Admin-only enforced server-side; the closure invariant is unchanged
      (an AI never verifies/closes)
- [ ] An AI-reviewer account is created from this GUI (a user + the `is_ai`
      policy flag); its credentials are then used by the MCP server
- [ ] ALUM styling (coral #FF6F61, teal #0E7C86, ink #15181D; Space Grotesk /
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

## Sources

Requested by Alberto Boffi, 2026-07-10 (post-v1.0.0 hardening for self-hosting).
