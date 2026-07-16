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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from malus import services as svc
from malus.api import authz
from malus.api.deps import get_session
from malus.auth.service import authenticate
from malus.constants import Disposition, Role, Status
from malus.db.models import User
from malus.harvest import FreezeViolation, validate_insertion_only
from malus.parser import ParseError
from malus.repo import ReviewerCopyRepo, ReviewerNoteRepo, ReviewRepo, RidRepo, VersionRepo

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
    request.session["must_change_password"] = user.must_change_password
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
    rows = []
    for r in ReviewRepo(session).list():
        role = authz.review_role(session, r, user)
        to_comment = False
        if role == Role.REVIEWER.value:  # flag reviews awaiting *my* comment
            mine = next(
                (c for c in ReviewerCopyRepo(session).list(r) if c.user_id == user.id), None
            )
            to_comment = mine is None or mine.submitted_at is None
        rows.append({"review": r, "role": role, "to_comment": to_comment})
    return templates.TemplateResponse(request, "reviews.html", {"user": user, "rows": rows})


@web.get("/ui/reviews/new", response_class=HTMLResponse)
def new_review_page(request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    return templates.TemplateResponse(request, "new_review.html", {"user": user, "error": None})


@web.post("/ui/reviews/new")
def new_review_submit(
    request: Request,
    review_id: str = Form(...),
    baseline: str = Form(...),
    title: str = Form(""),
    rid_prefix: str = Form(""),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review_id = review_id.strip()
    if not review_id:
        return templates.TemplateResponse(
            request, "new_review.html", {"user": user, "error": "A review id is required."}, status_code=422
        )
    if ReviewRepo(session).get(review_id) is not None:
        return templates.TemplateResponse(
            request,
            "new_review.html",
            {"user": user, "error": f"A review with id {review_id!r} already exists."},
            status_code=409,
        )
    # the creator becomes the owner; freeze the supplied baseline immediately
    review = svc.create_review(
        session,
        review_id=review_id,
        document_name="baseline.md",
        owner=user.display_name,
        reviewers=[],
        title=title or None,
        rid_prefix=rid_prefix or None,
    )
    svc.freeze_baseline(session, review, baseline, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


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

    # v1.6: reviewer submission panel (soft indicator — blocks nothing)
    copies_by_uid = {c.user_id: c for c in ReviewerCopyRepo(session).list(review)}
    submissions = []
    for m in ReviewRepo(session).members(review):
        if m.role != Role.REVIEWER.value:
            continue
        copy = copies_by_uid.get(m.user_id)
        state = "submitted" if (copy and copy.submitted_at) else ("draft" if copy else "not started")
        submissions.append({"name": m.user.display_name, "state": state})
    subm_total = len(submissions)
    subm_done = sum(1 for s in submissions if s["state"] == "submitted")
    ai_proposals = sum(1 for r in rtd.rids if r.ai_drafted and r.status is Status.OPEN)

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
            "submissions": submissions,
            "subm_done": subm_done,
            "subm_total": subm_total,
            "all_submitted": subm_total > 0 and subm_done == subm_total,
            "ai_proposals": ai_proposals,
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
            "can_dispose": role == Role.OWNER.value and not user.is_ai,
            "can_verify": _can_verify(role, user, dto.reviewer),
            "ai_proposal": dto.ai_drafted and dto.status is Status.OPEN,
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


@web.post("/ui/reviews/{review_id}/rids/{rid}/discard-draft")
def discard_draft(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    """Discard an AI-drafted proposal back to a plain OPEN finding (v1.7).
    Owner-only; an AI principal (which only ever drafts) is refused."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    if user.is_ai:
        raise HTTPException(status_code=403, detail="AI principals cannot confirm or discard drafts")
    if RidRepo(session).get(review, rid) is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    svc.discard_disposition_draft(session, review, rid, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}/rids/{rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/retract")
def retract_comment(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    """A reviewer retracts their OWN comment: it is removed from their copy and,
    if pristine (never disposed), hard-deleted. Reviewer-only, own, OPEN only."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    role = authz.review_role(session, review, user)
    if role != Role.REVIEWER.value or row.reviewer_id != user.id:
        raise HTTPException(status_code=403, detail="you may only retract your own comment")
    if row.status != Status.OPEN.value:
        raise HTTPException(status_code=409, detail="only an open comment can be retracted")
    svc.retract_comment(session, review, rid, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


# --------------------------------------------------------------------------- #
# editor: reviewer copy (Step 6) and owner implementation
# --------------------------------------------------------------------------- #


def _own_copy(session: Session, review, user: User):
    """The current user's reviewer-copy row for this review, or None."""
    return next(
        (c for c in ReviewerCopyRepo(session).list(review) if c.user_id == user.id), None
    )


@web.get("/ui/reviews/{review_id}/edit-copy", response_class=HTMLResponse)
def edit_copy_page(
    review_id: str,
    request: Request,
    saved: bool = False,
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) != Role.REVIEWER.value:
        raise HTTPException(status_code=403, detail="only a reviewer may edit a review copy")
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    mine = _own_copy(session, review, user)
    content = (mine.content if mine else None) or baseline.content
    return templates.TemplateResponse(
        request,
        "edit_copy.html",
        {
            "user": user,
            "review": review,
            "content": content,
            "baseline": baseline.content,
            "error": None,
            "saved": saved,
            "copy": mine,
        },
    )


@web.post("/ui/reviews/{review_id}/edit-copy", response_class=HTMLResponse)
def submit_copy(
    review_id: str,
    request: Request,
    content: str = Form(...),
    action: str = Form("submit"),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) != Role.REVIEWER.value:
        raise HTTPException(status_code=403, detail="only a reviewer may edit a review copy")
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    try:  # server-side freeze-rule check (authoritative) — for Save and Submit
        validate_insertion_only(baseline.content, content)
    except (FreezeViolation, ParseError) as exc:
        return templates.TemplateResponse(
            request,
            "edit_copy.html",
            {
                "user": user,
                "review": review,
                "content": content,
                "baseline": baseline.content,
                "error": f"Rejected — freeze rule / parse: {exc}",
            },
            status_code=422,
        )
    submit = action == "submit"
    svc.add_reviewer_copy(session, review, user.display_name, content, submitted=submit)
    svc.harvest(session, review, by=user)  # Save or Submit re-harvests → comments show in the table
    if submit:
        return RedirectResponse(f"/ui/reviews/{review_id}", 303)
    return RedirectResponse(f"/ui/reviews/{review_id}/edit-copy?saved=1", 303)


def _require_reviewer(session: Session, request: Request, review_id: str):
    """(user, review) for a reviewer of the review, or a redirect/403."""
    user = _current(request, session)
    if not user:
        return None, None, _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) != Role.REVIEWER.value:
        raise HTTPException(status_code=403, detail="only a reviewer has private notes here")
    return user, review, None


@web.get("/ui/reviews/{review_id}/my-notes")
def my_notes(review_id: str, request: Request, session: Session = Depends(get_session)):
    """The current reviewer's private notes for this review: {anchor_key: body}."""
    user, review, redirect = _require_reviewer(session, request, review_id)
    if redirect is not None:
        return redirect
    return JSONResponse(ReviewerNoteRepo(session).map_for(review, user))


@web.put("/ui/reviews/{review_id}/my-notes")
def save_my_note(
    review_id: str,
    request: Request,
    anchor_key: str = Form(...),
    body: str = Form(""),
    session: Session = Depends(get_session),
):
    """Upsert one private note (empty body clears it). Scoped to the reviewer."""
    user, review, redirect = _require_reviewer(session, request, review_id)
    if redirect is not None:
        return redirect
    ReviewerNoteRepo(session).upsert(review, user, anchor_key, body)
    return Response(status_code=204)


def _can_delete_review(session: Session, review, user: User) -> bool:
    return user.is_admin or authz.review_role(session, review, user) == Role.OWNER.value


@web.get("/ui/reviews/{review_id}/delete", response_class=HTMLResponse)
def delete_review_page(review_id: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not _can_delete_review(session, review, user):
        raise HTTPException(status_code=403, detail="only the owner or an admin may delete a review")
    return templates.TemplateResponse(
        request,
        "review_delete.html",
        {
            "user": user,
            "review": review,
            "findings": len(RidRepo(session).list(review)),
            "members": ReviewRepo(session).members(review),
        },
    )


@web.post("/ui/reviews/{review_id}/delete")
def delete_review_submit(review_id: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not _can_delete_review(session, review, user):
        raise HTTPException(status_code=403, detail="only the owner or an admin may delete a review")
    svc.delete_review(session, review, by=user)
    return RedirectResponse("/ui/reviews", 303)


@web.get("/ui/reviews/{review_id}/implement", response_class=HTMLResponse)
def implement_page(review_id: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    latest = VersionRepo(session).latest(review)
    accepted = [
        r
        for r in svc.export(session, review).rids
        if r.disposition is Disposition.ACCEPTED and r.status is Status.ANSWERED
    ]
    return templates.TemplateResponse(
        request,
        "implement.html",
        {
            "user": user,
            "review": review,
            "content": latest.content if latest else "",
            "accepted": accepted,
            "error": None,
        },
    )


@web.post("/ui/reviews/{review_id}/implement")
def implement_submit(
    review_id: str,
    request: Request,
    content: str = Form(...),
    rids: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    version = svc.save_version(session, review, content, by=user)
    for rid in rids:
        if RidRepo(session).get(review, rid) is None:
            continue
        svc.link_change(session, review, rid, version, by=user)
        try:  # advance accepted+answered RIDs now that a change links them
            svc.implement(session, review, rid, by=user)
        except ValueError:
            pass  # not eligible to advance (wrong disposition/status) — leave as-is
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)
