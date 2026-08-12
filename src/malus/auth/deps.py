"""Authentication dependencies: the current user from the session cookie or,
for programmatic clients (the AI agent, Step 7), HTTP Basic credentials."""

from __future__ import annotations

import base64
import binascii

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from malus.api.deps import get_session
from malus.auth import throttle
from malus.auth.service import authenticate
from malus.db.models import User


def _basic_auth_user(request: Request, session: Session) -> User | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return None
    try:
        username, _, password = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    # Basic auth is accepted on *every* protected endpoint, so it is as much a
    # guessing surface as the login form and is throttled the same way (ADR 0005).
    throttle.check(request, username)
    user = authenticate(session, username, password)
    throttle.record(request, username, ok=user is not None)
    return user


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    uid = request.session.get("user_id")
    if uid is not None:
        user = session.get(User, uid)
        if user is not None and user.is_active:
            return user
        request.session.clear()
    # Programmatic clients (the MCP AI reviewer) authenticate with HTTP Basic.
    user = _basic_auth_user(request, session)
    if user is not None:
        return user
    raise HTTPException(
        status_code=401,
        detail="authentication required",
        headers={"WWW-Authenticate": 'Basic realm="maluS"'},
    )


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin role required")
    return user
