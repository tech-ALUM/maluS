# maluS — Operations Runbook (v1)

Self-hosted deployment on the company server: Docker Compose, HTTPS via a
reverse proxy, SQLite (WAL) by default, Postgres optional.

## Deploy (fresh host)

1. Install Docker + Docker Compose. TLS is handled by the bundled `caddy`
   service — no separate proxy to install.
2. Clone the repo; `cp .env.example .env` and fill in:
   - `MALUS_SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `MALUS_ADMIN_USER` / `MALUS_ADMIN_PASSWORD` — the first-run admin (temporary).
   - `MALUS_DOMAIN` — the public hostname (e.g. `malus.tuodominio.it`).
3. Point the domain's DNS **A** record at this host; open ports **80** and **443**.
4. `docker compose up -d --build`
   - `app` migrates (`alembic upgrade head`) and serves on loopback; `caddy`
     terminates HTTPS on 80/443 and proxies to `app:8000`, auto-provisioning the
     certificate for `MALUS_DOMAIN`.
   - First run bootstraps the admin (forced password change).
5. Verify: `curl -fsS https://$MALUS_DOMAIN/health` → `{"status":"ok",...}`. Log in
   at `https://$MALUS_DOMAIN/ui/login` and change the admin password immediately.

*(Alternative: run Caddy natively on the host instead of the compose service —
use `deploy/Caddyfile` (`reverse_proxy 127.0.0.1:8000`) and drop the `caddy`
service.)*

## Upgrade

```sh
git pull
docker compose up -d --build      # entrypoint re-runs `alembic upgrade head`
```

Roll back by checking out the previous tag and re-running; restore a DB backup
first if a migration is not backward-compatible.

## Schema authority

`alembic upgrade head` is the **only** thing that changes the schema of a
deployed database. The entrypoint (`docker-entrypoint.sh`) runs it before the
server starts and `set -e` aborts the boot if it fails; `malus serve` itself
creates nothing and exits 2 with an actionable message if the database has no
schema.

- Where are we? `docker compose exec app alembic current`
- What is pending? `docker compose exec app alembic history --indicate-current`
- Fresh local database (development only): `malus init-db --db sqlite:///malus.db`
  — creates and stamps at head in one call.

Rules for anyone writing a revision:

1. **Idempotent.** Inspect before you create (`sa.inspect(op.get_bind())`);
   SQLite DDL is non-transactional, so a half-applied revision leaves objects
   behind and the retry must survive them.
2. **Never edit an applied revision.** Add a new one on top.
3. **Data migrations are revisions too**, written as set-based SQLAlchemy Core
   statements (portable across SQLite and Postgres), never through the ORM —
   the models will move on and the revision must not.
4. **Never `alembic stamp` a populated database** to escape a failed upgrade:
   it skips every pending migration and recreates the drift that took the
   service down on 2026-07-30. Restore a backup and fix the revision.

**Recovering a database that is unstamped but populated** (a pre-v3.1 volume):
compare its objects with the revision that should have created them, `alembic
stamp <that revision>`, then `alembic upgrade head`. Take a backup first
(§Backup & restore).

## Backup & restore

```sh
# Backup (host, app stopped or SQLite .backup is consistent live):
docker compose exec app sh -c 'MALUS_DB_URL="$MALUS_DB_URL" /app/scripts/backup.sh /data/backups'
# or from the host against the mounted volume.

# Restore (STOP the app first):
docker compose stop app
MALUS_DB_URL=... scripts/restore.sh backups/malus-YYYYmmdd-HHMMSS.db
docker compose start app
```

Schedule `scripts/backup.sh` via cron; keep off-host copies.

## Rotate secrets

- **Session key** (`MALUS_SECRET_KEY`): set a new value in `.env` and
  `docker compose up -d` — existing sessions are invalidated (users re-login).
- **Admin/user passwords**: change via the GUI (`/auth/change-password`) or an
  admin resets by creating/updating the user.

## Login throttling

Failed credential checks are rate-limited in the app (ADR 0005) — the edge
Caddy adds no authentication, so this is the only brake on password guessing.
It covers `/auth/login`, `/ui/login` and HTTP Basic. Defaults, overridable in
`.env` (a restart applies them; counters are in-process and reset on restart):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MALUS_LOGIN_MAX_ATTEMPTS` | `5` | Failures per username per window |
| `MALUS_LOGIN_IP_MAX_ATTEMPTS` | `20` | Failures per client IP per window |
| `MALUS_LOGIN_WINDOW_SECONDS` | `900` | Sliding window, in seconds |

A blocked attempt returns **429** with `Retry-After`; the GUI renders the login
page with an explanation. A successful login clears that username's counter, so
a mistyped password never leaves a legitimate user locked out.

**Locked out with no second admin?** Wait out the window, or
`docker compose restart app` — the counters live in memory.

> Do **not** run the app with `--workers` or multiple replicas without moving
> this state to a shared store: each process keeps its own counters, which
> multiplies the effective limit by the process count (ADR 0005 §Consequences).

## Switch to Postgres

1. In `.env`: `MALUS_DB_URL=postgresql+psycopg://malus:PASS@db:5432/malus` and set
   `POSTGRES_*`.
2. Build the image with the Postgres driver: add `[postgres]` to the install in
   the `Dockerfile` (`pip install ".[mcp,postgres]"`).
3. `docker compose --profile postgres up -d --build`. Same ORM; the entrypoint
   migrates the Postgres schema.

## Health & logs

- Liveness: `GET /health` (used by the container `HEALTHCHECK`).
- Logs: structured JSON lines on stdout — `docker compose logs -f app`.

## AI reviewer

Default is the free interactive path (see `docs/usage/ai-reviewer.md`); no key.
The paid server-side engine is off unless `MALUS_AI_ENGINE=anthropic`.
