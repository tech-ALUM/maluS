# Changelog

## v1.2.0 — 2026-07-12 (member management & reviewer onboarding)

- **Reviewer account picker + member management** (Step 1): the Members page
  assigns *existing* accounts through a searchable typeahead (by stable
  `username`) — a typo can no longer spawn a phantom user; plus inline role
  change and member removal. An owner-safety guard keeps the primary owner
  (`Review.owner_id`) from being demoted/removed, so a review always has ≥1
  owner; removing a member preserves their harvested RIDs.
- **Reviewer onboarding & hand-off** (Step 2): after assignment a reviewer is
  pointed straight to commenting — a prominent landing CTA on the review page, a
  "Copy review link" control for owner/admin, and a "to comment" badge in the
  review list that clears once the reviewer submits. No email/SMTP: the link is
  the existing authenticated review URL.
- **API hardening**: `POST /reviews/{id}/reviewers` now requires an existing,
  active account and rejects an unknown/inactive name (422) instead of creating
  a placeholder — consistent with the GUI. Bulk `create_review` and the legacy
  `import` path are unchanged (import still materializes placeholder users from
  `rtd.yaml` names by design).

## v1.1.0 — 2026-07-10 (self-hosting hardening)

- **Account-management GUI** (Step 10): self-service password change, admin user
  CRUD (create incl. AI reviewer, deactivate/reactivate, reset password), and
  per-review role assignment — server-side, admin-gated; forced password change
  at first login. Closure invariant unchanged.
- **Caddy in docker-compose** (Step 11): a `caddy` service terminates TLS on
  80/443 and proxies to the app (loopback-only) over the compose network;
  `MALUS_DOMAIN` for auto-HTTPS. One-command HTTPS deploy.
- **Create a review from the GUI** (Step 12): `/ui/reviews/new` (create + freeze
  in one step; creator = owner); login now shows an error on wrong credentials.

## v1.0.0 — 2026-07-10

maluS becomes a **self-hosted web application**. The reusable domain core
(`models`, `parser`, `triage`, `lifecycle`, `report`) is unchanged; persistence
and transport are replaced.

### Added
- **Database store** (SQLModel on SQLite/WAL, Postgres-ready) + Alembic
  migrations; `docs/spec/data-model.md`. Freeze is an immutable `DocumentVersion`
  (content hash); RID traceability is `RidChange` + an `AuditLog` (ADR 0001/0002).
- **Repository + service layer** — the whole pipeline runs on the DB.
- **HTTP API** (FastAPI, OpenAPI at `/docs`) — one typed contract for the GUI and
  the AI agent; `malus serve`.
- **Authentication & RBAC** — argon2 passwords, httponly `SameSite=strict`
  session cookies, review-scoped roles (owner/reviewer/moderator + global admin),
  first-run admin bootstrap. Closure invariant enforced server-side; every
  mutation is attributed in the audit log.
- **Web GUI** (server-rendered Jinja + HTMX, ALUM styling): login, review list,
  dashboard, filterable RTD table, disposition/verify, and an in-browser Markdown
  **editor** (reviewer commenting + owner implementation with RID-linked versions).
- **AI reviewer via MCP** — `malus mcp` exposes review tools driven by an
  interactive Claude Code session; **no paid Anthropic API** on the server. AI
  principals can never verify/close/confirm (`is_ai` guardrail). Optional paid
  server-side engine behind `MALUS_AI_ENGINE`, off by default.
- **Deployment** — Dockerfile + docker-compose (optional Postgres), `.env.example`,
  reverse-proxy TLS sample, backup/restore scripts, `/health`, JSON logging,
  `docs/ops/runbook.md`.
- **v0 import** — `malus import <dir>` loads a legacy review directory into the DB;
  `rtd.yaml` survives as an import/export interchange format.
- Multi-user end-to-end tests (human + AI reviewer, GUI + API + MCP, finalized).

### Changed
- `malus` CLI is now `serve` / `mcp` / `import` (the v0 file pipeline is retired).
- Documentation rewritten for the web app (`README.md`, `docs/usage.md`).

### Removed
- **git** as store/transport (no git call anywhere in `src/`).
- The v0 file/CLI pipeline and the v0 `--engine anthropic` reviewer path.

### Legacy
- `gui/rtd.html` (v0 single-file GUI) retained, clearly marked legacy.

## v0.1.0

Initial local, git-based, text-first CLI: freeze → per-reviewer copies → harvest
`rtd.yaml` → triage → disposition (single-file `gui/rtd.html`) → verify →
finalize. See `docs/plan/00-general-plan.md`.
