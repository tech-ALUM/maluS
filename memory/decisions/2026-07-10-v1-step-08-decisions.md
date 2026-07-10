---
title: v1 Step 8 — Deployment & Operations Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-08-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- deployment
- ops
---

# v1 Step 8 — Deployment & Operations Decisions

Run maluS on the company server: containerized, behind HTTPS, configurable,
backed up (docs/plan/v1/08-deployment.md).

## Observations

- [decision] Dockerfile (python:3.12-slim, non-root uid 10001, /data volume) installs .[mcp]; entrypoint runs `alembic upgrade head` then `malus serve` on 0.0.0.0:8000. HEALTHCHECK hits /health #docker
- [decision] docker-compose.yml: app service bound to 127.0.0.1:8000 (proxy in front), named volume malus-data; optional Postgres under the `postgres` profile. `docker compose up -d` is the one-command deploy #compose
- [decision] Config via .env only (.env.example committed, real .env gitignored). MALUS_SECRET_KEY, admin bootstrap, MALUS_AI_ENGINE, MALUS_LOG_LEVEL, MALUS_DB_URL. No secret committed #config
- [decision] GET /health public liveness probe; structured JSON-line logging (malus.logging.configure_logging) enabled by `malus serve` #observability
- [decision] TLS terminated by a reverse proxy (deploy/Caddyfile sample; nginx sketch). SameSite=strict + Secure cookies are correct behind the proxy (browser<->proxy is HTTPS) #tls
- [decision] Backup/restore scripts (scripts/backup.sh, restore.sh) handle SQLite (.backup) and Postgres (pg_dump/psql), selected from MALUS_DB_URL. Postgres driver behind the [postgres] extra; rebuild the image with .[mcp,postgres] to use it #backup
- [context] No Docker in the build environment: validated by smoke tests (compose YAML valid, artifacts present, /health ok, JSON logger). Live `docker compose up` is the operator step in docs/ops/runbook.md. 164 tests pass #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 7 — AI Reviewer via MCP Decisions]]

## Sources
- docs/plan/v1/08-deployment.md
- Implementation: Dockerfile, docker-entrypoint.sh, docker-compose.yml, .env.example, deploy/Caddyfile, scripts/backup.sh+restore.sh, docs/ops/runbook.md; /health + malus/logging.py
- Claude Code session with Alberto Boffi, 2026-07-10
