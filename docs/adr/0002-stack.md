# ADR 0002 — v1 technology stack

- **Status:** Accepted
- **Date:** 2026-07-09
- **Deciders:** Alberto Boffi (v1 design session); implemented by Claude Code
- **Depends on:** ADR 0001 (the web pivot this stack serves)

## Context

ADR 0001 turns maluS into a self-hosted web application with a database store,
authentication, an HTTP API consumed by *both* a browser GUI and an AI agent, and
Docker deployment. We need a concrete stack that is Python-native (to reuse the
v0 domain core directly), API-first, typed, low-dependency, and free to run.

The v0 dependency rule ("no third-party runtime dependencies beyond PyYAML and
Typer without a recorded decision") still applies; this ADR is that recorded
decision for the v1 additions.

## Decision

- **Language:** Python 3.12 — same as v0, so `malus.models`/`parser`/`triage`/
  `lifecycle`/`report` are reused as-is.
- **Web framework:** FastAPI — async, typed, automatic OpenAPI. The browser GUI
  and the AI agent consume the *same* HTTP API. *(introduced in Step 3)*
- **ORM / store:** SQLModel (SQLAlchemy 2.x + Pydantic v2) on **SQLite in WAL
  mode** for v1, **Postgres-ready** through the same ORM. *(Step 1)*
- **Migrations:** Alembic. *(Step 1)*
- **Auth:** username/password hashed with **argon2**; server-side sessions or
  JWT; review-scoped RBAC (admin / owner / reviewer / moderator). *(Step 4)*
- **AI transport:** an **MCP server** (plus the REST API) exposing review tools;
  Claude Code connects interactively. *(Step 7)*
- **Front end:** served by FastAPI — HTML + CSS + vanilla JS (HTMX) with
  CodeMirror 6 for the Markdown editor. Assets vendored; **no runtime CDN**.
  *(Steps 5–6)*
- **Deployment:** Dockerfile + docker-compose, TLS via a reverse proxy
  (Caddy/nginx), `.env` configuration, DB backups, first-run admin bootstrap.
  *(Step 8)*

**Cross-cutting rules.** Enum/status/type values remain owned by
`malus.constants`; DB columns store the enum `.value`. No secret (API key,
password) is ever committed; configuration is read from `.env`.

**Dependency phasing.** Step 1 adds only `sqlmodel` and `alembic` as runtime
dependencies. FastAPI, the argon2 hasher, the MCP SDK, HTMX/CodeMirror assets,
etc. are each added by the step that first uses them — all authorised by this
ADR.

## Consequences

- **(+)** One typed HTTP contract for GUI + AI; OpenAPI generated for free.
- **(+)** SQLite → Postgres with no ORM change; schema changes are versioned via
  Alembic.
- **(+)** Runtime dependencies stay minimal and are introduced incrementally; no
  runtime CDN.
- **(−)** SQLModel is younger than raw SQLAlchemy; we pin versions and keep the
  table models simple.
- **(−)** Async FastAPI over a synchronous domain core needs care at the boundary
  (addressed in Step 3).

## Alternatives considered

- **Django + DRF** — batteries-included but heavier and less async-native, and it
  duplicates the ORM/validation we already get from SQLModel/Pydantic; the domain
  core is plain Python and needs no framework.
- **Flask + SQLAlchemy** — workable, but no built-in typing/OpenAPI and more
  glue code than FastAPI + SQLModel.
- **Raw SQLAlchemy (no SQLModel)** — more boilerplate; SQLModel unifies the table
  model and the Pydantic schema, which matches FastAPI. We accept SQLModel's
  relative youth as the trade-off.
- **A document/NoSQL store** — rejected: the data is inherently relational
  (reviews → documents → versions → RIDs → changes) and needs constraints plus an
  audit trail.
- **A Node/TypeScript stack** — rejected: it would abandon the reusable Python
  domain core.

## Sources

- `docs/plan/v1/00-overview.md` — "Target architecture" and "Global Definition of
  Done".
- `docs/plan/v1/01-architecture-and-data-model.md` — Step 1 deliverables and
  tasks 3–4 (Alembic; enums as source of truth, columns store `.value`).
- `memory/knowledge/tech-stack.md` — the v0 stack and the runtime-dependency
  constraint this ADR satisfies.
- ADR 0001 — the pivot that motivates this stack.
