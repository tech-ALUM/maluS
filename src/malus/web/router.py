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
from malus.auth.service import authenticate
from malus.constants import Disposition, Role, Status
from malus.db.models import ReviewStatus, User
from malus.harvest import FreezeViolation, validate_insertion_only
from malus.parser import ParseError
from malus.repo import (
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
}
_ENUM_FACETS = ("status", "reviewer", "type", "severity", "disposition")
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

    def _facet_value(r, cfacet: str) -> str:
        if cfacet == "status":
            return r.status.value
        if cfacet == "reviewer":
            return r.reviewer
        if cfacet == "type":
            return r.type.value if r.type else ""
        if cfacet == "severity":
            return r.severity.value if r.severity else ""
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
    if user.is_admin:
        pass  # global superuser: retract any comment, any status (v1.10)
    elif role != Role.REVIEWER.value or row.reviewer_id != user.id:
        raise HTTPException(status_code=403, detail="you may only retract your own comment")
    elif row.status != Status.OPEN.value:
        raise HTTPException(status_code=409, detail="only an open comment can be retracted")
    svc.retract_comment(session, review, rid, by=user)
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

    data = {
        "reviewId": review.review_id_str,
        "phase": review.status,
        "role": role,
        "isAdmin": user.is_admin,
        "isReviewer": is_reviewer,
        "canDispose": (role == Role.OWNER.value or user.is_admin) and not user.is_ai,
        "me": user.display_name,
        "baseline": baseline.content,
        "myCopy": my_copy,
        "mySubmitted": bool(mine and mine.submitted_at) if is_reviewer else False,
        "reviewers": rtd.meta.reviewers,
        "colors": colors,
        "rids": rids,
        "saved": bool(saved),
        "focus": focus,
    }
    return {"user": user, "review": review, "role": role, "data": data, "error": error}


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
    except (FreezeViolation, ParseError) as exc:
        ctx = _document_context(
            session,
            request,
            user,
            review,
            error=f"Rejected — freeze rule / parse: {exc}",
            my_copy_override=content,  # keep what they typed
        )
        return templates.TemplateResponse(request, "document.html", ctx, status_code=422)
    submit = action == "submit"
    svc.add_reviewer_copy(session, review, user.display_name, content, submitted=submit)
    svc.harvest(session, review, by=user)  # Save or Submit re-harvests → comments show in the table
    if submit:
        return RedirectResponse(f"/ui/reviews/{review_id}", 303)
    return RedirectResponse(f"/ui/reviews/{review_id}/document?saved=1", 303)


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
    if review.status != ReviewStatus.CLOSEOUT.value:
        raise HTTPException(
            status_code=409, detail="implementing findings is only available during closeout"
        )
    latest = VersionRepo(session).latest(review)
    accepted = [
        r
        for r in svc.export(session, review).rids
        if r.disposition is Disposition.ACCEPTED and r.status is Status.CLOSED
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
    if review.status != ReviewStatus.CLOSEOUT.value:
        raise HTTPException(
            status_code=409, detail="implementing findings is only available during closeout"
        )
    version = svc.save_version(session, review, content, by=user)
    for rid in rids:
        if RidRepo(session).get(review, rid) is None:
            continue
        svc.link_change(session, review, rid, version, by=user)
        try:  # advance accepted+closed RIDs now that a change links them
            svc.implement(session, review, rid, by=user)
        except ValueError:
            pass  # not eligible to advance (wrong disposition/status) — leave as-is
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)
