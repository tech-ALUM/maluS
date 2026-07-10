# Step 4 — Authentication & Roles

## Objective

Put every endpoint behind login and enforce role-based permissions and the
closure invariant on the server.

## Deliverables

- [x] User registration/admin-create, login, logout; passwords hashed (argon2)
- [x] Session cookies (httponly, secure) or JWT; CSRF protection if cookies
- [x] Review-scoped roles: admin, owner, reviewer, moderator
- [x] Authorization dependency applied to all routers
- [x] First-run admin bootstrap (env-seeded, forced password change)
- [x] Tests for each permission boundary

## Permission rules (server-enforced)

- **owner**: edit the DUR, freeze, reply/disposition RIDs, create changes,
  finalize. **Cannot** verify/close anything.
- **reviewer**: edit only *their own* copy; verify/reopen only *their own* RIDs.
- **moderator**: run harvest/triage; verify on a reviewer's behalf (recorded as
  such in the audit log).
- **admin**: manage users; no special power over review content.
- **AI principals**: authenticate as a reviewer identity (Step 7) but a policy
  flag forbids any verify/close/disposition-confirm action, regardless of role.
- Reviewer identity is now the authenticated user (the v0 name string is
  replaced; existing RIDs map reviewer → user on import).

## Tasks

1. User model + auth flows; secure password storage; session/JWT.
2. Authorization dependency reading review-scoped role; wire into all routes.
3. Encode the closure invariant and per-role rules as explicit checks with
   tests that a wrong actor is rejected (owner-verifies → 403).
4. Admin bootstrap + user management endpoints.

## Definition of Done

No endpoint is reachable unauthenticated; an owner attempting to verify is
rejected server-side; a reviewer cannot touch another's copy or RID; audit log
records actor identity for every mutation; suite green.

## Out of scope

UI for login/user management (Step 5 renders it). SSO/OAuth (future).

## Deviations

Auth mechanism settled with Alberto via AskUserQuestion; details in
`memory/decisions/2026-07-10-v1-step-04-decisions.md`.

- **Auth mechanism (chosen):** signed httponly `SameSite=strict` session cookie
  (Starlette `SessionMiddleware`). SameSite=strict is itself the CSRF protection,
  so there is no CSRF-token dance. A bearer/API-token path for the AI agent is
  deferred to Step 7.
- **Role assignment:** `POST /reviews/{id}/reviewers` gained a `role` field
  (`reviewer`|`moderator`) so the owner can seat a moderator — the endpoint map
  had no role-assignment route. The review creator becomes the owner.
- **Pipeline authorization:** harvest/triage require **moderator** (per the
  rules); apply-suggs is allowed for **owner or moderator** (the plan did not
  assign it). A review therefore needs a moderator seat to consolidate.
- **Audit actor:** recorded for every mutation by threading `by=<current user>`
  through the services (added a `by` parameter to harvest/triage/link_change/
  update_rid).
- **`must_change_password`** is surfaced (bootstrap admin + admin-created users)
  but not hard-gated in Step 4 — the login GUI prompts for it in Step 5.
- **Public docs:** `/openapi.json` and `/docs` stay open (documentation); every
  review/user resource endpoint requires authentication.
- **AI restriction** is enforced at the authz layer (`is_ai` → 403 on
  verify/reopen); the disposition-confirm restriction is a Step-7 concern.
- Dev fallback session secret (`dev-insecure-secret-change-me`); production must
  set `MALUS_SECRET_KEY`. No secret is committed.

## Sources

v1 design session 2026-07-09; closure invariant from v0 ADRs.
