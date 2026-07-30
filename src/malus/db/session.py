"""Engine and session setup.

SQLite is the v1 store (WAL mode for file-based DBs), Postgres-ready through the
same ORM (ADR 0002). Foreign-key enforcement is enabled on every SQLite
connection (it is off by default in SQLite).
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

# URLs that denote an in-memory database, which must share one connection so the
# schema created by ``create_all`` is visible to every session.
_IN_MEMORY = frozenset({"sqlite://", "sqlite:///:memory:"})

DEFAULT_URL = "sqlite:///malus.db"


def make_engine(url: str = DEFAULT_URL, *, echo: bool = False, wal: bool = True) -> Engine:
    """Create an engine, applying SQLite pragmas (foreign keys always; WAL for
    file-based databases)."""
    is_sqlite = url.startswith("sqlite")
    is_mem = url in _IN_MEMORY
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    kwargs = {"poolclass": StaticPool} if is_mem else {}
    engine = create_engine(url, echo=echo, connect_args=connect_args, **kwargs)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if wal and not is_mem:
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


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
