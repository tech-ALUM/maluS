# Step 8 — Deployment & Operations

## Objective

Run maluS on the company server: containerized, behind HTTPS, configurable,
backed up.

## Deliverables

- [ ] `Dockerfile` (app) and `docker-compose.yml` (app + optional Postgres)
- [ ] `.env.example` — all config (DB URL, secret key, session settings,
      admin bootstrap, `MALUS_AI_ENGINE`); no secret committed
- [ ] Reverse-proxy guidance for TLS (Caddy or nginx) with a sample config
- [ ] DB backup + restore script (SQLite file copy or `pg_dump`)
- [ ] Healthcheck endpoint; structured logging
- [ ] `docs/ops/runbook.md` — deploy, upgrade, backup/restore, rotate secrets

## Key behaviors

- One command (`docker compose up -d`) brings up the app on the server.
- Secrets only via environment; first run seeds the admin and forces a password
  change. SQLite in WAL mode for v1; switching to Postgres is a compose + env
  change (same ORM), documented.

## Definition of Done

A clean checkout deploys via compose to a fresh host and serves the app over
HTTPS behind the proxy; a backup can be taken and restored; the runbook is
sufficient for a newcomer; suite green (config/smoke tests).

## Out of scope

Multi-node / high availability; managed cloud specifics.

## Sources

v1 design session 2026-07-09 (company-server hosting).
