# maluS v1 — Web Application (self-hosted)

The pivot: maluS moves from a local, git-based CLI toolkit (v0.1.0) to a
**self-hosted web application** on the company server. Everything happens in
the browser — including the Markdown editor — behind user login. Git is
removed; a database becomes the store. Claude Code can act as a reviewer
through maluS's own API, driven interactively under the user's Claude
subscription, so no paid Anthropic API is required.

## What changes vs v0

| Concern | v0.1.0 | v1 |
|---|---|---|
| Store / transport | files + git | database (SQLite→Postgres) |
| Reviewer copies | `reviewers/<name>.md` files | rows owned by a logged-in user |
| Identity | a name string | authenticated user account |
| Freeze / baseline | pinned git commit SHA | immutable `DocumentVersion` (content hash) |
| Traceability | RID ids in commit messages | in-app edits linked to RIDs + audit log |
| Disposition / editing | double-click `rtd.html`, edit files | web GUI + in-browser MD editor |
| AI reviewer | `--engine anthropic` (paid API) | maluS MCP/API + interactive Claude Code (free) |
| Delivery | `pipx install` | Docker Compose on the company server |

## What is kept

The domain core is storage-agnostic and is **reused**: `models` (enums,
lifecycle, RID/RTD), `parser` (comment blocks), `triage` (clustering,
suggestions), `lifecycle` (transitions, closure invariant), `report`
(minutes). Only the persistence and transport layers are replaced.
`rtd.yaml` survives as an **import/export interchange format**, not the store.

## Invariants preserved (non-negotiable)

- Only a **reviewer** (or moderator on their behalf) may mark a finding
  `verified`. The owner never can; an AI never can. Enforced server-side.
- Reviewers add only comment blocks to a copy (freeze rule); enforced in the
  editor and re-validated on the server by the existing parser.
- Every AI-submitted artifact is attributed and can never verify/close.

## Target architecture

- **Backend:** Python 3.12 + FastAPI (async, typed, auto-OpenAPI). **API-first**:
  the browser GUI and the AI agent consume the *same* HTTP API.
- **Store:** SQLModel (SQLAlchemy + Pydantic) on SQLite in WAL mode for v1,
  Postgres-ready via the same ORM; Alembic migrations.
- **Auth:** username/password (hashed, argon2), server-side sessions or JWT;
  RBAC roles admin / owner / reviewer / moderator.
- **Frontend:** served by FastAPI; HTML + CSS + vanilla JS (HTMX for
  interactivity); CodeMirror 6 for the Markdown editor. No heavy SPA framework;
  no runtime CDN (assets vendored). ALUM brand styling.
- **AI:** maluS exposes an **MCP server** (and the REST API) with review tools;
  Claude Code connects interactively (user's subscription) and submits comments.
  An optional server-side headless engine stays behind a flag (paid path).
- **Deploy:** Dockerfile + docker-compose; TLS via reverse proxy (Caddy/nginx);
  `.env` config; DB backups; first-run admin bootstrap.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-architecture-and-data-model.md` | ADR (git removal, stack), DB schema, model mapping | — |
| 2 | `02-persistence-off-git.md` | Repository layer; core runs on the DB; freeze+traceability without git | 1 |
| 3 | `03-api.md` | FastAPI, full pipeline over HTTP, OpenAPI | 1,2 |
| 4 | `04-auth-and-roles.md` | Accounts, login, RBAC, server-side invariant enforcement | 3 |
| 5 | `05-gui-dashboard-rtd.md` | Web GUI: login, review list, RTD table, disposition, verify | 3,4 |
| 6 | `06-gui-editor-reviewer.md` | In-browser MD editor; reviewer commenting; owner implementation | 5 |
| 7 | `07-ai-reviewer-mcp.md` | maluS MCP/API; interactive Claude Code as reviewer; no Anthropic API | 3,4 |
| 8 | `08-deployment.md` | Docker, TLS, config, backups, admin bootstrap | 3–7 |
| 9 | `09-e2e-and-release.md` | Multi-user E2E, v0 import, docs, tag v1.0.0 | all |
| 10 | `10-account-gui.md` | Account-management GUI: self-service password, admin user CRUD, per-review role assignment | 4,5 |
| 11 | `11-caddy-compose.md` | Caddy reverse proxy in docker-compose (TLS; app loopback-only) | 8 |

Steps 1–9 are v1.0.0. Steps 10–11 are post-1.0.0 hardening for self-hosting
(added 2026-07-10). Implemented one step at a time. Kickoff prompt: `90-kickoff.md`.

## Global Definition of Done

- `python -m pytest -q` green at the end of every step.
- No secret (API key, password) ever committed; config via `.env`.
- Each architectural deviation recorded in the step file and in
  `memory/decisions/`.

## Sources

Design session with Alberto Boffi, Claude chat, 2026-07-09: the v1 pivot
(company server, full GUI, MD editor, login, git removal, AI reviewer via
Claude Code without the paid Anthropic API). AI-billing constraint verified
against Anthropic support/pricing (June 15 2026 programmatic-usage change).
