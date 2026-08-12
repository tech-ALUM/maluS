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

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from malus import __version__ as malus_version
from malus import services as svc
from malus.api import authz
from malus.api.deps import get_session
from malus.auth import throttle
from malus.auth.service import authenticate
from malus.constants import Disposition, Role, Status
from malus.db.models import ReviewStatus, User
from malus.diffing import html_diff
from malus.harvest import FreezeViolation, WithdrawViolation, build_rtd, validate_insertion_only
from malus.parser import ParseError
from malus.repo import (
    ArtifactRepo,
    AuditRepo,
    ReviewerCopyRepo,
    ReviewerNoteRepo,
    ReviewRepo,
    RidRepo,
    UserRepo,
    VersionRepo,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
# cache-busting version for asset URLs (?v=...) — see RevalidatedStaticFiles
templates.env.globals["asset_v"] = malus_version
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
    if user.is_admin:  # global admin superuser (v1.10)
        return True
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
    # The form renders its own 429 rather than the JSON error handler, so a
    # throttled human sees the login page with an explanation (ADR 0005).
    try:
        throttle.check(request, username)
    except throttle.TooManyAttempts as exc:
        minutes = max(1, round(exc.retry_after / 60))
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "user": None,
                "error": f"Too many failed attempts. Try again in about {minutes} minute(s).",
            },
            status_code=429,
            headers={"Retry-After": str(exc.retry_after)},
        )
    user = authenticate(session, username, password)
    throttle.record(request, username, ok=user is not None)
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
    reviews = ReviewRepo(session)
    copies = ReviewerCopyRepo(session)
    pdf_ids = ArtifactRepo(session).review_ids_with("pdf")  # one query for the page
    rows = []
    for r in reviews.list():
        role = authz.review_role(session, r, user)
        to_comment = False
        if role == Role.REVIEWER.value:  # flag reviews awaiting *my* comment
            mine = next((c for c in copies.list(r) if c.user_id == user.id), None)
            to_comment = mine is None or mine.submitted_at is None
        rows.append(
            {
                "review": r,
                "role": role,
                "to_comment": to_comment,
                "status": r.status,
                "has_pdf": r.id in pdf_ids,
            }
        )
    return templates.TemplateResponse(request, "reviews.html", {"user": user, "rows": rows})


@web.get("/ui/reviews/new", response_class=HTMLResponse)
def new_review_page(request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    return templates.TemplateResponse(request, "new_review.html", {"user": user, "error": None})


_BASELINE_MAX_BYTES = 2 * 1024 * 1024  # 2 MB — plenty for a Markdown DUR


@web.post("/ui/reviews/new")
async def new_review_submit(
    request: Request,
    review_id: str = Form(...),
    baseline: UploadFile = File(...),
    title: str = Form(""),
    rid_prefix: str = Form(""),
    session: Session = Depends(get_session),
):
    """Create a review from an uploaded Markdown baseline (v2.1 — the paste
    textarea is gone). The JSON API ``POST /reviews`` is unchanged."""
    user = _current(request, session)
    if not user:
        return _LOGIN

    def _fail(message: str, status: int = 422):
        return templates.TemplateResponse(
            request, "new_review.html", {"user": user, "error": message}, status_code=status
        )

    review_id = review_id.strip()
    if not review_id:
        return _fail("A review id is required.")
    filename = baseline.filename or ""
    if not filename.lower().endswith((".md", ".markdown")):
        return _fail("The baseline must be a Markdown file (.md or .markdown).")
    raw = await baseline.read()
    if len(raw) > _BASELINE_MAX_BYTES:
        return _fail("The baseline file exceeds 2 MB.")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _fail("The baseline file is not valid UTF-8 text.")
    if ReviewRepo(session).get(review_id) is not None:
        return _fail(f"A review with id {review_id!r} already exists.", status=409)
    # the creator becomes the owner; freeze the uploaded baseline immediately
    review = svc.create_review(
        session,
        review_id=review_id,
        document_name="baseline.md",
        owner=user.display_name,
        reviewers=[],
        title=title.strip() or Path(filename).stem or None,
        rid_prefix=rid_prefix or None,
    )
    svc.freeze_baseline(session, review, content, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


_FACET_VALUES = {
    "status": ["open", "answered", "closed", "implemented", "verified", "withdrawn"],
    "type": ["typo", "editorial", "technical", "process"],
    "severity": ["minor", "major", "critical"],
    "disposition": ["accepted", "rejected", "deferred"],
    "draft": ["yes", "no"],  # v3: comment from a not-yet-submitted copy
}
_ENUM_FACETS = ("status", "reviewer", "type", "severity", "disposition", "draft")


def _draft_reviewers(session: Session, review) -> set[str]:
    """Reviewers whose current copy exists but is not submitted (v3): their
    findings render as drafts and cannot be disposed yet."""
    copies_by_uid = {c.user_id: c for c in ReviewerCopyRepo(session).list(review)}
    out: set[str] = set()
    for m in ReviewRepo(session).members(review):
        if m.role != Role.REVIEWER.value:
            continue
        copy = copies_by_uid.get(m.user_id)
        if copy is not None and copy.submitted_at is None:
            out.add(m.user.display_name)
    return out
_OP_LABELS = {"eq": "=", "ne": "≠", "contains": "contains"}


def _parse_conditions(raw: list[str]) -> list[tuple[str, str, str]]:
    """Parse `facet:op:value` filter conditions (v2.3); malformed → ignored.
    `comment` accepts only `contains` (any sent op is coerced to it)."""
    out: list[tuple[str, str, str]] = []
    for item in raw:
        parts = item.split(":", 2)
        if len(parts) != 3:
            continue
        facet, op, value = parts
        if not value:
            continue
        if facet == "comment":
            out.append((facet, "contains", value))
        elif facet in _ENUM_FACETS and op in ("eq", "ne"):
            out.append((facet, op, value))
    return out


def _conditions_qs(conds: list[tuple[str, str, str]]) -> str:
    return "?" + urlencode([("f", f"{facet}:{op}:{value}") for facet, op, value in conds]) if conds else "?"


@web.get("/ui/reviews/{review_id}", response_class=HTMLResponse)
def review_page(
    review_id: str,
    request: Request,
    session: Session = Depends(get_session),
    f: list[str] = Query(default=[]),
    facet: str = "",
    op: str = "eq",
    value: str = "",
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)

    conds = _parse_conditions(f)
    if facet and value:  # builder submit: fold into the canonical ?f= URL
        new = _parse_conditions([f"{facet}:{op}:{value}"])
        for cond in new:
            if cond not in conds:
                conds.append(cond)
        return RedirectResponse(
            f"/ui/reviews/{review_id}{_conditions_qs(conds)}", 303
        )

    role = authz.review_role(session, review, user)
    rtd = svc.export(session, review)

    eq_sets: dict[str, set[str]] = {}
    ne_sets: dict[str, set[str]] = {}
    contains: list[str] = []
    for cfacet, cop, cvalue in conds:
        if cop == "contains":
            contains.append(cvalue.lower())
        elif cop == "eq":
            eq_sets.setdefault(cfacet, set()).add(cvalue)
        else:
            ne_sets.setdefault(cfacet, set()).add(cvalue)

    draft_names = _draft_reviewers(session, review)

    def _facet_value(r, cfacet: str) -> str:
        if cfacet == "status":
            return r.status.value
        if cfacet == "reviewer":
            return r.reviewer
        if cfacet == "type":
            return r.type.value if r.type else ""
        if cfacet == "severity":
            return r.severity.value if r.severity else ""
        if cfacet == "draft":
            return "yes" if r.reviewer in draft_names else "no"
        return r.disposition.value if r.disposition else ""

    def keep(r) -> bool:
        if r.status is Status.WITHDRAWN and "withdrawn" not in eq_sets.get("status", set()):
            return False  # hidden unless explicitly selected (v2.2 rule)
        for cfacet in _ENUM_FACETS:
            v = _facet_value(r, cfacet)
            if cfacet in eq_sets and v not in eq_sets[cfacet]:
                return False
            if v in ne_sets.get(cfacet, ()):
                return False
        text = (r.comment or "").lower()
        return all(sub in text for sub in contains)

    rids = [r for r in rtd.rids if keep(r)]
    tokens = [
        {
            "facet": cfacet,
            "op": _OP_LABELS[cop],
            "value": cvalue,
            "remove_href": _conditions_qs([c for c in conds if c != (cfacet, cop, cvalue)]),
        }
        for cfacet, cop, cvalue in conds
    ]
    filter_options = dict(_FACET_VALUES, reviewer=rtd.meta.reviewers)
    counts_status = {s.value: sum(1 for r in rtd.rids if r.status is s) for s in Status}
    closed = (
        counts_status[Status.CLOSED.value]
        + counts_status[Status.VERIFIED.value]
        + counts_status[Status.WITHDRAWN.value]
    )
    total = len(rtd.rids)
    phase = review.status
    closeout_errors = svc.closeout_gate(session, review) if phase == ReviewStatus.IN_REVIEW.value else []
    finalize_ready = (
        phase == ReviewStatus.CLOSEOUT.value and not svc.finalize_gate(session, review)
    )
    has_pdf = (
        phase == ReviewStatus.FINALIZED.value
        and ArtifactRepo(session).get(review, "pdf") is not None
    )

    # v1.6: reviewer submission panel (soft indicator — blocks nothing)
    copies_by_uid = {c.user_id: c for c in ReviewerCopyRepo(session).list(review)}
    submissions = []
    for m in ReviewRepo(session).members(review):
        if m.role != Role.REVIEWER.value:
            continue
        copy = copies_by_uid.get(m.user_id)
        state = "submitted" if (copy and copy.submitted_at) else ("draft" if copy else "not started")
        submissions.append(
            {
                "name": m.user.display_name,
                "state": state,
                "reopen_requested": bool(copy and copy.submitted_at and copy.reopen_requested_at),
            }
        )
    subm_total = len(submissions)
    subm_done = sum(1 for s in submissions if s["state"] == "submitted")
    ai_proposals = sum(1 for r in rtd.rids if r.ai_drafted and r.status is Status.OPEN)
    draft_rids = {
        r.rid
        for r in rtd.rids
        if r.reviewer in draft_names and r.status is not Status.WITHDRAWN
    }

    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "draft_rids": draft_rids,
            "draft_count": len(draft_rids),
            "user": user,
            "review": review,
            "role": role,
            "owner": rtd.meta.owner,
            "reviewers": rtd.meta.reviewers,
            "colors": _reviewer_colors(session, review, rtd.meta.reviewers),
            "rids": rids,
            "counts_status": counts_status,
            "closed": closed,
            "total": total,
            "progress": round(100 * closed / total) if total else 0,
            "tokens": tokens,
            "filter_options": filter_options,
            "reviewer_names": rtd.meta.reviewers,
            "submissions": submissions,
            "subm_done": subm_done,
            "subm_total": subm_total,
            "all_submitted": subm_total > 0 and subm_done == subm_total,
            "ai_proposals": ai_proposals,
            "phase": phase,
            "closeout_errors": closeout_errors,
            "finalize_ready": finalize_ready,
            "has_pdf": has_pdf,
        },
    )


@web.get("/ui/reviews/{review_id}/rids/{rid}")
def finding_page(review_id: str, rid: str):
    """The standalone finding page is superseded by the viewer's focus mode
    (v2 step 5): the document is always shown beside the comment."""
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


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
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


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
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


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
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/accept")
def accept_action(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    """The RID's own reviewer (or a moderator on their behalf) accepts the
    owner's disposition (v3): ``answered -> closed``, in_review only."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    on_behalf = authz.require_verify(session, review, user, row)
    svc.accept_disposition(session, review, rid, reviewer=user.display_name, moderator=on_behalf)
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/request-changes")
def request_changes_action(
    review_id: str,
    rid: str,
    request: Request,
    reason: str = Form(...),
    session: Session = Depends(get_session),
):
    """The RID's own reviewer (or a moderator on their behalf) sends an
    implemented/verified RID back for rework (v3): ``-> closed``, closeout only."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    on_behalf = authz.require_verify(session, review, user, row)
    svc.request_changes(
        session, review, rid, reviewer=user.display_name, reason=reason, moderator=on_behalf
    )
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


@web.post("/ui/reviews/{review_id}/start-closeout")
def start_closeout_action(review_id: str, request: Request, session: Session = Depends(get_session)):
    """Owner-only (v3): ``in_review -> closeout``, gated on every finding
    being closed (or withdrawn) — see ``svc.closeout_gate``."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    authz.forbid_ai_commit(user)
    svc.start_closeout(session, review, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


@web.post("/ui/reviews/{review_id}/reopen-review")
def reopen_review_action(review_id: str, request: Request, session: Session = Depends(get_session)):
    """Admin escape hatch (v3): ``closeout -> in_review``. Reserved to a
    human global admin — not the owner, not a moderator, never an AI."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not (user.is_admin and not user.is_ai):
        raise HTTPException(
            status_code=403,
            detail="reopening a review from closeout is a human global-admin-only action",
        )
    svc.reopen_review(session, review, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


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
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/purge")
def purge_action(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    """PERMANENTLY remove a finding — human global admin only (v2.2)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not user.is_admin or user.is_ai:
        raise HTTPException(status_code=403, detail="only a human global admin may purge a comment")
    try:
        svc.purge_rid(session, review, rid, by=user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


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
    # an admin bypasses ownership, never status: v3 allows withdraw only from
    # 'open' (a disposed comment is reopened first, keeping its history)
    if not user.is_admin and (role != Role.REVIEWER.value or row.reviewer_id != user.id):
        raise HTTPException(status_code=403, detail="you may only retract your own comment")
    if row.status != Status.OPEN.value:
        raise HTTPException(status_code=409, detail="only an open comment can be retracted; reopen it first")
    svc.retract_comment(session, review, rid, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


@web.post("/ui/reviews/{review_id}/request-reopen")
def request_reopen(review_id: str, request: Request, session: Session = Depends(get_session)):
    """The reviewer asks to edit their submitted copy again (v3)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) != Role.REVIEWER.value:
        raise HTTPException(status_code=403, detail="only a reviewer may request a reopen")
    svc.request_copy_reopen(session, review, user.display_name, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}/document", 303)


@web.post("/ui/reviews/{review_id}/approve-reopen/{reviewer}")
def approve_reopen(review_id: str, reviewer: str, request: Request, session: Session = Depends(get_session)):
    """The owner (or an admin) approves a pending reopen request (v3)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not user.is_admin and authz.review_role(session, review, user) != Role.OWNER.value:
        raise HTTPException(status_code=403, detail="only the owner or an admin may approve a reopen")
    svc.approve_copy_reopen(session, review, reviewer, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


@web.post("/ui/reviews/{review_id}/reopen-submission/{reviewer}")
def reopen_submission(review_id: str, reviewer: str, request: Request, session: Session = Depends(get_session)):
    """Admin superuser: un-submit a reviewer's copy (submitted_at → None) so they
    can edit and resubmit (v1.10)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="only an admin may re-open a submission")
    try:
        svc.reopen_submission(session, review, reviewer, by=user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


# --------------------------------------------------------------------------- #
# editor: reviewer copy (Step 6) and owner implementation
# --------------------------------------------------------------------------- #


def _own_copy(session: Session, review, user: User):
    """The current user's reviewer-copy row for this review, or None."""
    return next(
        (c for c in ReviewerCopyRepo(session).list(review) if c.user_id == user.id), None
    )


def _reviewer_colors(session: Session, review, reviewer_names: list[str]) -> dict:
    """Resolved comment color per reviewer (v2.1): the review-member override
    wins over the user's global default; ``None`` means the client falls back
    to the deterministic palette."""
    members = {m.user.display_name: m for m in ReviewRepo(session).members(review) if m.user}
    colors: dict[str, Optional[str]] = {}
    for name in reviewer_names:
        member = members.get(name)
        if member is not None:
            colors[name] = member.color or (member.user.color if member.user else None)
        else:  # e.g. a removed member whose findings survive
            user = UserRepo(session).by_display_name(name)
            colors[name] = user.color if user else None
    return colors


def _document_context(
    session: Session,
    request: Request,
    user: User,
    review,
    *,
    saved: bool = False,
    error: Optional[str] = None,
    my_copy_override: Optional[str] = None,
    content_override: Optional[str] = None,
    focus: Optional[str] = None,
) -> dict:
    """Template context for the unified document viewer (v2 step 4).

    Any review member (or a global admin) may open it; capabilities are
    per-role flags the JS mirrors — the server keeps enforcing them on every
    mutation endpoint regardless."""
    role = authz.review_role(session, review, user)
    if role is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="only review members may open the document")
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    rtd = svc.export(session, review)
    is_reviewer = role == Role.REVIEWER.value
    draft_names = _draft_reviewers(session, review)
    mine = _own_copy(session, review, user) if is_reviewer else None
    my_copy = None
    if is_reviewer:
        my_copy = my_copy_override or (mine.content if mine and mine.content else None) or baseline.content
    rids = []
    for r in rtd.rids:
        if r.status is Status.WITHDRAWN and r.rid != focus:
            continue  # no longer in any copy — dashboard still lists it; keep it only when focused
        rids.append(
            {
                "rid": r.rid,
                "reviewer": r.reviewer,
                "kind": r.kind.value,
                "type": r.type.value if r.type else None,
                "severity": r.severity.value if r.severity else None,
                "status": r.status.value,
                "disposition": r.disposition.value if r.disposition else None,
                "comment": r.comment or "",
                "reply": r.reply or None,
                "resolution": r.resolution or None,
                "aiDrafted": bool(r.ai_drafted),
                "aiProposal": bool(r.ai_drafted and r.status is Status.OPEN),
                "draft": r.reviewer in draft_names,
                "offset": r.anchor.offset,
                "lineHint": r.anchor.line_hint,
                "section": r.anchor.section,
                "verifiedBy": r.verified_by,
                "verifiedOn": r.verified_on.isoformat() if r.verified_on else None,
                "canVerify": _can_verify(role, user, r.reviewer),
                "canRetract": user.is_admin
                or (is_reviewer and r.reviewer == user.display_name and r.status is Status.OPEN),
                "canPurge": user.is_admin and not user.is_ai,
                "mine": r.reviewer == user.display_name,
            }
        )
    # v2.1: resolved reviewer colors — review override → global default → null
    colors = _reviewer_colors(session, review, rtd.meta.reviewers)

    # v2.1: append-only per-RID history from the audit log (one grouped query)
    audit_rows = AuditRepo(session).for_targets([f"rid:{r['rid']}" for r in rids])
    history: dict[str, list[dict]] = {}
    for row in audit_rows:
        history.setdefault(row.target, []).append(
            {
                "action": row.action,
                "actor": row.actor.display_name if row.actor else None,
                "ts": row.ts.isoformat(timespec="seconds"),
                "detail": row.detail_json or {},
            }
        )
    for r in rids:
        r["history"] = history.get(f"rid:{r['rid']}", [])

    # v3 step 03 task 2: an accepted RID's post-baseline saves, rendered as
    # diffs — only once the document has left active review (closeout or
    # finalized), and only for findings the owner's disposition accepted
    closeout_phases = (ReviewStatus.CLOSEOUT.value, ReviewStatus.FINALIZED.value)
    for r in rids:
        show_changes = (
            review.status in closeout_phases and r["disposition"] == Disposition.ACCEPTED.value
        )
        if show_changes:
            r["changes"] = [
                {
                    "ordinal": c["ordinal"],
                    "created": c["created"],
                    "note": c["note"],
                    "diffHtml": c["diff_html"],
                }
                for c in svc.rid_changes(session, review, r["rid"])
            ]
        else:
            r["changes"] = []

    # v3.1 step 01: the closeout work queue rides in the viewer payload — the
    # side panel replaces the flat comment list with it (the standalone
    # workspace page is gone). Grouping lifted verbatim from the v3 workspace
    # context (retired in task 6) so the buckets could not drift apart.
    is_closeout = review.status == ReviewStatus.CLOSEOUT.value
    latest = VersionRepo(session).latest(review)
    for r in rids:
        group = None
        if r["disposition"] in (Disposition.REJECTED.value, Disposition.DEFERRED.value):
            group = "noChange"
        elif r["disposition"] == Disposition.ACCEPTED.value:
            reworked = "[changes requested by" in (r["reply"] or "")
            if r["status"] == Status.CLOSED.value:
                group = "rework" if reworked else "todo"
            elif r["status"] == Status.IMPLEMENTED.value:
                group = "awaiting"
            elif r["status"] == Status.VERIFIED.value:
                group = "done"
        r["queue"] = group if is_closeout else None
        r["hasChange"] = (
            is_closeout
            and r["disposition"] == Disposition.ACCEPTED.value
            and svc.rid_has_change(session, review, r["rid"])
        )

    data = {
        "reviewId": review.review_id_str,
        "phase": review.status,
        "role": role,
        "isAdmin": user.is_admin,
        "isReviewer": is_reviewer,
        "canDispose": (role == Role.OWNER.value or user.is_admin) and not user.is_ai,
        "me": user.display_name,
        "baseline": baseline.content,
        # a rejected closeout save re-renders the page with the unsaved text
        # (v3.1 step 01 task 6 — the workspace's own re-render, moved here)
        "latest": content_override
        if content_override is not None
        else (latest.content if latest else baseline.content),
        "latestOrdinal": latest.ordinal if latest else baseline.ordinal,
        "canEditDoc": is_closeout
        and (role == Role.OWNER.value or user.is_admin)
        and not user.is_ai,
        "myCopy": my_copy,
        "mySubmitted": bool(mine and mine.submitted_at) if is_reviewer else False,
        "myReopenRequested": bool(mine and mine.reopen_requested_at) if is_reviewer else False,
        "reviewers": rtd.meta.reviewers,
        "colors": colors,
        "rids": rids,
        "saved": bool(saved),
        "focus": focus,
    }
    # v3.1 step 02 task 5: Terminate rides in the closeout toolbar once the gate
    # holds. A Jinja-only flag — deliberately *not* in ``data``, so the
    # ``#viewer-data`` payload and its snapshot assertions stay untouched.
    finalize_ready = is_closeout and not svc.finalize_gate(session, review)
    return {
        "user": user,
        "review": review,
        "role": role,
        "data": data,
        "error": error,
        "finalize_ready": finalize_ready,
    }


@web.get("/ui/reviews/{review_id}/document", response_class=HTMLResponse)
def document_page(
    review_id: str,
    request: Request,
    saved: bool = False,
    focus: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """The unified document viewer: every role, one page (v2 step 4).
    ``?focus=<RID>`` opens it in focus mode — scrolled to the finding, its
    card expanded — so a comment is never shown without the document (v2
    step 5)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if focus is not None and RidRepo(session).get(review, focus) is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {focus}")
    ctx = _document_context(session, request, user, review, saved=saved, focus=focus)
    return templates.TemplateResponse(request, "document.html", ctx)


@web.get("/ui/reviews/{review_id}/diff", response_class=HTMLResponse)
def diff_page(
    review_id: str,
    request: Request,
    view: str = "compact",
    session: Session = Depends(get_session),
):
    """Full-document diff, baseline vs latest version (v3 step 03 task 4):
    same word-level renderer as the per-RID Changes section (task 3), same
    membership authz as ``document_page`` — any review member or a global
    admin, regardless of review phase.

    v3.1 step 03: ``?view=compact`` (default) keeps ±3 lines around each hunk;
    ``?view=full`` renders the whole document with old/new line numbers. The
    state lives in the URL (shareable, no JS — the v2.2 filter-chip idiom);
    an unrecognised value falls back to compact rather than erroring."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="only review members may open the diff")
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    latest = VersionRepo(session).latest(review)
    full = view == "full"
    return templates.TemplateResponse(
        request,
        "diff.html",
        {
            "user": user,
            "review": review,
            "baseline": baseline,
            "latest": latest,
            "view": "full" if full else "compact",
            "diff_html": html_diff(
                baseline.content,
                latest.content,
                context=None if full else 3,
                line_numbers=full,
            ),
        },
    )


@web.get("/ui/reviews/{review_id}/edit-copy")
def edit_copy_redirect(review_id: str):
    """The v1.4 reviewer editor is superseded by the unified viewer (v2)."""
    return RedirectResponse(f"/ui/reviews/{review_id}/document", 303)


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
        # dry-run the harvest BEFORE persisting anything: a vanished block for a
        # finding past 'open' must refuse the save (WithdrawViolation), and a
        # handled 422 would otherwise still commit the copy write (v3).
        rtd = svc.export(session, review)
        copies = {c.user.display_name: c.content for c in ReviewerCopyRepo(session).list(review)}
        copies[user.display_name] = content
        build_rtd(baseline.content, rtd.meta, copies, existing=rtd)
    except (FreezeViolation, WithdrawViolation, ParseError) as exc:
        ctx = _document_context(
            session,
            request,
            user,
            review,
            error=f"Rejected — {exc}",
            my_copy_override=content,  # keep what they typed
        )
        return templates.TemplateResponse(request, "document.html", ctx, status_code=422)
    submit = action == "submit"
    svc.add_reviewer_copy(session, review, user.display_name, content, submitted=submit)
    svc.harvest(session, review, by=user)  # Save or Submit re-harvests → comments show in the table
    if submit:
        return RedirectResponse(f"/ui/reviews/{review_id}", 303)
    return RedirectResponse(f"/ui/reviews/{review_id}/document?saved=1", 303)


def _require_member(session: Session, request: Request, review_id: str):
    """(user, review) for any member of the review (or a global admin), else
    a redirect/403. v3: private notes belong to every seat, not just reviewers
    — e.g. the owner annotates a draft comment they cannot dispose yet."""
    user = _current(request, session)
    if not user:
        return None, None, _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="only review members have private notes here")
    return user, review, None


@web.get("/ui/reviews/{review_id}/my-notes")
def my_notes(review_id: str, request: Request, session: Session = Depends(get_session)):
    """The current member's private notes for this review: {anchor_key: body}."""
    user, review, redirect = _require_member(session, request, review_id)
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
    """Upsert one private note (empty body clears it). Scoped to the member."""
    user, review, redirect = _require_member(session, request, review_id)
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


@web.get("/ui/reviews/{review_id}/closeout")
def closeout_redirect(review_id: str):
    """v3's standalone workspace is folded into the viewer (v3.1 step 01)."""
    return RedirectResponse(f"/ui/reviews/{review_id}/document", 303)


@web.post("/ui/reviews/{review_id}/closeout", response_class=HTMLResponse)
def closeout_save(
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
    authz.forbid_ai_commit(user)
    rids = list(dict.fromkeys(rids))  # dedup ticked RIDs (the service links duplicates verbatim)
    try:
        svc.save_closeout_version(session, review, content, rid_ids=rids, by=user)
    except svc.PhaseError:
        raise HTTPException(status_code=409, detail="the review is not in closeout")
    except ValueError as exc:
        ctx = _document_context(
            session, request, user, review, error=str(exc), content_override=content
        )
        return templates.TemplateResponse(request, "document.html", ctx, status_code=422)
    return RedirectResponse(f"/ui/reviews/{review_id}/document", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/implement")
def mark_implemented(
    review_id: str,
    rid: str,
    request: Request,
    resolution: str = Form(""),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    authz.forbid_ai_commit(user)
    try:
        # recorded plan deviation (step 02 task 2): the dispose form no longer
        # carries `resolution` — it's captured here, right before the owner
        # marks the finding implemented.
        if resolution:
            svc.update_rid(session, review, rid, resolution=resolution, by=user)
        svc.implement(session, review, rid, by=user)
    except svc.PhaseError:  # 409 like the workspace GET/save (phase conflict)
        raise HTTPException(status_code=409, detail="the review is not in closeout")
    except ValueError as exc:  # no linked change / wrong status / no such RID
        raise HTTPException(status_code=422, detail=str(exc))
    # v3.1 step 01: back to the card that was just marked, in the viewer where
    # the owner now works (the standalone workspace is gone)
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


@web.get("/ui/reviews/{review_id}/implement")
def implement_redirect(review_id: str):
    """v2's implement page is superseded by the closeout workspace (v3)."""
    return RedirectResponse(f"/ui/reviews/{review_id}/closeout", 303)


# --------------------------------------------------------------------------- #
# finalize + downloads (v3 step 04)
# --------------------------------------------------------------------------- #


@web.post("/ui/reviews/{review_id}/finalize")
def finalize_action(review_id: str, request: Request, session: Session = Depends(get_session)):
    """Owner (human) finalizes: last version stamped final, phase flips, the
    PDF is generated once and archived (when malus[pdf] is installed)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    authz.forbid_ai_commit(user)
    errors = svc.finalize(session, review, by=user)
    if errors:
        raise HTTPException(status_code=409, detail="; ".join(errors))
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


@web.post("/ui/reviews/{review_id}/reopen-terminated")
def reopen_terminated_action(
    review_id: str, request: Request, session: Session = Depends(get_session)
):
    """Admin escape hatch (v3.1): ``finalized -> closeout``, the undo of
    Terminate. Reserved to a human global admin — not the owner, not a
    moderator, never an AI. ``svc.reopen_finalized`` re-checks both bars, and
    raises ``PhaseError`` (-> 409) when the review is not terminated."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not (user.is_admin and not user.is_ai):
        raise HTTPException(
            status_code=403,
            detail="reopening a terminated review is a human global-admin-only action",
        )
    svc.reopen_finalized(session, review, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


def _member_finalized(session: Session, request: Request, review_id: str):
    user = _current(request, session)
    if not user:
        return None, None, _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="members only")
    if review.status != ReviewStatus.FINALIZED.value:
        raise HTTPException(status_code=409, detail="the review is not finalized yet")
    return user, review, None


@web.get("/ui/reviews/{review_id}/download/baseline.md")
def download_baseline_md(review_id: str, request: Request, session: Session = Depends(get_session)):
    """The frozen original (v3.1 step 04) — what the reviewers actually read,
    kept next to the final text so the pair is auditable outside maluS."""
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    baseline = VersionRepo(session).baseline(review)
    return Response(
        content=baseline.content if baseline else "",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-baseline.md"'},
    )


@web.get("/ui/reviews/{review_id}/download/final.md")
def download_final_md(review_id: str, request: Request, session: Session = Depends(get_session)):
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    latest = VersionRepo(session).latest(review)
    return Response(
        content=latest.content if latest else "",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-final.md"'},
    )


@web.get("/ui/reviews/{review_id}/download/diff.html")
def download_diff_html(review_id: str, request: Request, session: Session = Depends(get_session)):
    """Self-contained baseline→final diff (v3.1 step 04): one HTML file, inline
    CSS, no scripts and no /static references, so it survives being e-mailed or
    archived beside the PDF. `html_diff` escapes every line before adding
    markup (v3.1 step 03 supplies context=None / line_numbers)."""
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    versions = VersionRepo(session)
    baseline, latest = versions.baseline(review), versions.latest(review)
    if baseline is None or latest is None:  # defensive: a finalized review always has both
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    markup = templates.get_template("diff_download.html").render(
        review=review,
        baseline=baseline,
        latest=latest,
        diff_html=html_diff(baseline.content, latest.content, context=None, line_numbers=True),
    )
    return Response(
        content=markup,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-diff.html"'},
    )


@web.get("/ui/reviews/{review_id}/download/report.md")
def download_report_md(review_id: str, request: Request, session: Session = Depends(get_session)):
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    errors, report_md = svc.report(session, review)
    if errors:
        raise HTTPException(status_code=409, detail="; ".join(errors))
    return Response(
        content=report_md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-report.md"'},
    )


@web.get("/ui/reviews/{review_id}/download/review.pdf")
def download_review_pdf(review_id: str, request: Request, session: Session = Depends(get_session)):
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    artifact = ArtifactRepo(session).get(review, "pdf")
    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail="PDF was not generated — install malus[pdf] and re-finalize",
        )
    return Response(
        content=artifact.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{review_id}.pdf"'},
    )


@web.get("/ui/reviews/{review_id}/print", response_class=HTMLResponse)
def print_view(review_id: str, request: Request, session: Session = Depends(get_session)):
    """Zero-dependency PDF fallback: the final document rendered for the
    browser print dialog (any member, any phase past the freeze)."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="members only")
    latest = VersionRepo(session).latest(review)
    if latest is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    return templates.TemplateResponse(
        request,
        "print.html",
        {"user": user, "review": review, "content": latest.content},
    )
