"""Authentication dependencies: the current user from the session cookie."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from malus.api.deps import get_session
from malus.db.models import User


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    uid = request.session.get("user_id")
    if uid is None:
        raise HTTPException(status_code=401, detail="authentication required")
    user = session.get(User, uid)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin role required")
    return user
