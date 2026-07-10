"""FastAPI dependencies: a per-request database session.

The engine lives on ``app.state.engine`` (set by ``create_app``), so tests can
inject an in-memory engine. The session commits on success and rolls back on any
error, so a failed request never leaves a partial write.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlmodel import Session


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
