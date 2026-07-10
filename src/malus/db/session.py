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
    """Create every table on ``engine`` (used by tests and first-run bootstrap;
    production schema changes go through Alembic)."""
    from malus.db import models  # noqa: F401  ensure tables are registered on metadata

    SQLModel.metadata.create_all(engine)
