# v3.1 Step 5 — One schema authority: Alembic

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [x]`) syntax for tracking.

**Status:** added on **2026-07-30**, after the production incident of the same
day. `docs/plan/v3.1/00-design.md` §Steps lists steps 1–4 only (it is a UX
feedback wave and records *"Migration | None"*); this step is an **addition to
that design**, agreed with Alberto Boffi after the outage, and is the only v3.1
step that touches the database boot path. It carries no UX change.

**Goal:** `alembic upgrade head` becomes the **single** authority over the
production schema. The serving path (`malus serve` → `create_app`) stops
mutating the schema behind Alembic's back, the two hand-rolled backfills move
into revisions, and any path that still creates a schema stamps it at head so a
database is never left unstamped. After this step the failure mode of
2026-07-30 cannot recur, and it is caught by tests one commit after it is
introduced instead of one deploy later.

## The incident this step exists for

maluS keeps two schema authorities that do not talk to each other:

| Authority | Entry point | What it does |
|---|---|---|
| Alembic | `docker-entrypoint.sh` → `alembic upgrade head`, before the server starts | full DDL chain, writes `alembic_version` |
| `create_all` | `src/malus/api/app.py:84` (every `malus serve`) and `src/malus/cli.py:57` (`malus import`) | `SQLModel.metadata.create_all` (missing **tables** only, never columns) + `migrate_reviewer_copy_columns` + `migrate_review_phases`; **never touches `alembic_version`** |

The model `ReviewArtifact` landed in `964362f`; the revision creating the same
table (`b9e4d5f6a701`) landed two commits later in `3ea2a56`. The server booted
in that window, so `create_all` created `review_artifacts` while
`alembic_version` still read `a7c31e90d412`. Every later `alembic upgrade head`
then died on `sqlite3.OperationalError: table review_artifacts already exists`,
and `set -e` in the entrypoint kept the container down.

`a5a0125` stopped the bleeding — `b9e4d5f6a701` now inspects before creating,
and `tests/db/test_db_migration.py::test_upgrade_head_after_create_all_already_ran`
pins that behaviour. It did **not** remove the second authority. This step does.

## Investigation — established facts

Everything below was read out of the tree at `2df818c` + `a5a0125`, or measured.
Do not re-derive; do not contradict without re-measuring.

### F1 — every `create_all` call site

| # | Call site | Reached by | What breaks if `create_all` stops running there |
|---|---|---|---|
| 1 | `src/malus/api/app.py:84` (`create_app`, `create_schema: bool = True`) | `malus serve` (`src/malus/cli.py:78`) → the container entrypoint; and the `app` fixture of `tests/api`, `tests/web`, `tests/e2e`, `tests/mcp` | **Production: nothing.** The entrypoint already ran `alembic upgrade head`, so every table exists and `create_all` is a no-op. **Local dev: `malus serve --db sqlite:///new.db` on a non-existent file** would reach `_bootstrap_admin` (`app.py:115`) with no `users` table → `OperationalError`. **Tests: 218 test functions** build their app through this fixture. |
| 2 | `src/malus/cli.py:57` (`import_cmd`) | `malus import <dir> --db …` | `malus import` against a new SQLite file fails; `tests/test_cli.py::test_import_seeds_the_database` (1 test) fails. |
| 3 | `tests/db/conftest.py:15` (`engine` fixture) | 48 of the 52 test functions in `tests/db` | schema-less in-memory engine → every DB test errors. |
| 4 | `tests/services/conftest.py:17` (`engine` fixture) | 39 of the 43 test functions in `tests/services` | same. |
| 5 | `tests/test_pdfgen.py:43` | `test_generate_pdf_bytes` (1 test, skipped without `malus[pdf]`) | same. |
| 6 | `tests/db/test_db_mapping.py:188` (inline `create_all(engine2)`) | `test_import_is_idempotent_across_databases` (already inside the 48) | same. |
| 7 | `tests/db/test_db_migration.py:48` | `test_upgrade_head_after_create_all_already_ran` (1 test) | **deliberate** — it reproduces the incident state and must keep calling `create_all` raw and unstamped. |

`create_schema` appears nowhere except its definition and use in
`src/malus/api/app.py` (`grep -rn "create_schema"`): no test passes it, so all
218 web/api/e2e/mcp tests rely on the default `True`.

### F2 — how many tests are affected, exactly

`grep -rE "^\s*(async )?def test_" tests --include='*.py' | wc -l` → **458**
test functions in the suite.

- **218 indirect**, through `create_app`'s default: `tests/api` 28/28,
  `tests/web` 178/179, `tests/e2e` 2/2, `tests/mcp` 10/11 take an
  app-derived fixture (`app`/`client`/`login`/`admin`/`mkuser`/`basic_client`).
- **89 direct**: 48 (`tests/db`) + 39 (`tests/services`) via the `engine`/
  `session` fixtures, + `tests/test_pdfgen.py::test_generate_pdf_bytes`,
  + `tests/db/test_db_migration.py::test_upgrade_head_after_create_all_already_ran`.

**307 of 458** test functions reach `create_all`. The choke points are **six
files**: four `conftest.py` (`api`, `web`, `e2e`, `mcp`) and two fixture
`conftest.py` (`db`, `services`) — the latter two need no change at all,
because `create_all` survives as the **test** schema helper.

### F3 — a fresh deployment does not need `create_all`

Measured, not assumed. On a fresh SQLite file, `alembic upgrade head` produces a
schema **identical** to `SQLModel.metadata.create_all` — 11 tables, no column,
index or unique-constraint difference; `alembic.autogenerate.compare_metadata`
against the head-migrated database returns **0 diffs**. The container entrypoint
runs `alembic upgrade head` **before** `exec malus serve`, and `set -e` aborts
the boot if it fails, so the server never starts against an unmigrated volume.
A fresh deployment is therefore complete and usable with Alembic alone.

### F4 — `migrate_review_phases` is idempotent, and a data migration

It promotes `reviews.status in ('draft','active')` to `'in_review'` when the
review has a frozen baseline (`tests/db/test_migration_v3.py::test_backfill_is_idempotent`
pins this). Re-running it on a database where it already ran finds nothing:
`draft`+baseline is not a reachable steady state in v3 — `freeze_baseline`
(`src/malus/services/core.py:158`) sets `IN_REVIEW` in the same call, and no
service ever writes `draft` back (`grep -rn "set_status(" src/malus/` →
`session.py:57`, `core.py:158/882/893/948`: only `in_review`, `closeout`,
`finalized`). It has **no Alembic revision** — it is pure DML that today runs on
every single process start, which is both wasteful and, being outside the
version chain, invisible to `alembic current`.

`migrate_reviewer_copy_columns` is a different case: it adds
`reviewer_copies.reopen_requested_at`, which is exactly what `b9e4d5f6a701`
already does (idempotently, since `a5a0125`). It is pure duplication.

### F5 — SQLite and Postgres both tolerate the plan

- The backfill is written with SQLAlchemy Core constructs, not literal SQL.
  Verified compilation on both dialects:
  SQLite → `… WHERE document_versions.is_baseline IS 1`,
  PostgreSQL → `… WHERE document_versions.is_baseline IS true`.
  `UPDATE … WHERE id IN (SELECT …)` is supported by both.
- `sa.inspect(op.get_bind())` guards (the `a5a0125` idiom) are dialect-agnostic.
- `render_as_batch=True` in `alembic/env.py` is a SQLite-only affordance and
  inert on Postgres.
- Stamping writes the dialect-agnostic `alembic_version` table.
- Postgres runs DDL transactionally; SQLite does **not**
  (`alembic.runtime.migration: Will assume non-transactional DDL`), so a
  half-applied revision can leave objects behind on SQLite — a second reason
  every revision must be idempotent.
- CI has no Postgres (`psycopg` is the optional `postgres` extra,
  `pyproject.toml`; `docker-compose.yml` ships it behind `--profile postgres`).
  Postgres coverage in this step is therefore **by construction** plus a
  compile-only assertion using `sqlalchemy.dialects.postgresql.dialect()`,
  which needs no driver.

### F6 — a latent hazard in the current Alembic wiring

`alembic/env.py:28` resolves the URL as `MALUS_DB_URL` **first**, config second.
Any programmatic Alembic call (including the ones this step adds, and the
existing `tests/db/test_db_migration.py`) would silently be redirected to a
developer's exported `MALUS_DB_URL` instead of the intended database. Task 1
closes this by letting the caller inject a live connection.

## Decision (approved by Alberto Boffi, 2026-07-30 — do not redesign)

1. **Alembic is the single schema authority in production.** The serving path
   creates nothing. `create_app` loses its `create_schema` parameter entirely
   (it is used by no test — F1) rather than defaulting it to `False`, so a
   future entry point cannot re-enable the drift by passing `True`.
2. **`create_all` is confined to tests**, plus one wrapper for an explicit
   developer bootstrap. The wrapper is genuinely needed: without it,
   `malus serve --db sqlite:///malus.db` on a fresh checkout has no way to get
   a schema short of running Alembic by hand, and `malus import` (whose test
   creates a brand-new file, F1 #2) breaks. The wrapper is
   `bootstrap_schema()` — create **and stamp** — exposed as the new command
   **`malus init-db`**, and used by `malus import`.
3. **Both backfills move into Alembic.** `migrate_reviewer_copy_columns` is
   **deleted** (duplicate of `b9e4d5f6a701`). `migrate_review_phases` becomes a
   **new revision** `c4d5e6f7a8b9`, *not* an edit to `b9e4d5f6a701` — because
   `b9e4d5f6a701` is **already applied in production** (the `a5a0125` deploy),
   so a backfill folded into it would never run there; and because a released
   revision is never mutated. Then it is deleted from `session.py`.
4. **Belt and braces.** `bootstrap_schema` stamps head the instant it creates a
   schema, and only on a genuinely **empty** database — a populated but
   unstamped database is an operator decision, never an automatic one (stamping
   it head would skip every pending migration). Revision idempotency becomes a
   **written repo convention** in `CLAUDE.md` §Conventions and
   `docs/ops/runbook.md` §Schema authority, enforced by a lint test.
5. **`serve` fails fast** on an unmigrated database with an actionable message,
   instead of half-working.

## Architecture

```
docker-entrypoint.sh ── alembic upgrade head ──▶ [ the schema ]      (production)
malus init-db ────────── bootstrap_schema ──────▶ create_all + stamp head
                                                   (empty databases only)
tests/*/conftest.py ──── create_all ────────────▶ tables only, unstamped
malus serve / create_app ──────────────────────▶ (nothing — read-only)
```

New module `src/malus/db/migrations.py`: a thin, dependency-free wrapper around
the Alembic API (`alembic` is already a hard runtime dependency —
`pyproject.toml`) exposing `alembic_config`, `current_revision`, `stamp_head`,
`upgrade_head`, all driven against an **injected connection** so no environment
variable can redirect them. `alembic.ini` + `alembic/` live at the repo /image
root, not inside the wheel, so resolution is `MALUS_ALEMBIC_INI` → repo root
derived from `malus.__file__` → `Path.cwd()` (WORKDIR is `/app` in the image,
which holds both).

**Tech stack:** Python 3.12, SQLModel/SQLAlchemy 2, Alembic, Typer, pytest.
Depends on `a5a0125`. Independent of v3.1 steps 01–04 — it touches no template,
no route, no service.

## Global constraints

- Python 3.12+. **No new runtime dependency** (CLAUDE.md §Conventions):
  `alembic`, `sqlmodel`, `typer` are already declared in `pyproject.toml`.
- **SQLite and Postgres both supported** (ADR 0002). No literal SQL that binds
  to one dialect; booleans through SQLAlchemy Core (F5).
- **No data loss under any path.** No revision drops or rewrites a row; the
  data migration only promotes `draft`/`active` → `in_review`; downgrades of
  the data revision are explicit no-ops.
- **Every task leaves the app bootable.** This step edits the boot path of a
  running production service: after each task, `docker compose up` must still
  reach `/health` 200. Task order is chosen so that no intermediate commit can
  produce an unstamped database.
- `python -m pytest -q` **green at the end of every task** — no test deleted or
  weakened; `test_upgrade_head_after_create_all_already_ran` (the `a5a0125`
  regression pin) must survive verbatim.
- Conventional Commits, one commit per task.

## Deliverables

- [x] `alembic/env.py` honours an injected `config.attributes["connection"]`
      and stops reconfiguring logging on programmatic calls
- [x] `src/malus/db/migrations.py`: `alembic_config` / `current_revision` /
      `stamp_head` / `upgrade_head`
- [x] Revision `c4d5e6f7a8b9` — the v3 `draft|active → in_review` data backfill
- [x] `migrate_review_phases` and `migrate_reviewer_copy_columns` deleted from
      `src/malus/db/session.py`; `create_all` is schema-only
- [x] `bootstrap_schema` (create **+ stamp**, empty databases only) and the
      `malus init-db` command; `malus import` uses it
- [x] `create_app` loses `create_schema` — the serving path creates nothing;
      `malus serve` refuses an unmigrated database with exit code 2
- [x] Column-level models↔migrations parity guard (`compare_metadata`) — the
      test that would have caught `964362f`
- [x] Fresh-empty-database and pre-existing-drifted-database boots, both
      through `alembic upgrade head` only, as pytest tests
- [x] Revision-idempotency convention written in `CLAUDE.md` +
      `docs/ops/runbook.md`, enforced by a lint test
- [x] `docs/spec/data-model.md` §Migration/backfill and §5 updated
- [x] Full suite green

---

### Task 1: Alembic drivable from Python, against a given connection

**Files:**
- Modify: `alembic/env.py`
- Create: `src/malus/db/migrations.py`
- Modify: `src/malus/db/__init__.py`
- Test: `tests/db/test_schema_authority.py` (new)

**Interfaces produced:**

```python
# src/malus/db/migrations.py
def alembic_ini() -> Path                      # raises AlembicNotFound
def alembic_config() -> Config
def current_revision(engine: Engine) -> str | None
def stamp_head(engine: Engine) -> None
def upgrade_head(engine: Engine) -> None
```

- [x] **Step 1: failing test** — `tests/db/test_schema_authority.py`:

```python
"""Alembic is the single schema authority (v3.1 step 05).

These tests pin the boot contract that the 2026-07-30 incident broke: the
serving path never creates schema, anything that does create schema stamps it,
and a database is reachable from `alembic upgrade head` alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import malus.db.models  # noqa: F401  populate SQLModel.metadata
from malus.db.migrations import alembic_ini, current_revision, stamp_head, upgrade_head

ROOT = Path(__file__).resolve().parents[2]


def test_alembic_ini_is_discoverable_from_the_package():
    assert alembic_ini() == ROOT / "alembic.ini"


def test_stamp_head_marks_an_unstamped_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'plain.db'}"
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    assert current_revision(engine) is None

    stamp_head(engine)

    assert current_revision(engine) == "b9e4d5f6a701"  # head at task 1


def test_injected_connection_wins_over_MALUS_DB_URL(tmp_path, monkeypatch):
    """env.py reads MALUS_DB_URL first (alembic/env.py:28). A programmatic
    upgrade must go to the engine it was handed, never to whatever the
    environment happens to point at — otherwise a developer with MALUS_DB_URL
    exported migrates the wrong database."""
    decoy = tmp_path / "decoy.db"
    target = tmp_path / "target.db"
    monkeypatch.setenv("MALUS_DB_URL", f"sqlite:///{decoy}")

    upgrade_head(create_engine(f"sqlite:///{target}"))

    assert "users" in inspect(create_engine(f"sqlite:///{target}")).get_table_names()
    assert not decoy.exists()
```

- [x] **Step 2:** `python -m pytest -q tests/db/test_schema_authority.py`
      → FAIL (`ModuleNotFoundError: No module named 'malus.db.migrations'`).
- [x] **Step 3: implement.** `alembic/env.py` — replace the logging block and
      `run_migrations_online`:

```python
# an injected connection (malus.db.migrations) must not have the caller's
# logging configuration torn down and rebuilt under it
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)
```

```python
def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against an injected connection when the caller supplies
    one through ``config.attributes["connection"]`` (``malus.db.migrations``),
    otherwise build an engine from the URL. The injected connection wins over
    every URL source: a stray ``MALUS_DB_URL`` in the environment must never
    redirect a programmatic upgrade or stamp to another database."""
    injected = config.attributes.get("connection")
    if injected is not None:
        _run(injected)
        return
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _run(connection)
```

  `src/malus/db/migrations.py` (new):

```python
"""Programmatic access to Alembic — the single schema authority (v3.1 step 05).

maluS used to keep two authorities: Alembic, and ``create_all`` running on
every ``malus serve``. On 2026-07-30 that drift took the server down (a table
created by ``create_all`` with ``alembic_version`` left behind, so the next
``alembic upgrade head`` collided with it). Alembic now owns the production
schema alone, and everything that still creates a schema — only the developer
bootstrap — stamps it here, immediately.

The Alembic scripts ship next to the repo / image root, not inside the wheel
(``Dockerfile`` copies ``alembic.ini`` and ``alembic/`` into ``/app``, which is
also WORKDIR), so they are resolved in this order:
``MALUS_ALEMBIC_INI`` → the repo root derived from ``malus.__file__`` →
``Path.cwd()``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Engine

import malus


class AlembicNotFound(RuntimeError):
    """The Alembic scripts are not reachable from this installation."""


def _candidates() -> list[Path]:
    env = os.environ.get("MALUS_ALEMBIC_INI")
    found = [Path(env)] if env else []
    found.append(Path(malus.__file__).resolve().parents[2] / "alembic.ini")
    found.append(Path.cwd() / "alembic.ini")
    return found


def alembic_ini() -> Path:
    """The ``alembic.ini`` whose sibling ``alembic/versions`` actually exists."""
    for candidate in _candidates():
        if candidate.is_file() and (candidate.parent / "alembic" / "versions").is_dir():
            return candidate
    raise AlembicNotFound(
        "alembic.ini not found (looked in: "
        + ", ".join(str(c) for c in _candidates())
        + ") — set MALUS_ALEMBIC_INI"
    )


def alembic_config() -> Config:
    ini = alembic_ini()
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    cfg.attributes["configure_logger"] = False
    return cfg
    # NB: sqlalchemy.url is deliberately left alone — every call below injects a
    # live connection, so no credential is ever copied into the Config object.


def current_revision(engine: Engine) -> Optional[str]:
    """The revision this database is stamped at, or ``None`` if unstamped."""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _with_connection(engine: Engine, run: Callable[[Config], None]) -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        run(cfg)


def stamp_head(engine: Engine) -> None:
    """Write ``alembic_version`` = head without running any migration."""
    _with_connection(engine, lambda cfg: command.stamp(cfg, "head"))


def upgrade_head(engine: Engine) -> None:
    """``alembic upgrade head`` against this engine (tests, tooling)."""
    _with_connection(engine, lambda cfg: command.upgrade(cfg, "head"))
```

  `src/malus/db/__init__.py` — extend the import and `__all__`:

```python
from malus.db.migrations import current_revision, stamp_head, upgrade_head
```

  (append `"current_revision"`, `"stamp_head"`, `"upgrade_head"` to `__all__`).

- [x] **Step 4:** `python -m pytest -q tests/db/test_schema_authority.py` → PASS,
      then `python -m pytest -q` → PASS (458 tests, exit 0).
- [x] **Step 5:** `git commit -m "feat(db): drive Alembic programmatically against an injected connection"`

### Task 2: the v3 phase backfill becomes an Alembic revision

**Files:**
- Create: `alembic/versions/c4d5e6f7a8b9_v3_phase_backfill.py`
- Rewrite: `tests/db/test_migration_v3.py`

`b9e4d5f6a701` is already applied on the production database (the `a5a0125`
deploy), so the backfill **must** be a new revision on top of it — folded into
`b9e4d5f6a701` it would never run there. `down_revision = 'b9e4d5f6a701'`; head
becomes `c4d5e6f7a8b9`.

The Python function `migrate_review_phases` stays in place for this task (it is
idempotent, so running both is harmless) and is deleted in task 3 — that
ordering keeps every intermediate commit bootable.

- [x] **Step 1: failing test** — replace `tests/db/test_migration_v3.py`
      entirely. The old file drove `migrate_review_phases` through the ORM;
      the backfill is now DML inside a revision, so the test drives Alembic:

```python
"""The v3 phase backfill is an Alembic revision (v3.1 step 05).

Pre-v3 rows sit at ``draft`` (no phase column existed) or at the removed v2
value ``active``. Revision ``c4d5e6f7a8b9`` promotes those that already have a
frozen baseline to ``in_review``, once, inside the version chain — it used to
be ``migrate_review_phases`` running on every process start, outside Alembic's
knowledge (the 2026-07-30 drift).

Rows are seeded with literal SQL at the *previous* revision, never through the
ORM: a data migration must keep working when the models move on. SQLite only —
booleans as 0/1 (see the plan, F5, for the Postgres story).
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS = "b9e4d5f6a701"
BACKFILL = "c4d5e6f7a8b9"


def _config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


def _seed(conn, n: int, *, review_id: str, status: str, baseline: bool) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO users (id, username, display_name, is_active, created,"
            " is_admin, is_ai, must_change_password)"
            " VALUES (:id, :u, :u, 1, '2026-01-01 00:00:00', 0, 0, 0)"
        ),
        {"id": n, "u": f"user{n}"},
    )
    conn.execute(
        sa.text(
            "INSERT INTO reviews (id, review_id_str, owner_id, status, created)"
            " VALUES (:id, :rid, :id, :st, '2026-01-01')"
        ),
        {"id": n, "rid": review_id, "st": status},
    )
    conn.execute(
        sa.text("INSERT INTO documents (id, review_id, name) VALUES (:id, :id, 'd.md')"),
        {"id": n},
    )
    if baseline:
        conn.execute(
            sa.text(
                "INSERT INTO document_versions (id, document_id, ordinal, content,"
                " content_hash, is_baseline, is_final, created)"
                " VALUES (:id, :id, 1, '# doc', 'h', 1, 0, '2026-01-01 00:00:00')"
            ),
            {"id": n},
        )


def _statuses(engine) -> dict[str, str]:
    with engine.connect() as conn:
        return dict(conn.execute(sa.text("SELECT review_id_str, status FROM reviews")).all())


def _drifted_db(tmp_path, monkeypatch):
    """A pre-v3 database at the revision before the backfill, seeded with one
    row of every shape the backfill has an opinion about."""
    monkeypatch.delenv("MALUS_DB_URL", raising=False)  # alembic/env.py:28 reads it first
    url = f"sqlite:///{tmp_path / 'prev3.db'}"
    cfg = _config(url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed(conn, 1, review_id="R-DRAFT-FROZEN", status="draft", baseline=True)
        _seed(conn, 2, review_id="R-ACTIVE-FROZEN", status="active", baseline=True)
        _seed(conn, 3, review_id="R-DRAFT-BARE", status="draft", baseline=False)
        _seed(conn, 4, review_id="R-CLOSEOUT", status="closeout", baseline=True)
        _seed(conn, 5, review_id="R-FINALIZED", status="finalized", baseline=True)
    return cfg, engine


def test_backfill_promotes_only_frozen_draft_and_active(tmp_path, monkeypatch):
    cfg, engine = _drifted_db(tmp_path, monkeypatch)

    command.upgrade(cfg, "head")

    assert _statuses(engine) == {
        "R-DRAFT-FROZEN": "in_review",
        "R-ACTIVE-FROZEN": "in_review",
        "R-DRAFT-BARE": "draft",        # no baseline — nothing to promote
        "R-CLOSEOUT": "closeout",       # never touched
        "R-FINALIZED": "finalized",     # never touched
    }


def test_backfill_is_idempotent(tmp_path, monkeypatch):
    """Re-running the statement changes nothing. ``downgrade`` of a data
    revision is a no-op, so downgrade+upgrade re-executes the UPDATE — the
    strongest available idempotency proof."""
    cfg, engine = _drifted_db(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    before = _statuses(engine)

    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")

    assert _statuses(engine) == before


def test_backfill_loses_no_row(tmp_path, monkeypatch):
    cfg, engine = _drifted_db(tmp_path, monkeypatch)

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM reviews")).scalar() == 5
        assert conn.execute(sa.text("SELECT count(*) FROM document_versions")).scalar() == 4


def test_backfill_statement_compiles_on_sqlite_and_postgres(tmp_path, monkeypatch):
    """No Postgres in CI (psycopg is the optional `postgres` extra), so the
    portability claim is pinned by compiling the statement under both dialects
    — booleans are the trap: `IS 1` on SQLite, `IS true` on Postgres."""
    monkeypatch.delenv("MALUS_DB_URL", raising=False)
    cfg = _config(f"sqlite:///{tmp_path / 'unused.db'}")
    module = ScriptDirectory.from_config(cfg).get_revision(BACKFILL).module

    for dialect, expected in ((sqlite.dialect(), "IS 1"), (postgresql.dialect(), "IS true")):
        sql = str(module.backfill_statement().compile(
            dialect=dialect, compile_kwargs={"literal_binds": True}
        ))
        assert sql.startswith("UPDATE reviews SET status='in_review'")
        assert expected in sql
```

- [x] **Step 2:** `python -m pytest -q tests/db/test_migration_v3.py` → FAIL
      (`KeyError: 'c4d5e6f7a8b9'` / no such revision).
- [x] **Step 3: implement** `alembic/versions/c4d5e6f7a8b9_v3_phase_backfill.py`:

```python
"""v3 phase backfill: draft|active -> in_review for frozen reviews

Revision ID: c4d5e6f7a8b9
Revises: b9e4d5f6a701
Create Date: 2026-07-30 16:00:00.000000

This is the DATA half of the v3 lifecycle migration. It used to live in Python
as ``malus.db.session.migrate_review_phases``, re-run on every process start
and invisible to Alembic — one of the two schema authorities whose drift took
the server down on 2026-07-30 (v3.1 ``docs/plan/v3.1/05-one-schema-authority.md``).

It is a separate revision rather than an edit to ``b9e4d5f6a701`` because that
revision is already applied in production: a backfill folded into it would
never run there.

Built from SQLAlchemy Core constructs, not literal SQL, so the boolean test
renders correctly on both supported dialects (``IS 1`` on SQLite, ``IS true``
on PostgreSQL). It only ever promotes a status — no row is deleted, no column
is dropped, nothing is rewritten.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b9e4d5f6a701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def backfill_statement() -> sa.sql.Update:
    """The backfill as a Core statement (also compiled by the tests, which
    assert it is portable across SQLite and PostgreSQL).

    Pre-v3 rows are stuck at ``draft`` (there was no phase column) or at the
    removed v2 value ``active``. A review whose baseline is already frozen
    belongs at ``in_review``; one without a baseline is a genuine draft and is
    left alone; ``closeout``/``finalized`` are never touched.
    """
    reviews = sa.table(
        "reviews", sa.column("id", sa.Integer), sa.column("status", sa.String)
    )
    documents = sa.table(
        "documents", sa.column("id", sa.Integer), sa.column("review_id", sa.Integer)
    )
    versions = sa.table(
        "document_versions",
        sa.column("document_id", sa.Integer),
        sa.column("is_baseline", sa.Boolean),
    )
    frozen = (
        sa.select(documents.c.review_id)
        .select_from(documents.join(versions, versions.c.document_id == documents.c.id))
        .where(versions.c.is_baseline.is_(True))
    )
    return (
        reviews.update()
        .where(reviews.c.status.in_(("draft", "active")))
        .where(reviews.c.id.in_(frozen))
        .values(status="in_review")
    )


def upgrade() -> None:
    """Promote frozen pre-v3 reviews to ``in_review``. Idempotent: a second run
    matches nothing, because ``freeze_baseline`` is the only writer of
    ``in_review`` and no service ever writes ``draft`` back."""
    op.execute(backfill_statement())


def downgrade() -> None:
    """Deliberately a no-op. This revision carries no schema change, and the
    pre-migration status of a promoted review (``draft`` vs the removed v2
    ``active``) is not recoverable — inventing one would be data loss. Reviews
    stay at ``in_review``, which is a valid v3 phase."""
```

- [x] **Step 4:** `python -m pytest -q tests/db/test_migration_v3.py` → PASS
      (5 tests), then `python -m pytest -q` → PASS. Note that
      `tests/db/test_db_migration.py::test_migration_creates_full_schema` and
      `::test_migration_downgrades_to_base` still pass: the new revision adds
      no table and its downgrade is inert.
- [x] **Step 5:** `git commit -m "feat(db): v3 phase backfill becomes revision c4d5e6f7a8b9"`

### Task 3: `create_all` is schema-only; `bootstrap_schema` creates **and stamps**

**Files:**
- Modify: `src/malus/db/session.py`
- Modify: `src/malus/db/__init__.py`
- Modify: `src/malus/cli.py`
- Modify: `tests/db/test_schema_authority.py` (extend)
- Modify: `tests/test_cli.py` (extend)

`src/malus/api/app.py` is **not** touched in this task — it keeps calling
`create_all`, exactly as today, so the commit is bootable and the 218 web/api
tests keep running at full speed (no per-test stamping). Task 4 removes it.

- [x] **Step 1: failing tests** — append to `tests/db/test_schema_authority.py`:

```python
from malus.db import bootstrap_schema


def test_bootstrap_schema_creates_and_stamps_an_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")

    assert bootstrap_schema(engine) is True

    insp = inspect(engine)
    assert set(insp.get_table_names()) - {"alembic_version"} == set(SQLModel.metadata.tables)
    assert current_revision(engine) == "c4d5e6f7a8b9"  # never left unstamped


def test_bootstrap_schema_refuses_a_populated_database(tmp_path):
    """A database that already has tables belongs to Alembic. Stamping it head
    would skip every pending migration — the 2026-07-30 failure mode, inverted."""
    url = f"sqlite:///{tmp_path / 'existing.db'}"
    engine = create_engine(url)
    upgrade_head(engine)

    assert bootstrap_schema(engine) is False
    assert current_revision(engine) == "c4d5e6f7a8b9"


def test_bootstrap_schema_refuses_a_stamped_but_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'weird.db'}")
    stamp_head(engine)

    with pytest.raises(RuntimeError, match="stamped at"):
        bootstrap_schema(engine)


def test_create_all_does_not_stamp(tmp_path):
    """`create_all` stays the raw test helper: no stamp, no backfill. The
    a5a0125 regression test depends on being able to reproduce exactly that."""
    from malus.db import create_all

    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    create_all(engine)

    assert current_revision(engine) is None
```

  and to `tests/test_cli.py`:

```python
def test_init_db_creates_and_stamps(tmp_path):
    from sqlalchemy import create_engine

    from malus.db import current_revision

    db = tmp_path / "dev.db"
    result = runner.invoke(app, ["init-db", "--db", f"sqlite:///{db}"])

    assert result.exit_code == 0, result.stdout
    assert current_revision(create_engine(f"sqlite:///{db}")) is not None


def test_init_db_refuses_an_existing_database(tmp_path):
    db = tmp_path / "dev.db"
    assert runner.invoke(app, ["init-db", "--db", f"sqlite:///{db}"]).exit_code == 0

    result = runner.invoke(app, ["init-db", "--db", f"sqlite:///{db}"])

    assert result.exit_code == 1
    assert "alembic upgrade head" in result.stdout
```

- [x] **Step 2:** `python -m pytest -q tests/db/test_schema_authority.py tests/test_cli.py`
      → FAIL (`ImportError: cannot import name 'bootstrap_schema'`; `No such command 'init-db'`).
- [x] **Step 3: implement.** `src/malus/db/session.py` — delete
      `migrate_review_phases` and `migrate_reviewer_copy_columns` outright
      (revision `c4d5e6f7a8b9` owns the first, `b9e4d5f6a701` the second),
      drop the now-unused `select` import, and replace `create_all`:

```python
def create_all(engine: Engine) -> None:
    """Create every table declared on ``SQLModel.metadata``.

    **Tests only**, plus ``bootstrap_schema`` below. Production schema belongs
    to Alembic alone — ``docker-entrypoint.sh`` runs ``alembic upgrade head``
    before the server starts (v3.1 step 05). Deliberately schema-only: no
    backfill, no stamp. It creates missing *tables* and nothing else — never a
    column on an existing table — which is exactly why it must never be used to
    evolve a real database, and why an unstamped database it created collides
    with the next ``alembic upgrade head`` (the 2026-07-30 incident)."""
    from malus.db import models  # noqa: F401  register tables on the metadata

    SQLModel.metadata.create_all(engine)


def bootstrap_schema(engine: Engine) -> bool:
    """Create **and stamp** the schema of an *empty* database — the developer
    bootstrap (``malus init-db``, ``malus import``). Returns ``True`` when it
    created one, ``False`` when the database already has tables.

    Stamping happens in the same call, so a database created here is never left
    unstamped. Three cases, all deliberate:

    - tables present → return ``False`` and touch nothing: Alembic owns that
      database, and stamping it at head would skip every pending migration.
    - no tables but a revision recorded → refuse loudly: something dropped the
      schema out from under Alembic, and guessing would risk data.
    - empty → create, then stamp head.
    """
    from sqlalchemy import inspect

    from malus.db.migrations import current_revision, stamp_head

    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    if tables:
        return False
    revision = current_revision(engine)
    if revision is not None:
        raise RuntimeError(
            f"database is stamped at {revision} but has no tables — refusing to "
            "guess; run 'alembic upgrade head' or restore a backup"
        )
    create_all(engine)
    stamp_head(engine)
    return True
```

  `src/malus/db/__init__.py` — export `bootstrap_schema` (import + `__all__`).

  `src/malus/cli.py` — `import_cmd` uses the bootstrap, and the new command:

```python
from .db import DEFAULT_URL, bootstrap_schema, make_engine
```

```python
    engine = make_engine(db)
    bootstrap_schema(engine)  # creates + stamps only if the database is empty
    with Session(engine) as session:
```

```python
@app.command("init-db")
def init_db(
    db: str = typer.Option(DEFAULT_URL, "--db", help="Database URL (SQLModel/SQLAlchemy)."),
) -> None:
    """Create an empty development database and stamp it at Alembic head.

    Local development only. A deployment migrates with ``alembic upgrade head``
    — the single schema authority (v3.1 step 05); the container entrypoint runs
    it before the server starts.
    """
    if bootstrap_schema(make_engine(db)):
        typer.echo(f"created and stamped schema at head: {db}")
        return
    typer.echo(f"{db} already has tables — run 'alembic upgrade head' instead")
    raise typer.Exit(code=1)
```

- [x] **Step 4:** `python -m pytest -q` → PASS (462 tests: 458 − 5 rewritten in
      task 2 + 5 new there + 4 here + 2 CLI; the exact number is whatever the
      run reports, exit 0 is the gate). Confirm
      `tests/db/test_db_migration.py::test_upgrade_head_after_create_all_already_ran`
      still passes untouched — `create_all` is still raw and unstamped, so it
      still reproduces the incident.
- [x] **Step 5:** `git commit -m "refactor(db): create_all is schema-only, bootstrap_schema stamps head"`

### Task 4: the serving path stops creating schema

**Files:**
- Modify: `src/malus/api/app.py`
- Modify: `src/malus/cli.py`
- Modify: `tests/api/conftest.py`, `tests/web/conftest.py`,
  `tests/e2e/conftest.py`, `tests/mcp/conftest.py`
- Modify: `tests/db/test_schema_authority.py`, `tests/test_cli.py` (extend)

`create_schema` is **removed**, not defaulted to `False`: no test passes it
(F1), and a parameter that can re-enable the drift is the thing this step
exists to delete.

- [x] **Step 1: failing tests** — append to `tests/db/test_schema_authority.py`:

```python
def test_create_app_creates_no_schema(tmp_path):
    """The boot path is read-only with respect to the schema. In production the
    entrypoint has already run `alembic upgrade head`; anything create_app did
    on top of that could only be drift."""
    from malus.api import create_app

    engine = create_engine(f"sqlite:///{tmp_path / 'untouched.db'}")
    create_app(engine, https_only=False, session_secret="s", bootstrap_admin=None)

    assert inspect(engine).get_table_names() == []


def test_create_app_has_no_create_schema_switch():
    import inspect as pyinspect

    from malus.api import create_app

    assert "create_schema" not in pyinspect.signature(create_app).parameters
```

  and to `tests/test_cli.py`:

```python
def test_serve_refuses_a_database_without_schema(tmp_path):
    """Fail fast with an actionable message instead of half-booting: the
    serving path never creates a schema (v3.1 step 05)."""
    result = runner.invoke(app, ["serve", "--db", f"sqlite:///{tmp_path / 'empty.db'}"])

    assert result.exit_code == 2
    assert "alembic upgrade head" in result.output
    assert "malus init-db" in result.output
```

- [x] **Step 2:** `python -m pytest -q tests/db/test_schema_authority.py tests/test_cli.py`
      → FAIL (`create_schema` still in the signature; tables created; `serve` exits 0/starts).
- [x] **Step 3: implement.** `src/malus/api/app.py` — drop the parameter and the
      call (and the now-unused `create_all` from the `malus.db` import, keeping
      `DEFAULT_URL` and `make_engine`):

```python
def create_app(
    engine: Optional[Engine] = None,
    *,
    session_secret: Optional[str] = None,
    https_only: bool = True,
    bootstrap_admin: Optional[tuple[str, str]] = None,
) -> FastAPI:
    """Build the ASGI app. **Creates no schema**: Alembic is the single schema
    authority (v3.1 step 05) and ``docker-entrypoint.sh`` runs
    ``alembic upgrade head`` before the server starts. Tests create their own
    schema with ``malus.db.create_all``; developers use ``malus init-db``."""
```

  (delete lines 83–84, `if create_schema: create_all(...)`.)

  `src/malus/cli.py` — preflight in `serve`, before the app is built:

```python
def _require_schema(engine, db: str) -> None:
    """Refuse to serve a database that was never migrated. ``serve`` is
    read-only with respect to the schema (v3.1 step 05) — it must not silently
    invent one, which is how the two schema authorities drifted apart."""
    from sqlalchemy import inspect

    if "users" in inspect(engine).get_table_names():
        return
    typer.secho(
        f"error: no schema in {db}.\n"
        "  deployment: run 'alembic upgrade head' (the container entrypoint does this)\n"
        f"  local dev:  run 'malus init-db --db {db}'",
        err=True,
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=2)
```

```python
    configure_logging()
    engine = make_engine(db)
    _require_schema(engine, db)
    typer.echo(f"serving maluS API on http://{host}:{port} (db: {db})")
    uvicorn.run(create_app(engine), host=host, port=port)
```

  The four app conftests each grow one line — `tests/web/conftest.py`,
  identically for `tests/api`, `tests/e2e`, `tests/mcp`:

```python
from malus.db import create_all, make_engine


@pytest.fixture
def app():
    engine = make_engine("sqlite://")
    create_all(engine)  # tests own their schema; the app creates none (v3.1 step 05)
    return create_app(
        engine,
        https_only=False,
        session_secret="test-secret",
        bootstrap_admin=ADMIN,
    )
```

- [x] **Step 4:** `python -m pytest -q` → PASS, exit 0. The 218 app-fixture
      tests must all still pass; if any error with `no such table`, a conftest
      was missed.
- [x] **Step 5:** `git commit -m "feat(api): the serving path no longer creates schema — Alembic owns it"`

### Task 5: models↔migrations parity guard (the test that would have caught `964362f`)

**Files:**
- Modify: `tests/db/test_db_migration.py`

`test_migration_creates_full_schema` compares **table names** only, which is why
`ReviewArtifact` could land in `964362f` with its revision two commits behind.
`alembic.autogenerate.compare_metadata` compares tables, columns, types,
nullability, indexes and constraints, and returns **0 diffs** against the
current head — so it can be asserted empty with no tolerance list.

- [x] **Step 1: write the guard** in `tests/db/test_db_migration.py`:

```python
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext


def test_migrations_match_the_models_exactly(tmp_path, monkeypatch):
    """`alembic upgrade head` must reproduce SQLModel.metadata down to the
    column — the guard the 2026-07-30 incident was missing. A model added
    without a revision (or a revision that drifts from its model) fails here,
    one commit after it is written, instead of one deploy later.

    `compare_metadata` returns 0 differences against the current head, so the
    assertion carries no tolerance list: any entry is a real drift."""
    monkeypatch.delenv("MALUS_DB_URL", raising=False)  # alembic/env.py:28 reads it first
    url = f"sqlite:///{tmp_path / 'parity.db'}"
    command.upgrade(_alembic_config(url), "head")

    with create_engine(url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)

    assert diff == [], "migrations drifted from the models: " + repr(diff)
```

- [x] **Step 2: prove it has teeth** (it passes as written — there is no drift
      today, so the failing-first step is a deliberate injection). Add a scratch
      column to `src/malus/db/models.py`, e.g. inside `class ReviewArtifact`:

```python
    scratch_drift_column: Optional[str] = None
```

  `python -m pytest -q tests/db/test_db_migration.py` → **FAIL** with
  `migrations drifted from the models: [('add_column', None, 'review_artifacts',
  Column('scratch_drift_column', ...))]`. Remove the scratch column
  (`git checkout -- src/malus/db/models.py`) and re-run → PASS. Do **not**
  commit the scratch column.
- [x] **Step 3:** `python -m pytest -q` → PASS, exit 0.
- [x] **Step 4:** `git commit -m "test(db): pin migrations to the models column-by-column"`

### Task 6: a FRESH empty database boots through `alembic upgrade head` alone

**Files:**
- Modify: `tests/db/test_schema_authority.py` (extend)

- [x] **Step 1: failing test:**

```python
def test_fresh_deployment_boots_from_alembic_alone(tmp_path, monkeypatch):
    """The container path, end to end: empty volume -> `alembic upgrade head`
    (docker-entrypoint.sh) -> `malus serve` (create_app, which creates nothing)
    -> /health 200 and a working login. No `create_all` anywhere."""
    from fastapi.testclient import TestClient

    from malus.api import create_app
    from malus.db import make_engine

    monkeypatch.delenv("MALUS_DB_URL", raising=False)
    url = f"sqlite:///{tmp_path / 'fresh-volume.db'}"
    engine = make_engine(url)

    upgrade_head(engine)                      # the entrypoint's only schema step

    assert current_revision(engine) == "c4d5e6f7a8b9"
    app = create_app(
        engine, https_only=False, session_secret="s", bootstrap_admin=("admin", "admin-pw")
    )
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.post(
        "/auth/login", json={"username": "admin", "password": "admin-pw"}
    ).status_code == 200


def test_fresh_deployment_second_boot_is_a_no_op(tmp_path, monkeypatch):
    """Restarting the container re-runs the entrypoint; the second
    `alembic upgrade head` must be a no-op, not a collision."""
    monkeypatch.delenv("MALUS_DB_URL", raising=False)
    engine = create_engine(f"sqlite:///{tmp_path / 'restart.db'}")

    upgrade_head(engine)
    upgrade_head(engine)

    assert current_revision(engine) == "c4d5e6f7a8b9"
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set(
        SQLModel.metadata.tables
    )
```

- [x] **Step 2:** run `python -m pytest -q tests/db/test_schema_authority.py`.
      Both pass only if tasks 1–4 are correct — if `create_app` still created
      schema, the first would pass for the wrong reason, which is why task 4's
      `test_create_app_creates_no_schema` runs alongside it.
- [x] **Step 3:** `python -m pytest -q` → PASS, exit 0.
- [x] **Step 4:** `git commit -m "test(db): a fresh database boots from alembic upgrade head alone"`

### Task 7: a PRE-EXISTING drifted database boots through `alembic upgrade head` alone

The production database as it actually exists: schema partly created by
`create_all`, stamped behind, and carrying real rows.

**Files:**
- Modify: `tests/db/test_schema_authority.py` (extend)

- [x] **Step 1: failing test:**

```python
def test_drifted_deployment_boots_from_alembic_alone(tmp_path, monkeypatch):
    """The 2026-07-30 server state: stamped at a7c31e90d412 while `create_all`
    had already made review_artifacts and the reopen column, plus a pre-v3
    review row stuck at `draft` with a frozen baseline. One
    `alembic upgrade head` must converge the schema *and* run the phase
    backfill, and the app must then boot with no schema creation of its own."""
    import sqlalchemy as sa
    from alembic import command
    from fastapi.testclient import TestClient

    from malus.api import create_app
    from malus.db import create_all, make_engine

    monkeypatch.delenv("MALUS_DB_URL", raising=False)
    url = f"sqlite:///{tmp_path / 'drifted-volume.db'}"
    cfg = _alembic_config(url)          # module-level helper, see below
    command.upgrade(cfg, "a7c31e90d412")
    engine = make_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO users (id, username, display_name, is_active, created,"
            " is_admin, is_ai, must_change_password)"
            " VALUES (1, 'own', 'own', 1, '2026-01-01 00:00:00', 0, 0, 0)"
        ))
        conn.execute(sa.text(
            "INSERT INTO reviews (id, review_id_str, owner_id, status, created)"
            " VALUES (1, 'LEGACY-R1', 1, 'draft', '2026-01-01')"
        ))
        conn.execute(sa.text(
            "INSERT INTO documents (id, review_id, name) VALUES (1, 1, 'd.md')"
        ))
        conn.execute(sa.text(
            "INSERT INTO document_versions (id, document_id, ordinal, content,"
            " content_hash, is_baseline, is_final, created)"
            " VALUES (1, 1, 1, '# doc', 'h', 1, 0, '2026-01-01 00:00:00')"
        ))
    create_all(engine)                  # the old bootstrap, mid-window

    upgrade_head(engine)                # the entrypoint's only schema step

    assert current_revision(engine) == "c4d5e6f7a8b9"
    insp = inspect(engine)
    assert set(insp.get_table_names()) - {"alembic_version"} == set(SQLModel.metadata.tables)
    assert "reopen_requested_at" in {c["name"] for c in insp.get_columns("reviewer_copies")}
    with engine.connect() as conn:      # the backfill ran, no row lost
        assert conn.execute(
            sa.text("SELECT status FROM reviews WHERE review_id_str = 'LEGACY-R1'")
        ).scalar() == "in_review"
        assert conn.execute(sa.text("SELECT count(*) FROM users")).scalar() == 1

    client = TestClient(create_app(engine, https_only=False, session_secret="s"))
    assert client.get("/health").status_code == 200
```

  Add the Alembic config helper to the top of `tests/db/test_schema_authority.py`
  (mirroring `tests/db/test_db_migration.py:19`):

```python
from alembic.config import Config


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.attributes["configure_logger"] = False
    return cfg
```

- [x] **Step 2:** run → this is the acceptance test for the whole step. It fails
      if the backfill did not become a revision (status stays `draft`) or if a
      revision is not idempotent (`table review_artifacts already exists`).
- [x] **Step 3:** `python -m pytest -q` → PASS, exit 0.
- [x] **Step 4:** `git commit -m "test(db): a drifted database converges on alembic upgrade head"`

### Task 8: write the convention down, and enforce it

**Files:**
- Modify: `CLAUDE.md` (§Conventions)
- Modify: `docs/ops/runbook.md` (new §Schema authority, after §Upgrade)
- Modify: `docs/spec/data-model.md` (§2 Migration/backfill, §5, §Sources)
- Create: `tests/db/test_revision_conventions.py`

- [x] **Step 1: the lint test** — `tests/db/test_revision_conventions.py`:

```python
"""Every new Alembic revision must be idempotent (v3.1 step 05).

Databases in the wild were built by two authorities before this step; a
revision that assumes an object is absent takes the container down on the next
deploy, because `set -e` in docker-entrypoint.sh aborts the boot (2026-07-30).
On SQLite, DDL is additionally non-transactional, so a revision that fails
halfway leaves its earlier objects behind — the next attempt hits the same
wall. Inspect before you create.

The four pre-incident revisions are grandfathered by explicit id: they are
applied everywhere and rewriting applied history is a worse risk than the
debt. Every revision written from now on is checked.
"""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory

from malus.db.migrations import alembic_config

GRANDFATHERED = {
    "01135281e9f4",  # initial schema
    "8208e7694462",  # user auth columns
    "f1a2b3c4d5e6",  # reviewer private notes
    "a7c31e90d412",  # member colors
}


def _upgrade_body(path: str) -> str:
    source = Path(path).read_text(encoding="utf-8")
    return source.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]


def test_every_new_revision_guards_its_ddl():
    for script in ScriptDirectory.from_config(alembic_config()).walk_revisions():
        if script.revision in GRANDFATHERED:
            continue
        body = _upgrade_body(script.path)
        if "op.create_table(" in body or "op.add_column(" in body:
            assert "inspect(" in body, (
                f"revision {script.revision} ({Path(script.path).name}) creates a "
                "schema object without an existence guard — see CLAUDE.md "
                "§Conventions and docs/ops/runbook.md §Schema authority"
            )
```

- [x] **Step 2: prove it has teeth.** Create a throwaway
      `alembic/versions/zz00deadbeef_scratch.py` with
      `down_revision = 'c4d5e6f7a8b9'` and an unguarded
      `op.add_column('users', sa.Column('scratch', sa.String(), nullable=True))`;
      `python -m pytest -q tests/db/test_revision_conventions.py` → **FAIL**
      naming `zz00deadbeef`. Delete the file and re-run → PASS. Do **not**
      commit it.
- [x] **Step 3: the documentation.** `CLAUDE.md` §Conventions — append two bullets:

```markdown
- **Alembic is the single schema authority.** `alembic upgrade head` (run by
  `docker-entrypoint.sh` before the server starts) owns the production schema;
  `create_app` creates nothing. `SQLModel.metadata.create_all` is for tests and
  for `malus init-db`, which stamps head in the same call so a database is
  never left unstamped. A model change without a revision is a bug —
  `tests/db/test_db_migration.py::test_migrations_match_the_models_exactly`
  fails on it (the 2026-07-30 incident).
- **Every Alembic revision is idempotent**: inspect before you create
  (`sa.inspect(op.get_bind())` — see `b9e4d5f6a701`), and data migrations are
  written as set-based SQLAlchemy Core statements, never through the ORM.
  Enforced by `tests/db/test_revision_conventions.py`.
```

  `docs/ops/runbook.md` — new section between §Upgrade and §Backup & restore:

```markdown
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
```

  `docs/spec/data-model.md` — rewrite the §2 **Migration/backfill** paragraph
  (it currently says the backfill is "run from `create_all` on every startup"):

```markdown
**Migration/backfill:** pre-v3 databases have rows stuck at `draft` (no phase
column existed before) or at the removed `active` value. Alembic revision
`c4d5e6f7a8b9` (`alembic/versions/c4d5e6f7a8b9_v3_phase_backfill.py`) promotes
any `draft`/`active` review that already has a frozen baseline to `in_review`,
**once**, inside the version chain; reviews with no baseline yet are left at
`draft`, and `closeout`/`finalized` rows are never touched. It was a Python
function re-run on every startup (`migrate_review_phases`) until v3.1 step 05
made Alembic the single schema authority.
```

  and §5, replacing the "The schema is created for production…" bullet:

```markdown
- The schema is owned by Alembic: `alembic upgrade head`, run by
  `docker-entrypoint.sh` before the server starts. `SQLModel.metadata.create_all`
  is a test helper (and the `malus init-db` bootstrap, which stamps head in the
  same call). `tests/db/test_db_migration.py` verifies that the chain applies on
  a fresh SQLite file and matches the model metadata **column by column**
  (`alembic.autogenerate.compare_metadata` → no differences), and that a
  drifted pre-v3.1 database converges on `upgrade head`.
```

  Add to §Sources: `docs/plan/v3.1/05-one-schema-authority.md` and
  `src/malus/db/migrations.py`.

  Finally, `docs/plan/v3.1/00-design.md` §Steps — append a row so the index is
  not silently wrong:

```markdown
| 5 | `05-one-schema-authority.md` | Alembic becomes the single schema authority: serving path stops creating schema, backfills move into revisions, models↔migrations parity guard. Added 2026-07-30 after the production incident of that day; not part of the original UX wave. | — |
```

- [x] **Step 4:** `python -m pytest -q` → PASS, exit 0.
- [x] **Step 5:** `git commit -m "docs: Alembic is the single schema authority; revisions must be idempotent"`

## Definition of Done

- [x] Every deliverable checked; `python -m pytest -q` green, exit 0, with no
      test deleted or weakened. In particular
      `tests/db/test_db_migration.py::test_upgrade_head_after_create_all_already_ran`
      (the `a5a0125` regression pin) passes unmodified.
- [x] `grep -rn "create_all" src/` returns **only** `src/malus/db/session.py`
      and `src/malus/db/__init__.py`. No hit in `src/malus/api/`, none in
      `src/malus/cli.py`.
- [x] `grep -rn "migrate_review_phases\|migrate_reviewer_copy_columns" src/`
      returns nothing.
- [~] **Docker, fresh volume — the whole point of the step:** the Docker daemon
      was not running on the implementation machine, so this was verified by
      reproducing the entrypoint sequence locally with the real `alembic` CLI —
      see `## Deviations` #5. The migration log matched the expected text below
      line for line.

```sh
docker compose down -v
docker compose up -d --build
docker compose logs app
```

  expected, in order:

```
maluS: applying database migrations (alembic upgrade head)...
INFO  [alembic.runtime.migration] Running upgrade  -> 01135281e9f4, initial schema
INFO  [alembic.runtime.migration] Running upgrade 01135281e9f4 -> 8208e7694462, user auth columns
INFO  [alembic.runtime.migration] Running upgrade 8208e7694462 -> f1a2b3c4d5e6, reviewer private notes (v1.4)
INFO  [alembic.runtime.migration] Running upgrade f1a2b3c4d5e6 -> a7c31e90d412, member colors (v2.1): users.color + review_members.color
INFO  [alembic.runtime.migration] Running upgrade a7c31e90d412 -> b9e4d5f6a701, v3: review_artifacts table + reviewer_copies.reopen_requested_at
INFO  [alembic.runtime.migration] Running upgrade b9e4d5f6a701 -> c4d5e6f7a8b9, v3 phase backfill: draft|active -> in_review for frozen reviews
maluS: starting server on 0.0.0.0:8000 ...
```

```sh
curl -fsS http://127.0.0.1:8000/health          # -> {"status":"ok","version":"2.3.0"}
docker compose exec app alembic current         # -> c4d5e6f7a8b9 (head)
```

- [~] **Docker, restart is a no-op** (the second authority is gone): verified
      the same way — a second `alembic upgrade head` on the same file emitted
      **0** `Running upgrade` lines and stayed at `c4d5e6f7a8b9`.

```sh
docker compose restart app
docker compose logs --tail=20 app
```

  expected: the `maluS: applying database migrations…` line, **no**
  `Running upgrade` line at all, then `maluS: starting server…`; `/health` 200.

- [ ] **NOT DONE — operator action.** Deploying to the ALUM server is outside
      what an implementation session may do. Run this before/with the first
      deploy of this step: **Docker, the real production volume**: back it up
      (`docs/ops/runbook.md` §Backup & restore) **before** the first deploy of
      this step, then `docker compose up -d --build` and check
      `docker compose exec app alembic current` reports `c4d5e6f7a8b9`, and that
      no review changed phase unexpectedly (the backfill only promotes
      `draft`/`active` rows that have a frozen baseline; on a healthy v3
      database there are none).
- [x] `malus init-db --db sqlite:///$(mktemp -u).db` prints
      `created and stamped schema at head`, and `malus serve --db <that file>`
      then starts (no schema error).

## Deviations

Recorded during implementation, 2026-07-30. Nothing in the Decision section was
redesigned; these are corrections to the step's own test code plus one gap in
its investigation.

**1. `test_stamp_head_marks_an_unstamped_database` pins `c4d5e6f7a8b9`, not
`b9e4d5f6a701`.** Task 1 wrote that assertion with the comment "head at task 1";
task 2 makes `c4d5e6f7a8b9` the head, so the assertion was updated there. It now
matches what tasks 3, 6 and 7 assert.

**2. `tests/api/test_api.py` builds a second app inline — the F1 table missed
it.** F1 lists `create_app`'s callers as "the `app` fixture of `tests/api`,
`tests/web`, `tests/e2e`, `tests/mcp`", so task 4 only patched the four
conftests. But `test_export_import_roundtrip_across_databases`
(`tests/api/test_api.py:111`) constructs a *second* `create_app` with its own
`make_engine("sqlite://")` to test a cross-database round-trip; with the serving
path no longer creating schema it failed on `no such table: users`. Fixed the
same way as the conftests — `create_all(other_engine)` before `create_app`.
(`tests/ops/test_ops.py:21` also calls `create_app` directly but only hits
`/health`, which touches no table, and passes `bootstrap_admin=None`.)

**3. Task 4's failing-first step hangs the suite if run as written.** The step
says to run `test_serve_refuses_a_database_without_schema` before implementing
`_require_schema`. Without the preflight, `serve` reaches `uvicorn.run` and
boots a real server inside the test runner, which never returns. Task 4's other
two tests were run failing-first as normal; the `serve` test was written first
but executed only after `_require_schema` landed. A future step adding a `serve`
test should implement the guard before running it.

**4. The DoD grep `no hit in src/malus/api/` has one — in a docstring the step
itself prescribes.** Task 4's `create_app` docstring (specified verbatim by this
file) reads "Tests create their own schema with ``malus.db.create_all``". The
substantive gate — zero *calls* — holds: `grep -rn "create_all(" src/` outside
`src/malus/db/session.py` returns 0.

**5. Docker verification was done by reproducing the entrypoint, not by running
it.** The Docker daemon was not running on the implementation machine. Since
`docker-entrypoint.sh` is four lines — `alembic upgrade head` then
`exec malus serve` — the same sequence was run directly against a fresh SQLite
file using the real `alembic` CLI and the real `malus serve`:

- first boot printed exactly the six `Running upgrade` lines listed in the DoD,
  ending at `c4d5e6f7a8b9`, and `alembic current` reported `c4d5e6f7a8b9 (head)`;
- `malus serve` then started, `/health` returned
  `{"status":"ok","version":"2.3.0"}`, and the bootstrapped admin logged in;
- a second `alembic upgrade head` on the same file emitted **0**
  `Running upgrade` lines and stayed at head.

What this does *not* cover is the image packaging itself (`WORKDIR /app`, the
`COPY alembic.ini ./` / `COPY alembic ./alembic` lines) — unchanged by this
step, but worth eyeballing on the first `docker compose up --build`.

Also verified end to end outside Docker: `malus init-db` created and stamped a
new file at `c4d5e6f7a8b9`, refused the second invocation with exit 1, `malus
serve` on an empty database exited **2** with the actionable message, and `malus
serve` on the init-db file started and answered `/health`.

## Out of scope

- **Moving `alembic/` inside the wheel.** `malus.db.migrations` resolves the
  scripts through `MALUS_ALEMBIC_INI` → repo root → cwd, which covers the
  source checkout, the test suite and the image (WORKDIR `/app`). Packaging
  them would touch `pyproject.toml`, `alembic.ini` and the `Dockerfile` for no
  behaviour change here.
- **Rewriting the four grandfathered revisions** to be idempotent. They are
  applied on every existing database; the lint test allow-lists them by id and
  records the debt.
- **Running the suite against Postgres in CI.** Portability is pinned by
  dual-dialect compilation (task 2) and by using Core constructs only; a
  Postgres CI service is a separate decision (it would add a container to every
  run and `psycopg` to the dev extra).
- **An `alembic downgrade` path for the data backfill** — deliberately a no-op
  (the pre-migration `draft`-vs-`active` value is not recoverable).
- **A health endpoint that reports the schema revision**, and alerting on a
  behind-head database. Worth doing; not this step.
- CHANGELOG entry and the `asset_v` bump — v3 `06-release.md`, which ships the
  single `3.0.0` bump.
- Any UX change: v3.1 steps 01–04 own the closeout viewer, terminate/reopen,
  diff views and downloads. This step touches no template and no route.

## Sources

- The 2026-07-30 incident and its hotfix: commit `a5a0125`
  (`fix(db): revision b9e4d5f6a701 tolerates what create_all already made`),
  the commits that opened the window — `964362f` (model) and `3ea2a56`
  (revision) — and `tests/db/test_db_migration.py::test_upgrade_head_after_create_all_already_ran`.
- Alberto Boffi's decision, 2026-07-30 (this session): Alembic becomes the
  single authority; `create_all` confined to tests plus an explicit developer
  bootstrap; both backfills into revisions; stamp-on-create and revision
  idempotency as belt and braces.
- Current code read for the facts in §Investigation: `src/malus/db/session.py`,
  `src/malus/api/app.py:66-118`, `src/malus/cli.py:48-78`, `alembic/env.py`,
  `alembic/versions/*.py` (all five), `alembic.ini`, `docker-entrypoint.sh`,
  `Dockerfile`, `docker-compose.yml`, `pyproject.toml`,
  `src/malus/services/core.py` (`freeze_baseline:152`, `reopen_review:889`),
  `tests/{db,services,api,web,e2e,mcp}/conftest.py`,
  `tests/db/test_db_migration.py`, `tests/db/test_migration_v3.py`,
  `tests/test_cli.py`, `tests/test_pdfgen.py`, `docs/ops/runbook.md`.
- Measurements (F2, F3, F5): test-function counts by `grep -rE "^\s*(async )?def test_"`;
  fresh-database schema comparison and `compare_metadata` run against
  `alembic upgrade head` on a temporary SQLite file; statement compilation
  under `sqlalchemy.dialects.sqlite` and `sqlalchemy.dialects.postgresql`.
- `docs/plan/v3.1/00-design.md` (the cycle this step is appended to),
  `docs/plan/v3/00-design.md` §Migration, `docs/spec/data-model.md` §2/§5,
  ADR 0002 (SQLModel + Alembic on SQLite→Postgres), `CLAUDE.md` §Conventions.
