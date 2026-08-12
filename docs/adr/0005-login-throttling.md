# ADR 0005 — Login throttling in the application, not at the edge

**Status:** accepted. **Date:** 2026-08-12.

## Context

maluS is published on the public internet as `malus.alum-lab.com`. A security
review of the host on 2026-08-12 established the exposure precisely:

- the container binds `127.0.0.1:8000` only (`docker-compose.yml`), so the app
  is reachable **exclusively** through the shared edge Caddy;
- that vhost (`/opt/alum/caddy/Caddyfile`) is a bare `reverse_proxy` — it adds
  **no** `basic_auth` and no `forward_auth`, so the application's own
  authentication is the only authentication that exists;
- credentials are verified in three places, all reaching
  `malus.auth.service.authenticate`: `POST /auth/login`, `POST /ui/login`, and
  HTTP Basic, which `malus.auth.deps.get_current_user` accepts on *every*
  protected endpoint;
- nothing limited the rate of those attempts. argon2 (ADR 0002) makes each
  guess expensive, but slowing an attacker is not the same as stopping one, and
  the per-guess cost is paid by our CPU, not theirs.

The edge was considered first and rejected: the deployed proxy is the stock
`caddy:2` image (v2.11.4) shared with Nextcloud, the brain services and docs.
`caddy list-modules` confirms no rate-limiting module — the `rate_limit`
directive comes from the third-party `caddy-ratelimit` plugin and would require
replacing the image that fronts every other service on the host.

## Decision

Throttling lives **in the application**, keyed on two independent dimensions,
either of which can refuse an attempt:

- **username** — sliding window of `MALUS_LOGIN_MAX_ATTEMPTS` (default 5)
  failures per `MALUS_LOGIN_WINDOW_SECONDS` (default 900). Stops password
  guessing against a named account regardless of how many source addresses the
  attacker rotates through.
- **client IP** — the same window with `MALUS_LOGIN_IP_MAX_ATTEMPTS`
  (default 20). Stops password spraying, where one password is tried against
  many usernames and no single username ever trips its own counter.

Refusal happens **before** the password is verified, so a throttled attacker
never reaches argon2 and the attack stops costing us CPU. A successful
authentication clears that username's counter — a user who mistypes and then
succeeds is never left locked out. The IP counter is deliberately *not*
cleared by a success, so one valid account cannot launder an ongoing spray from
the same address.

The implementation is `src/malus/auth/throttle.py`, **stdlib only**: ADR 0002
keeps the core runtime dependency-clean, and a sliding-window counter does not
justify a new runtime dependency. State is held per app instance on
`app.state.login_throttle`, which keeps tests isolated from one another.

The guard is applied at the three HTTP entry points rather than inside
`authenticate()`, because only there is the request — and therefore the client
address — available. `authenticate()` stays a pure service function usable from
the CLI.

Client identity comes from the **last** `X-Forwarded-For` hop, which is the
address Caddy itself accepted; earlier entries are client-supplied and forged
by any attacker who wants a fresh identity per request. This is sound only
while nothing but the proxy can reach the app — it is a second reason the
loopback bind in `docker-compose.yml` must not be widened.

## Consequences

- A locked-out user waits out the window; there is no admin unlock and no
  email-based recovery. With the default 5/15 min this is a minor inconvenience
  against a real attack, but an admin who locks themselves out and has no
  second admin account must wait, or restart the container.
- **State is in-process and does not survive a restart**, and it is not shared
  between replicas. This is correct for the deployed topology —
  `docker-entrypoint.sh` runs a single uvicorn process with no `--workers` — but
  running multiple workers or replicas would silently multiply the effective
  limits by the process count and needs a shared store (Redis, or a DB table)
  before that happens.
- Throttling is per entry point by construction, so a **future** credential
  surface must call `throttle.check`/`throttle.record` explicitly; unlike the
  router-wide `Depends(get_current_user)`, it does not come for free.
  `tests/api/test_login_throttle.py` covers all three current surfaces.
- This is anti-automation, not a replacement for password quality: the
  bootstrap admin credentials (`MALUS_ADMIN_USER`/`MALUS_ADMIN_PASSWORD`) still
  need to be strong.

## Sources

- Host security review, 2026-08-12: `ufw status verbose` (default deny incoming;
  only 22/tcp, 80/tcp, 443/tcp allowed), `ss -tlnp`, `docker ps`,
  `docker exec caddy caddy list-modules`, `/opt/alum/caddy/Caddyfile:73-75`.
- OWASP ASVS v4 §2.2.1 (anti-automation controls on authentication) and the
  OWASP Authentication Cheat Sheet, which recommend rate limiting plus
  per-account throttling over hard permanent lockout.
- ADR 0002 (stack, argon2, dependency-clean core).
