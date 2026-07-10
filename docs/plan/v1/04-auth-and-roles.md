# Step 4 — Authentication & Roles

## Objective

Put every endpoint behind login and enforce role-based permissions and the
closure invariant on the server.

## Deliverables

- [ ] User registration/admin-create, login, logout; passwords hashed (argon2)
- [ ] Session cookies (httponly, secure) or JWT; CSRF protection if cookies
- [ ] Review-scoped roles: admin, owner, reviewer, moderator
- [ ] Authorization dependency applied to all routers
- [ ] First-run admin bootstrap (env-seeded, forced password change)
- [ ] Tests for each permission boundary

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

## Sources

v1 design session 2026-07-09; closure invariant from v0 ADRs.
