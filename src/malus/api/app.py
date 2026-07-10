"""FastAPI application factory.

Wires the engine (on ``app.state`` so tests can inject an in-memory one), signed
httponly session cookies (SameSite=strict → CSRF-safe), the error handlers, and
the auth + review routers. OpenAPI is at ``/openapi.json``, Swagger at ``/docs``.
An admin is bootstrapped from ``MALUS_ADMIN_USER``/``MALUS_ADMIN_PASSWORD`` (or
the ``bootstrap_admin`` arg) when the user table is empty.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

import malus
from malus.api.errors import install_error_handlers
from malus.api.routes import router
from malus.auth.routes import auth_router, users_router
from malus.auth.service import bootstrap_admin as _bootstrap_admin
from malus.db import DEFAULT_URL, create_all, make_engine
from malus.web import STATIC_DIR
from malus.web import web as web_router
from malus.web.accounts import accounts as accounts_router

# GUI paths reachable while a password change is still required.
_PW_EXEMPT = {"/ui/account/password", "/ui/logout"}


async def _force_password_change(request, call_next):
    """Redirect /ui pages to the password page until must_change_password clears."""
    session = request.scope.get("session")
    if session and session.get("must_change_password"):
        path = request.url.path
        if path.startswith("/ui") and path not in _PW_EXEMPT:
            return RedirectResponse("/ui/account/password", status_code=303)
    return await call_next(request)

# Dev fallback only — production MUST set MALUS_SECRET_KEY. No real secret is committed.
_DEV_SECRET = "dev-insecure-secret-change-me"


def create_app(
    engine: Optional[Engine] = None,
    *,
    create_schema: bool = True,
    session_secret: Optional[str] = None,
    https_only: bool = True,
    bootstrap_admin: Optional[tuple[str, str]] = None,
) -> FastAPI:
    app = FastAPI(
        title="maluS API",
        version=malus.__version__,
        description=(
            "Formal RID-based review management — one authenticated HTTP contract "
            "for the browser GUI (Steps 5–6) and the AI agent (Step 7)."
        ),
    )
    app.state.engine = engine or make_engine(os.environ.get("MALUS_DB_URL", DEFAULT_URL))
    if create_schema:
        create_all(app.state.engine)

    # Added before SessionMiddleware so it runs *inside* it (session is populated).
    app.add_middleware(BaseHTTPMiddleware, dispatch=_force_password_change)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret or os.environ.get("MALUS_SECRET_KEY", _DEV_SECRET),
        same_site="strict",
        https_only=https_only,
    )
    install_error_handlers(app)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        """Liveness probe (public) for the reverse proxy / orchestrator."""
        return {"status": "ok", "version": malus.__version__}

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(router)
    app.include_router(web_router)
    app.include_router(accounts_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    admin = bootstrap_admin or (
        (os.environ["MALUS_ADMIN_USER"], os.environ["MALUS_ADMIN_PASSWORD"])
        if os.environ.get("MALUS_ADMIN_USER") and os.environ.get("MALUS_ADMIN_PASSWORD")
        else None
    )
    if admin is not None:
        with Session(app.state.engine) as session:
            _bootstrap_admin(session, admin[0], admin[1])
            session.commit()

    return app
