"""User auth operations: create, authenticate, set password, admin bootstrap."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from malus.auth.passwords import hash_password, verify_password
from malus.db.models import User


def create_user(
    session: Session,
    *,
    username: str,
    password: Optional[str] = None,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    is_admin: bool = False,
    is_ai: bool = False,
    must_change_password: bool = False,
) -> User:
    user = User(
        username=username,
        display_name=display_name or username,
        email=email,
        password_hash=hash_password(password) if password else None,
        is_admin=is_admin,
        is_ai=is_ai,
        must_change_password=must_change_password,
    )
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, username: str, password: str) -> Optional[User]:
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def set_password(session: Session, user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    user.must_change_password = False
    session.add(user)
    session.flush()


def bootstrap_admin(session: Session, username: str, password: str) -> Optional[User]:
    """Create a forced-password-change admin, but only if there are no users yet."""
    if session.exec(select(User)).first() is not None:
        return None
    return create_user(
        session, username=username, password=password, is_admin=True, must_change_password=True
    )
