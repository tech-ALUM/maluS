"""Server-rendered GUI routes.

Plain HTML forms (so the flow works with JavaScript disabled) with `hx-boost`
progressive enhancement. Pages read via the services and render Jinja; every
mutation goes through the same services + authorization as the API — the GUI
holds no authority the server does not also enforce (e.g. the owner is never
shown a verify control, and the server rejects it even if forged).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from malus import services as svc
from malus.api import authz
from malus.api.deps import get_session
from malus.auth.service import authenticate
from malus.constants import Disposition, Role, Status
from malus.db.models import User
from malus.repo import ReviewRepo, RidRepo

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
web = APIRouter(include_in_schema=False)

_LOGIN = RedirectResponse("/ui/login", status_code=303)


def _current(request: Request, session: Session) -> Optional[User]:
    uid = request.session.get("user_id")
    if uid is None:
        return None
    user = session.get(User, uid)
    return user if (user is not None and user.is_active) else None


def _review_or_404(session: Session, review_id: str):
    review = ReviewRepo(session).get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"no such review: {review_id}")
    return review


def _can_verify(role: Optional[str], user: User, reviewer_name: str) -> bool:
    if user.is_ai:
        return False
    if role == Role.MODERATOR.value:
        return True
    return role == Role.REVIEWER.value and reviewer_name == user.display_name


# --------------------------------------------------------------------------- #
# auth pages
# --------------------------------------------------------------------------- #


@web.get("/", response_class=HTMLResponse)
def root(request: Request, session: Session = Depends(get_session)):
    return RedirectResponse("/ui/reviews" if _current(request, session) else "/ui/login", 303)


@web.get("/ui/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)):
    if _current(request, session):
        return RedirectResponse("/ui/reviews", 303)
    return templates.TemplateResponse(request, "login.html", {"user": None, "error": None})


@web.post("/ui/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = authenticate(session, username, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": "Invalid username or password."},
            status_code=401,
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/ui/reviews", 303)


@web.post("/ui/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/ui/login", 303)


# --------------------------------------------------------------------------- #
# review list, dashboard + RTD table, finding detail
# --------------------------------------------------------------------------- #


@web.get("/ui/reviews", response_class=HTMLResponse)
def reviews_page(request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    rows = [
        {"review": r, "role": authz.review_role(session, r, user)}
        for r in ReviewRepo(session).list()
    ]
    return templates.TemplateResponse(request, "reviews.html", {"user": user, "rows": rows})


@web.get("/ui/reviews/{review_id}", response_class=HTMLResponse)
def review_page(
    review_id: str,
    request: Request,
    session: Session = Depends(get_session),
    status: Optional[str] = None,
    reviewer: Optional[str] = None,
    type: Optional[str] = None,
    severity: Optional[str] = None,
    disposition: Optional[str] = None,
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    role = authz.review_role(session, review, user)
    rtd = svc.export(session, review)

    filters = {
        "status": status,
        "reviewer": reviewer,
        "type": type,
        "severity": severity,
        "disposition": disposition,
    }

    def keep(r) -> bool:
        return (
            (not status or r.status.value == status)
            and (not reviewer or r.reviewer == reviewer)
            and (not type or (r.type.value if r.type else "") == type)
            and (not severity or (r.severity.value if r.severity else "") == severity)
            and (not disposition or (r.disposition.value if r.disposition else "") == disposition)
        )

    rids = [r for r in rtd.rids if keep(r)]
    counts_status = {s.value: sum(1 for r in rtd.rids if r.status is s) for s in Status}
    closed = counts_status[Status.VERIFIED.value] + counts_status[Status.WITHDRAWN.value]
    total = len(rtd.rids)
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "user": user,
            "review": review,
            "role": role,
            "owner": rtd.meta.owner,
            "reviewers": rtd.meta.reviewers,
            "rids": rids,
            "counts_status": counts_status,
            "closed": closed,
            "total": total,
            "progress": round(100 * closed / total) if total else 0,
            "filters": filters,
            "reviewer_names": rtd.meta.reviewers,
        },
    )


@web.get("/ui/reviews/{review_id}/rids/{rid}", response_class=HTMLResponse)
def finding_page(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    role = authz.review_role(session, review, user)
    dto = next((r for r in svc.export(session, review).rids if r.rid == rid), None)
    if dto is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    return templates.TemplateResponse(
        request,
        "finding.html",
        {
            "user": user,
            "review": review,
            "r": dto,
            "role": role,
            "can_dispose": role == Role.OWNER.value,
            "can_verify": _can_verify(role, user, dto.reviewer),
        },
    )


# --------------------------------------------------------------------------- #
# mutations (same services + authorization as the API)
# --------------------------------------------------------------------------- #


@web.post("/ui/reviews/{review_id}/rids/{rid}/dispose")
def dispose(
    review_id: str,
    rid: str,
    request: Request,
    disposition: str = Form(...),
    reply: str = Form(""),
    resolution: str = Form(""),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    try:
        disp = Disposition(disposition)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid disposition: {disposition!r}")
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    if row.status == Status.OPEN.value:
        svc.answer(session, review, rid, disposition=disp, reply=reply or None, by=user)
        if resolution:
            svc.update_rid(session, review, rid, resolution=resolution, by=user)
    else:
        svc.update_rid(
            session, review, rid, reply=reply or None, resolution=resolution or None,
            disposition=disp, by=user,
        )
    return RedirectResponse(f"/ui/reviews/{review_id}/rids/{rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/verify")
def verify_action(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    on_behalf = authz.require_verify(session, review, user, row)
    svc.verify(session, review, rid, reviewer=user.display_name, moderator=on_behalf, on=dt.date.today())
    return RedirectResponse(f"/ui/reviews/{review_id}/rids/{rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/reopen")
def reopen_action(
    review_id: str,
    rid: str,
    request: Request,
    reason: str = Form(...),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    on_behalf = authz.require_verify(session, review, user, row)
    svc.reopen(session, review, rid, reviewer=user.display_name, reason=reason, moderator=on_behalf)
    return RedirectResponse(f"/ui/reviews/{review_id}/rids/{rid}", 303)
