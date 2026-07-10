"""HTTP routes — a thin, typed, authorized layer over the Step-2 services.

The router requires an authenticated user (session cookie) on every route.
Per-route authorization (``malus.api.authz``) enforces the review-scoped role
matrix; the services still enforce the closure invariant themselves. Missing
resources raise 404; domain exceptions map to 403/409 via ``errors.py``.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from malus import services as svc
from malus.api import authz
from malus.api.deps import get_session
from malus.api.schemas import (
    ApplySuggsIn,
    ApplySuggsOut,
    ChangeIn,
    ChangeOut,
    ClusterOut,
    CopyIn,
    CopyOut,
    DocumentIn,
    DocumentOut,
    DuplicateLinkOut,
    FinalizeOut,
    FreezeIn,
    HarvestOut,
    ReopenIn,
    ReportOut,
    ReviewCreate,
    ReviewerAdd,
    ReviewOut,
    RidOut,
    RidPatch,
    SuggResultOut,
    TraceabilityOut,
    TriageIn,
    TriageOut,
    VersionOut,
    ViolationOut,
)
from malus.auth.deps import get_current_user
from malus.constants import Disposition, Role, Status
from malus.db.models import RID, User
from malus.db.rtd_io import import_rtd
from malus.harvest import FreezeViolation, validate_insertion_only
from malus.models import RTD
from malus.parser import ParseError
from malus.repo import ReviewerCopyRepo, ReviewRepo, RidRepo, UserRepo, VersionRepo
from malus.triage import apply_suggs as apply_suggs_core

# Every route requires an authenticated user (401 otherwise).
router = APIRouter(dependencies=[Depends(get_current_user)])


def _review_or_404(session: Session, review_id: str):
    review = ReviewRepo(session).get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"no such review: {review_id}")
    return review


def _require_rid(session: Session, review, rid: str) -> RID:
    row = RidRepo(session).get(review, rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such RID: {rid}")
    return row


def _rid_dto(rtd: RTD, rid: str):
    for r in rtd.rids:
        if r.rid == rid:
            return r
    raise HTTPException(status_code=404, detail=f"no such RID: {rid}")


def _disposition(value: Optional[str]) -> Optional[Disposition]:
    if value is None:
        return None
    try:
        return Disposition(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid disposition: {value!r}")


# --------------------------------------------------------------------------- #
# reviews, document, freeze, reviewers, copies
# --------------------------------------------------------------------------- #


@router.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(
    body: ReviewCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # the creating user becomes the owner
    review = svc.create_review(
        session,
        review_id=body.review_id,
        document_name=body.document_name,
        owner=user.display_name,
        reviewers=body.reviewers,
        title=body.title,
        rid_prefix=body.rid_prefix,
        created=body.created,
    )
    session.flush()
    return ReviewOut.from_row(review)


@router.get("/reviews", response_model=list[ReviewOut])
def list_reviews(session: Session = Depends(get_session)):
    return [ReviewOut.from_row(r) for r in ReviewRepo(session).list()]


@router.post("/reviews/import", response_model=ReviewOut, status_code=201)
def import_review(
    rtd_yaml: str = Body(..., media_type="text/plain"),
    session: Session = Depends(get_session),
):
    review = import_rtd(session, RTD.from_yaml(rtd_yaml))
    session.flush()
    return ReviewOut.from_row(review)


@router.get("/reviews/{review_id}", response_model=ReviewOut)
def get_review(review_id: str, session: Session = Depends(get_session)):
    return ReviewOut.from_row(_review_or_404(session, review_id))


@router.post("/reviews/{review_id}/document", response_model=DocumentOut)
def set_document(
    review_id: str,
    body: DocumentIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    version = svc.save_version(session, review, body.content, by=user)
    return DocumentOut(
        name=review.documents[0].name, content=version.content, version=VersionOut.from_row(version)
    )


@router.get("/reviews/{review_id}/document", response_model=DocumentOut)
def get_document(review_id: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    latest = VersionRepo(session).latest(review)
    if latest is None:
        raise HTTPException(status_code=404, detail="no document version yet")
    return DocumentOut(
        name=review.documents[0].name, content=latest.content, version=VersionOut.from_row(latest)
    )


@router.post("/reviews/{review_id}/freeze", response_model=VersionOut)
def freeze(
    review_id: str,
    body: FreezeIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    content = body.content
    if content is None:
        latest = VersionRepo(session).latest(review)
        if latest is None:
            raise HTTPException(status_code=409, detail="no document content to freeze")
        content = latest.content
    return VersionOut.from_row(svc.freeze_baseline(session, review, content, by=user))


@router.post("/reviews/{review_id}/reviewers", response_model=ReviewOut)
def add_reviewer(
    review_id: str,
    body: ReviewerAdd,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    if body.role not in (Role.REVIEWER.value, Role.MODERATOR.value):
        raise HTTPException(status_code=422, detail="role must be 'reviewer' or 'moderator'")
    account = UserRepo(session).get_or_create(body.name)
    if not any(m.user_id == account.id for m in review.members):
        ReviewRepo(session).add_member(review, account, body.role)
        session.flush()
    return ReviewOut.from_row(review)


@router.get("/reviews/{review_id}/reviewers", response_model=list[str])
def list_reviewers(review_id: str, session: Session = Depends(get_session)):
    return ReviewOut.from_row(_review_or_404(session, review_id)).reviewers


@router.put("/reviews/{review_id}/copies/{user}", response_model=CopyOut)
def put_copy(
    review_id: str,
    user: str,
    body: CopyIn,
    session: Session = Depends(get_session),
    caller: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_own_copy(session, review, caller, user)
    copy = svc.add_reviewer_copy(session, review, user, body.content)
    ordinal = copy.based_on_version.ordinal if copy.based_on_version else None
    return CopyOut(user=user, content=copy.content, based_on_ordinal=ordinal)


@router.get("/reviews/{review_id}/copies/{user}", response_model=CopyOut)
def get_copy(review_id: str, user: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    account = UserRepo(session).by_display_name(user)
    copy = None
    if account is not None:
        copy = next(
            (c for c in ReviewerCopyRepo(session).list(review) if c.user_id == account.id), None
        )
    if copy is None:
        raise HTTPException(status_code=404, detail=f"no copy for {user!r}")
    ordinal = copy.based_on_version.ordinal if copy.based_on_version else None
    return CopyOut(user=user, content=copy.content, based_on_ordinal=ordinal)


@router.get("/reviews/{review_id}/baseline")
def get_baseline(review_id: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=404, detail="no frozen baseline yet")
    return {
        "content": baseline.content,
        "content_hash": baseline.content_hash,
        "ordinal": baseline.ordinal,
    }


@router.post("/reviews/{review_id}/copies/{user}/submit", response_model=HarvestOut)
def submit_copy(
    review_id: str,
    user: str,
    body: CopyIn,
    session: Session = Depends(get_session),
    caller: User = Depends(get_current_user),
):
    """A reviewer (human or AI agent) submits their copy: validate (parser) →
    save → re-harvest. Comment blocks only; tampering is rejected (422)."""
    review = _review_or_404(session, review_id)
    authz.require_own_copy(session, review, caller, user)
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    try:
        validate_insertion_only(baseline.content, body.content)
    except (FreezeViolation, ParseError) as exc:
        raise HTTPException(status_code=422, detail=f"freeze/parse rejection: {exc}")
    svc.add_reviewer_copy(session, review, user, body.content)
    result = svc.harvest(session, review, by=caller)
    return HarvestOut(
        rids=[RidOut.from_dto(r) for r in result.rtd.rids],
        violations=[
            ViolationOut(reviewer=v.reviewer, message=v.message, line=v.line)
            for v in result.violations
        ],
    )


# --------------------------------------------------------------------------- #
# pipeline: harvest, triage, apply suggestions
# --------------------------------------------------------------------------- #


@router.post("/reviews/{review_id}/harvest", response_model=HarvestOut)
def harvest(
    review_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_moderator(session, review, user)
    result = svc.harvest(session, review, by=user)
    return HarvestOut(
        rids=[RidOut.from_dto(r) for r in result.rtd.rids],
        violations=[
            ViolationOut(reviewer=v.reviewer, message=v.message, line=v.line)
            for v in result.violations
        ],
    )


@router.post("/reviews/{review_id}/triage", response_model=TriageOut)
def triage(
    review_id: str,
    body: TriageIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    if body.auto:
        authz.require_moderator(session, review, user)  # applying links is moderator-only
    # proposing clusters (read-only) is available to any authenticated member
    proposals, applied = svc.triage(
        session,
        review,
        auto=body.auto,
        threshold=body.threshold,
        auto_threshold=body.auto_threshold,
        by=user,
    )
    return TriageOut(
        proposals=[
            ClusterOut(
                master=p.master,
                links=[DuplicateLinkOut(duplicate=l.duplicate, confidence=l.confidence) for l in p.links],
            )
            for p in proposals
        ],
        applied=applied,
    )


@router.post("/reviews/{review_id}/apply-suggs", response_model=ApplySuggsOut)
def apply_suggs(
    review_id: str,
    body: ApplySuggsIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner_or_moderator(session, review, user)
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="freeze the baseline before applying suggestions")
    if body.dry_run:
        _text, results = apply_suggs_core(baseline.content, svc.export(session, review))
        version = None
    else:
        db_version, results = svc.apply_suggestions(session, review, by=user)
        version = VersionOut.from_row(db_version)
    return ApplySuggsOut(
        version=version,
        results=[
            SuggResultOut(rid=r.rid, old=r.old, new=r.new, applied=r.applied, reason=r.reason)
            for r in results
        ],
    )


# --------------------------------------------------------------------------- #
# RIDs: read, edit/transition (owner), verify/reopen (reviewer/moderator), changes
# --------------------------------------------------------------------------- #


@router.get("/reviews/{review_id}/rids", response_model=list[RidOut])
def list_rids(review_id: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    return [RidOut.from_dto(r) for r in svc.export(session, review).rids]


@router.get("/reviews/{review_id}/rids/{rid}", response_model=RidOut)
def get_rid(review_id: str, rid: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    return RidOut.from_dto(_rid_dto(svc.export(session, review), rid))


@router.patch("/reviews/{review_id}/rids/{rid}", response_model=RidOut)
def patch_rid(
    review_id: str,
    rid: str,
    body: RidPatch,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)  # reply/disposition/resolution + answer/implement
    _require_rid(session, review, rid)
    disposition = _disposition(body.disposition)

    if body.status is None:
        svc.update_rid(
            session, review, rid, reply=body.reply, resolution=body.resolution,
            disposition=disposition, by=user,
        )
    elif body.status == Status.ANSWERED.value:
        if disposition is None:
            raise HTTPException(status_code=422, detail="answering a RID requires a disposition")
        svc.answer(session, review, rid, disposition=disposition, reply=body.reply, by=user)
        if body.resolution is not None:
            svc.update_rid(session, review, rid, resolution=body.resolution, by=user)
    elif body.status == Status.IMPLEMENTED.value:
        if body.reply is not None or body.resolution is not None:
            svc.update_rid(session, review, rid, reply=body.reply, resolution=body.resolution, by=user)
        svc.implement(session, review, rid, by=user)
    else:
        raise HTTPException(
            status_code=422,
            detail=f"PATCH cannot set status {body.status!r}; use /verify or /reopen",
        )
    return RidOut.from_dto(_rid_dto(svc.export(session, review), rid))


@router.post("/reviews/{review_id}/rids/{rid}/verify", response_model=RidOut)
def verify(
    review_id: str,
    rid: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    row = _require_rid(session, review, rid)
    on_behalf = authz.require_verify(session, review, user, row)
    svc.verify(session, review, rid, reviewer=user.display_name, moderator=on_behalf, on=dt.date.today())
    return RidOut.from_dto(_rid_dto(svc.export(session, review), rid))


@router.post("/reviews/{review_id}/rids/{rid}/reopen", response_model=RidOut)
def reopen(
    review_id: str,
    rid: str,
    body: ReopenIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    row = _require_rid(session, review, rid)
    on_behalf = authz.require_verify(session, review, user, row)
    svc.reopen(session, review, rid, reviewer=user.display_name, reason=body.reason, moderator=on_behalf)
    return RidOut.from_dto(_rid_dto(svc.export(session, review), rid))


@router.post("/reviews/{review_id}/changes", response_model=ChangeOut)
def create_change(
    review_id: str,
    body: ChangeIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    for rid in body.rids:
        _require_rid(session, review, rid)
    version = svc.save_version(session, review, body.content, by=user)
    for rid in body.rids:
        svc.link_change(session, review, rid, version, note=body.note, by=user)
    return ChangeOut(version=VersionOut.from_row(version), linked=list(body.rids))


# --------------------------------------------------------------------------- #
# report, traceability, finalize, export
# --------------------------------------------------------------------------- #


@router.get("/reviews/{review_id}/report", response_model=ReportOut)
def report(review_id: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    errors, markdown = svc.report(session, review)
    return ReportOut(errors=errors, report=markdown)


@router.get("/reviews/{review_id}/traceability", response_model=TraceabilityOut)
def traceability(review_id: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    result = svc.check_traceability(session, review)
    return TraceabilityOut(
        referenced=result.referenced,
        accepted_unreferenced=result.accepted_unreferenced,
        referenced_not_accepted=result.referenced_not_accepted,
        ok=result.ok,
    )


@router.post("/reviews/{review_id}/finalize", response_model=FinalizeOut)
def finalize(
    review_id: str,
    body: Optional[FreezeIn] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    errors = svc.finalize(session, review, final_content=body.content if body else None, by=user)
    return FinalizeOut(errors=errors, finalized=not errors, status=review.status)


@router.get("/reviews/{review_id}/export")
def export_review(review_id: str, session: Session = Depends(get_session)):
    review = _review_or_404(session, review_id)
    return PlainTextResponse(svc.export(session, review).to_yaml(), media_type="application/x-yaml")
