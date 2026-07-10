---
title: v1 Step 11 — Caddy in docker-compose Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-11-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- deployment
- caddy
---

# v1 Step 11 — Caddy in docker-compose Decisions

"Option B" of Step 8: TLS inside the compose stack (docs/plan/v1/11-caddy-compose.md).

## Observations

- [decision] Added a `caddy` service to docker-compose.yml: image caddy:2, ports 80/443, cert/config volumes (caddy-data, caddy-config), reverse_proxy to app:8000 over the compose network. `docker compose up -d` now serves HTTPS #caddy
- [decision] The app is published only on loopback (127.0.0.1:8000) for local debugging; Caddy is the sole public entry point #loopback
- [decision] Compose Caddyfile is a separate file deploy/Caddyfile.docker (reverse_proxy app:8000, domain from ${MALUS_DOMAIN}); the host-native deploy/Caddyfile (127.0.0.1:8000) remains as the alternative. .env.example + runbook updated #caddyfile
- [context] Verified by config/smoke tests (compose has app+caddy, 80/443 published, app loopback-only, proxy to app:8000, cert volume); no live Docker run here. 179 tests pass #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 10 — Account Management GUI Decisions]]
- extends [[v1 Step 8 — Deployment & Operations Decisions]]

## Sources
- docs/plan/v1/11-caddy-compose.md
- Implementation: docker-compose.yml (caddy service), deploy/Caddyfile.docker, .env.example (MALUS_DOMAIN), docs/ops/runbook.md
- Claude Code session with Alberto Boffi, 2026-07-10
