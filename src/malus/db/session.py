"""Engine and session setup.

SQLite is the v1 store (WAL mode for file-based DBs), Postgres-ready through the
same ORM (ADR 0002). Foreign-key enforcement is enabled on every SQLite
connection (it is off by default in SQLite).
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

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


def migrate_review_phases(session: Session) -> None:
    """v3 one-time backfill: pre-v3 rows stuck at ``draft`` or the removed v2
    ``active`` value are promoted to ``in_review`` if their baseline is
    already frozen (the ``ReviewStatus`` phase column is new in v3; earlier
    rows have no phase to speak of, only draft-vs-frozen). Never touches
    ``closeout``/``finalized`` rows, and leaves drafts with no baseline alone.
    Idempotent — re-running finds nothing left to promote."""
    from malus.db.models import Review, ReviewStatus
    from malus.repo import ReviewRepo, VersionRepo

    rows = session.exec(select(Review).where(Review.status.in_(("draft", "active")))).all()
    for review in rows:
        if VersionRepo(session).baseline(review) is not None:
            ReviewRepo(session).set_status(review, ReviewStatus.IN_REVIEW.value)


def migrate_reviewer_copy_columns(engine: Engine) -> None:
    """v3 additive column: ``reviewer_copies.reopen_requested_at`` (Submit is
    irreversible; a reviewer requests a reopen the owner approves).
    ``create_all`` only creates missing tables, never columns — pre-v3
    databases need the ALTER. Idempotent via a PRAGMA column check."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(engine).get_columns("reviewer_copies")}
    if "reopen_requested_at" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE reviewer_copies ADD COLUMN reopen_requested_at TIMESTAMP")
            )


def create_all(engine: Engine) -> None:
    """Create every table on ``engine`` (used by tests and first-run bootstrap;
    production schema changes go through Alembic), then run the v3 phase
    backfill (``migrate_review_phases``) so pre-v3 databases come back up on
    ``in_review`` instead of stuck at ``draft``/``active``. This is the one
    init path shared by the CLI (``malus import``/``serve``) and the API
    factory (``create_app``), so wiring the backfill in here — rather than in
    each caller — is enough to cover both.

    NOT schema-only: this opens a short-lived session and COMMITS the backfill,
    so callers must not invoke it while unrelated uncommitted work is pending
    in another session on the same engine."""
    from malus.db import models  # noqa: F401  ensure tables are registered on metadata

    SQLModel.metadata.create_all(engine)
    migrate_reviewer_copy_columns(engine)
    with Session(engine) as session:
        migrate_review_phases(session)
        session.commit()
