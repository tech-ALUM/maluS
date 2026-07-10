# maluS

Document review management for Markdown documents, modeled on formal
aerospace-style RID (Review Item Discrepancy) review processes.

**v1 is a self-hosted web application.** A database (not git) is the store;
reviewers, owners and moderators — human or AI — work through the browser behind
login. An AI reviewer participates for free by connecting Claude Code
interactively to maluS's MCP server (no paid Anthropic API on the server).

## The review cycle

1. **Freeze** an immutable baseline of the Document Under Review (DUR).
2. Reviewers insert structured inline comment blocks
   (`{COMM|type=…|sev=…: …}`, `{SUGG: "old" -> "new"}`) into their own copy —
   never editing the baseline text (the *freeze rule*, enforced by the parser).
3. **Harvest** extracts all comments into RIDs (one tracked finding each).
4. **Triage** clusters duplicates and batch-applies mechanical suggestions.
5. The **owner** dispositions each RID (accept / reject / defer) in the GUI.
6. Accepted RIDs are **implemented** in the in-browser editor, creating a new
   document version linked to the RIDs it resolves (the traceability record —
   no git needed).
7. **Reviewers — never the owner — verify and close** each RID.
8. **Finalize** produces the finalized document plus review minutes.

The three roles (owner, reviewer, moderator) can each be a human or an AI. The
reviewer-side closure authority — *only a reviewer or a moderator on their
behalf may verify; the owner never can; an AI never can* — is the safety control
that makes AI participation sound, and it is enforced server-side.

## Deploy

```sh
cp .env.example .env          # set MALUS_SECRET_KEY + admin bootstrap; never commit .env
docker compose up -d --build  # migrates, then serves on 127.0.0.1:8000
```

Put a TLS reverse proxy in front (`deploy/Caddyfile`), then open
`https://<host>/ui/login`. SQLite (WAL) by default; Postgres is a `.env` +
profile change. Full operations guide: **[docs/ops/runbook.md](docs/ops/runbook.md)**.

## Use

- Web GUI: log in, open a review, disposition/verify, edit in the browser.
- HTTP API: the same operations, typed, at `/docs` (OpenAPI). `malus serve` runs it.
- AI reviewer (free, interactive): **[docs/usage/ai-reviewer.md](docs/usage/ai-reviewer.md)**.
- Full walkthrough (human and AI modes): **[docs/usage.md](docs/usage.md)**.

## Migrating from v0

A v0 file-based review imports into the DB:

```sh
malus import path/to/reviews/<review-id>   # baseline.md + rtd.yaml + reviewers/*.md
```

The v0 single-file GUI `gui/rtd.html` is retained as **legacy** (see `gui/README.md`).

## Stack

Python 3.12 · FastAPI · SQLModel (SQLite→Postgres) · Alembic · argon2 ·
Jinja + HTMX GUI · MCP · Docker. See `docs/adr/`.

## Status

**v1.0.0.** Suite: `python -m pytest -q` (green). Plan: `docs/plan/v1/`.

## Repository layout

| Path | Content |
|---|---|
| `src/malus/db`, `repo`, `services` | schema, repositories, DB-backed pipeline |
| `src/malus/api`, `auth`, `web` | HTTP API, auth/RBAC, server-rendered GUI |
| `src/malus/mcp`, `legacy` | MCP AI-reviewer server; v0 import |
| `src/malus/{models,parser,triage,harvest,report,lifecycle}.py` | reused domain core |
| `alembic/` | migrations · `Dockerfile`, `docker-compose.yml`, `deploy/`, `scripts/` |
| `docs/adr`, `docs/plan/v1`, `docs/spec`, `docs/ops`, `docs/usage*` | decisions, plan, contracts, ops, guides |
| `gui/rtd.html` | legacy v0 single-file GUI |
| `tests/` | pytest suite (db, api, web, mcp, ops, e2e) |
| `memory/` | design decisions & specs |
