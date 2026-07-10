# Step 11 — Caddy in docker-compose (TLS, all-in-stack)

Added post-v1.0.0 (requested by Alberto, 2026-07-10). "Option B" of the Step-8
deployment: bring TLS into the compose stack so one `docker compose up -d`
serves the app over HTTPS.

## Objective

A `caddy` service reverse-proxies to the app over the internal compose network
and terminates HTTPS on 80/443. The app is published only on loopback.

## Deliverables

- [x] `caddy` service in `docker-compose.yml`: `reverse_proxy app:8000`, ports
      80/443, persistent volumes for certs/config
- [x] The app is published **only on loopback** (`127.0.0.1`); Caddy is the sole
      public entry point
- [x] A compose Caddyfile (`deploy/Caddyfile.docker`) with the domain from
      `${MALUS_DOMAIN}` (`malus.<DOMINIO>`)
- [x] `.env.example`: `MALUS_DOMAIN`; runbook updated for the all-in-stack path
- [x] Config / smoke tests

## Definition of Done

`docker compose up -d` starts `app` + `caddy`; Caddy holds 80/443 and proxies to
`app:8000` (the app is not publicly published); the Caddyfile uses the configured
domain and auto-provisions TLS; suite green (config tests).

## Out of scope

Non-Caddy proxies (the nginx sketch stays in `deploy/Caddyfile`).

## Deviations

Details in `memory/decisions/2026-07-10-v1-step-11-decisions.md`.

- The compose Caddyfile is a **separate file** (`deploy/Caddyfile.docker`,
  `reverse_proxy app:8000`) distinct from the host-native `deploy/Caddyfile`
  (`127.0.0.1:8000`); domain via `${MALUS_DOMAIN}`.
- The app keeps a **loopback** publish (`127.0.0.1:8000`) for local debugging; it
  is not public. Caddy reaches it over the compose network.
- Verified by config/smoke tests (no live Docker/Caddy run in this environment);
  a real host provisions the TLS cert on first start.

## Sources

Requested by Alberto Boffi, 2026-07-10 (Option B — Caddy inside the compose stack).
