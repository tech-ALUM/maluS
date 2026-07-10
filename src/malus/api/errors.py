"""Consistent HTTP error model (ADR: one contract for GUI + agent).

- 403 — closure-authority violation (``ClosureAuthorityError``): the owner/AI, or
  the wrong reviewer, tried to issue a verdict.
- 409 — illegal state transition (``TransitionError``), unique conflict
  (``IntegrityError``), or an unmet precondition (``ValueError`` from a service,
  e.g. the traceability gate).
- 404 — endpoints raise ``HTTPException(404)`` for a missing review/RID/user.
- 422 — request-body validation (FastAPI's ``RequestValidationError``, automatic).

Handler lookup walks the exception's MRO, so ``ClosureAuthorityError`` (403) is
matched before its ``TransitionError`` base (409).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from malus.models import ClosureAuthorityError, TransitionError


def _detail(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": message})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ClosureAuthorityError)
    async def _closure(_request: Request, exc: ClosureAuthorityError) -> JSONResponse:
        return _detail(403, str(exc))

    @app.exception_handler(TransitionError)
    async def _transition(_request: Request, exc: TransitionError) -> JSONResponse:
        return _detail(409, str(exc))

    @app.exception_handler(IntegrityError)
    async def _integrity(_request: Request, _exc: IntegrityError) -> JSONResponse:
        return _detail(409, "conflict: the resource already exists or violates a constraint")

    @app.exception_handler(ValueError)
    async def _value(_request: Request, exc: ValueError) -> JSONResponse:
        return _detail(409, str(exc))
