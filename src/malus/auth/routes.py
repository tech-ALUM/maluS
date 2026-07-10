"""Auth + user-management routes (login/logout/me/change-password; admin CRUD)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from malus.api.deps import get_session
from malus.auth.deps import get_current_user, require_admin
from malus.auth.passwords import verify_password
from malus.auth.service import authenticate, create_user, set_password
from malus.db.models import User


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_admin: bool = False
    is_ai: bool = False


class UserOut(BaseModel):
    username: str
    display_name: str
    email: Optional[str] = None
    is_active: bool
    is_admin: bool
    is_ai: bool
    must_change_password: bool

    @classmethod
    def from_row(cls, u: User) -> "UserOut":
        return cls(
            username=u.username,
            display_name=u.display_name,
            email=u.email,
            is_active=u.is_active,
            is_admin=u.is_admin,
            is_ai=u.is_ai,
            must_change_password=u.must_change_password,
        )


auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/login", response_model=UserOut)
def login(request: Request, body: LoginIn, session: Session = Depends(get_session)):
    user = authenticate(session, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid username or password")
    request.session["user_id"] = user.id
    return UserOut.from_row(user)


@auth_router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@auth_router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.from_row(user)


@auth_router.post("/change-password", response_model=UserOut)
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not verify_password(user.password_hash, body.old_password):
        raise HTTPException(status_code=403, detail="current password is incorrect")
    set_password(session, user, body.new_password)
    return UserOut.from_row(user)


users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.post("", response_model=UserOut, status_code=201)
def create_user_endpoint(
    body: UserCreate,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    if session.exec(select(User).where(User.username == body.username)).first() is not None:
        raise HTTPException(status_code=409, detail=f"username already exists: {body.username}")
    user = create_user(
        session,
        username=body.username,
        password=body.password,
        display_name=body.display_name,
        email=body.email,
        is_admin=body.is_admin,
        is_ai=body.is_ai,
        must_change_password=True,
    )
    return UserOut.from_row(user)


@users_router.get("", response_model=list[UserOut])
def list_users(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    return [UserOut.from_row(u) for u in session.exec(select(User).order_by(User.id)).all()]
