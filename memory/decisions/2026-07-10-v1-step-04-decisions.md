---
title: v1 Step 4 — Authentication & Roles Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-04-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- auth
- rbac
---

# v1 Step 4 — Authentication & Roles Decisions

Decisions implementing v1 Step 4 (docs/plan/v1/04-auth-and-roles.md): every
endpoint behind login, review-scoped RBAC, and the closure invariant enforced
server-side. The v0 reviewer name string is now backed by an authenticated user.

## Observations

- [decision] Auth mechanism (Alberto's choice via AskUserQuestion): signed httponly SameSite=strict session cookie via Starlette SessionMiddleware. SameSite=strict is the CSRF protection (no token dance); natural for the HTMX GUI. A bearer/API-token path for the AI agent is deferred to Step 7 #auth
- [decision] Passwords hashed with argon2 (argon2-cffi). Deps added: argon2-cffi, itsdangerous #passwords
- [decision] Global vs review-scoped roles: `admin` is a global User flag (is_admin; user management only, no review-content power). owner/reviewer/moderator are review-scoped (ReviewMember). `is_ai` marks AI principals; `must_change_password` supports bootstrap #roles
- [decision] Authorization (malus.api.authz) wired into every route via a router-level get_current_user dependency (401) + per-route role checks (403). Matrix: owner = DUR/freeze/answer/implement/changes/finalize (never verify); reviewer = own copy + verify/reopen own RIDs; moderator = harvest/triage + verify on behalf; AI = never verify/reopen. Services still enforce closure as defense-in-depth #authz
- [decision] Actor = the authenticated user; reviewer/owner dropped from request bodies. verify/reopen derive the actor + moderator-on-behalf from the caller's role. Audit records the actor by threading by=user through the services #actor
- [decision] Role assignment: POST /reviews/{id}/reviewers gained a role field (reviewer|moderator) so the owner can seat a moderator (no role-assignment endpoint existed). The review creator becomes owner. harvest/triage require moderator; apply-suggs allows owner or moderator #role-assignment
- [decision] First-run admin bootstrap from MALUS_ADMIN_USER/MALUS_ADMIN_PASSWORD on an empty user table (must_change_password=true). Dev session-secret fallback; production must set MALUS_SECRET_KEY. No secret committed #bootstrap
- [context] /openapi.json and /docs remain public; all review/user endpoints require auth. must_change_password is surfaced but not hard-gated in Step 4 (GUI prompts in Step 5) #scope
- [context] 142 tests pass; boundaries covered: 401 unauth, 403 owner-verify / cross-reviewer / AI-verify / non-owner, admin-only, audit-actor. Migration chain (initial -> user auth columns) applies on a fresh DB #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 3 — HTTP API Decisions]]
- enforces [[Architecture Decisions 2026-07-03]] (D3 reviewer-side closure) at the transport boundary

## Sources
- docs/plan/v1/04-auth-and-roles.md
- Implementation: src/malus/auth/ (passwords, service, deps, routes), src/malus/api/authz.py, SessionMiddleware + bootstrap in api/app.py, migration 8208e7694462
- Claude Code session with Alberto Boffi, 2026-07-10
