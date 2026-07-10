"""FastAPI application factory.

``create_app`` wires the engine (on ``app.state`` so tests can inject an
in-memory one), installs the error handlers, and mounts the routes. OpenAPI is
served at ``/openapi.json`` and Swagger UI at ``/docs`` automatically.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from sqlalchemy.engine import Engine

import malus
from malus.api.errors import install_error_handlers
from malus.api.routes import router
from malus.db import DEFAULT_URL, create_all, make_engine


def create_app(engine: Engine | None = None, *, create_schema: bool = True) -> FastAPI:
    app = FastAPI(
        title="maluS API",
        version=malus.__version__,
        description=(
            "Formal RID-based review management — one HTTP contract for the "
            "browser GUI (Steps 5–6) and the AI agent (Step 7)."
        ),
    )
    app.state.engine = engine or make_engine(os.environ.get("MALUS_DB_URL", DEFAULT_URL))
    if create_schema:
        create_all(app.state.engine)
    install_error_handlers(app)
    app.include_router(router)
    return app
