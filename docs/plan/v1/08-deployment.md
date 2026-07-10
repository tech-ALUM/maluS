# Step 8 — Deployment & Operations

## Objective

Run maluS on the company server: containerized, behind HTTPS, configurable,
backed up.

## Deliverables

- [x] `Dockerfile` (app) and `docker-compose.yml` (app + optional Postgres)
- [x] `.env.example` — all config (DB URL, secret key, session settings,
      admin bootstrap, `MALUS_AI_ENGINE`); no secret committed
- [x] Reverse-proxy guidance for TLS (Caddy or nginx) with a sample config
- [x] DB backup + restore script (SQLite file copy or `pg_dump`)
- [x] Healthcheck endpoint; structured logging
- [x] `docs/ops/runbook.md` — deploy, upgrade, backup/restore, rotate secrets

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

## Deviations

Details in `memory/decisions/2026-07-10-v1-step-08-decisions.md`.

- **Verification is by smoke tests, not a live container build** (no Docker in
  this environment): the compose file parses, all artifacts exist, `/health`
  returns ok, and the JSON logger works. An actual `docker compose up` on a host
  is the operator action described in the runbook.
- **Migrations at startup:** the container entrypoint runs `alembic upgrade head`
  then `malus serve`. The default DB is SQLite on a named volume; **Postgres** is
  a `.env` + `--profile postgres` change, and the image must be rebuilt with the
  `[postgres]` extra (documented in the runbook + compose comment).
- **HTTPS** is terminated by a reverse proxy (Caddy sample provided; nginx
  sketch); the app binds `127.0.0.1:8000`. `SameSite=strict` + `Secure` cookies
  are correct behind the TLS proxy (the browser↔proxy hop is HTTPS).

## Sources

v1 design session 2026-07-09 (company-server hosting).
