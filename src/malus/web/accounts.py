"""Account-management GUI (v1 Step 10): self-service password change, admin
user CRUD + activation + reset, and per-review role assignment.

Server-rendered and admin-gated. Every action goes through ``malus.auth`` +
the repositories; the GUI adds no authority the server does not enforce. The
closure invariant is untouched (this step manages accounts/roles, not verdicts).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from malus.api import authz
from malus.api.deps import get_session
from malus.auth.passwords import verify_password
from malus.auth.service import create_user, set_password
from malus.constants import Role
from malus.db.models import User
from malus.repo import ReviewRepo
from malus.web.router import _current, _review_or_404, templates

accounts = APIRouter(include_in_schema=False)
_LOGIN = RedirectResponse("/ui/login", status_code=303)

_ROLE_VALUES = {Role.OWNER.value, Role.REVIEWER.value, Role.MODERATOR.value}


def _admin_or_redirect(request: Request, session: Session):
    """Return the admin user, ``None`` (caller redirects to login), or raise 403."""
    user = _current(request, session)
    if user is None:
        return None
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin role required")
    return user


def _user_or_404(session: Session, username: str) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(status_code=404, detail=f"no such user: {username}")
    return user


# --------------------------------------------------------------------------- #
# self-service: change my password
# --------------------------------------------------------------------------- #


@accounts.get("/ui/account/password", response_class=HTMLResponse)
def password_page(request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    return templates.TemplateResponse(request, "account_password.html", {"user": user, "error": None})


@accounts.post("/ui/account/password")
def password_submit(
    request: Request,
    current: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    if not verify_password(user.password_hash, current):
        return templates.TemplateResponse(
            request,
            "account_password.html",
            {"user": user, "error": "Current password is incorrect."},
            status_code=403,
        )
    set_password(session, user, new_password)
    request.session["must_change_password"] = False
    return RedirectResponse("/ui/reviews", 303)


# --------------------------------------------------------------------------- #
# admin: user management
# --------------------------------------------------------------------------- #


@accounts.get("/ui/admin/users", response_class=HTMLResponse)
def users_page(request: Request, session: Session = Depends(get_session)):
    admin = _admin_or_redirect(request, session)
    if admin is None:
        return _LOGIN
    users = session.exec(select(User).order_by(User.id)).all()
    return templates.TemplateResponse(request, "admin_users.html", {"user": admin, "users": users})


@accounts.get("/ui/admin/users/new", response_class=HTMLResponse)
def new_user_page(request: Request, session: Session = Depends(get_session)):
    admin = _admin_or_redirect(request, session)
    if admin is None:
        return _LOGIN
    return templates.TemplateResponse(request, "admin_user_new.html", {"user": admin, "error": None})


@accounts.post("/ui/admin/users/new")
def new_user_submit(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    kind: str = Form("regular"),  # regular | admin | ai
    session: Session = Depends(get_session),
):
    admin = _admin_or_redirect(request, session)
    if admin is None:
        return _LOGIN
    if session.exec(select(User).where(User.username == username)).first() is not None:
        return templates.TemplateResponse(
            request,
            "admin_user_new.html",
            {"user": admin, "error": f"Username already exists: {username}"},
            status_code=409,
        )
    create_user(
        session,
        username=username,
        password=password,
        display_name=display_name,
        is_admin=(kind == "admin"),
        is_ai=(kind == "ai"),
        must_change_password=True,
    )
    return RedirectResponse("/ui/admin/users", 303)


@accounts.post("/ui/admin/users/{username}/deactivate")
def deactivate_user(username: str, request: Request, session: Session = Depends(get_session)):
    admin = _admin_or_redirect(request, session)
    if admin is None:
        return _LOGIN
    user = _user_or_404(session, username)
    if user.id == admin.id:
        raise HTTPException(status_code=409, detail="you cannot deactivate your own account")
    user.is_active = False
    session.add(user)
    session.flush()
    return RedirectResponse("/ui/admin/users", 303)


@accounts.post("/ui/admin/users/{username}/activate")
def activate_user(username: str, request: Request, session: Session = Depends(get_session)):
    admin = _admin_or_redirect(request, session)
    if admin is None:
        return _LOGIN
    user = _user_or_404(session, username)
    user.is_active = True
    session.add(user)
    session.flush()
    return RedirectResponse("/ui/admin/users", 303)


@accounts.post("/ui/admin/users/{username}/reset-password")
def reset_password(
    username: str,
    request: Request,
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    admin = _admin_or_redirect(request, session)
    if admin is None:
        return _LOGIN
    user = _user_or_404(session, username)
    set_password(session, user, password)
    user.must_change_password = True  # force a change on next login
    session.add(user)
    session.flush()
    return RedirectResponse("/ui/admin/users", 303)


# --------------------------------------------------------------------------- #
# per-review role assignment (owner or admin)
# --------------------------------------------------------------------------- #


def _can_manage_members(session: Session, review, user: User) -> bool:
    return user.is_admin or authz.review_role(session, review, user) == Role.OWNER.value


def _is_primary_owner(review, account: User) -> bool:
    """The user carried by ``Review.owner_id`` — the owner that drives
    disposition attribution and must never be demoted/removed (a review always
    keeps at least this owner; ownership transfer is a separate, future action)."""
    return review.owner_id is not None and review.owner_id == account.id


@accounts.get("/ui/reviews/{review_id}/members", response_class=HTMLResponse)
def members_page(review_id: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not _can_manage_members(session, review, user):
        raise HTTPException(status_code=403, detail="only the owner or an admin may manage members")
    members = ReviewRepo(session).members(review)
    return templates.TemplateResponse(
        request, "members.html", {"user": user, "review": review, "members": members}
    )


@accounts.post("/ui/reviews/{review_id}/members")
def members_submit(
    review_id: str,
    request: Request,
    username: str = Form(...),
    role: str = Form(...),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not _can_manage_members(session, review, user):
        raise HTTPException(status_code=403, detail="only the owner or an admin may manage members")
    if role not in _ROLE_VALUES:
        raise HTTPException(status_code=422, detail="role must be owner, reviewer, or moderator")
    # Assign an EXISTING account by its stable username (no get_or_create: a typo
    # must never spawn a phantom user). Account creation stays in the admin area.
    account = session.exec(select(User).where(User.username == username)).first()
    if account is None or not account.is_active:
        raise HTTPException(status_code=422, detail=f"unknown or inactive account: {username!r}")
    if _is_primary_owner(review, account) and role != Role.OWNER.value:
        raise HTTPException(
            status_code=409, detail="the primary owner cannot be demoted; transfer ownership first"
        )
    ReviewRepo(session).set_member_role(review, account, role)
    return RedirectResponse(f"/ui/reviews/{review_id}/members", 303)


@accounts.get("/ui/reviews/{review_id}/members/search", response_class=HTMLResponse)
def members_search(
    review_id: str, request: Request, q: str = "", session: Session = Depends(get_session)
):
    """HTMX typeahead: existing **active** accounts not already on the review,
    matched case-insensitively on username / display name."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not _can_manage_members(session, review, user):
        raise HTTPException(status_code=403, detail="only the owner or an admin may manage members")
    member_ids = {m.user_id for m in ReviewRepo(session).members(review)}
    needle = q.strip().lower()
    everyone = session.exec(select(User).order_by(User.display_name)).all()
    candidates = [
        u
        for u in everyone
        if u.is_active
        and u.id not in member_ids
        and (not needle or needle in u.username.lower() or needle in u.display_name.lower())
    ][:20]
    return templates.TemplateResponse(
        request, "members_candidates.html", {"candidates": candidates}
    )


@accounts.post("/ui/reviews/{review_id}/members/{username}/remove")
def member_remove(
    review_id: str, username: str, request: Request, session: Session = Depends(get_session)
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not _can_manage_members(session, review, user):
        raise HTTPException(status_code=403, detail="only the owner or an admin may manage members")
    account = _user_or_404(session, username)
    if _is_primary_owner(review, account):
        raise HTTPException(
            status_code=409, detail="the primary owner cannot be removed; transfer ownership first"
        )
    ReviewRepo(session).remove_member(review, account)
    return RedirectResponse(f"/ui/reviews/{review_id}/members", 303)
