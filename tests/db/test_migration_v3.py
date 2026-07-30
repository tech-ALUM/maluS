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
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

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
