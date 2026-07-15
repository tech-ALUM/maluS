"""DB-backed review services: the v0 pipeline reproduced on the database.

Each service reads inputs via the repository layer, runs the **unchanged**
domain core (``harvest.build_rtd``, ``triage``, ``report``, ``lifecycle``
transitions), and persists results via repositories + ``sync_rtd_to_review``.
No git, no filesystem. Services flush; the caller commits.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from malus.constants import Disposition, Role, Status
from malus.db.models import (
    RID,
    AuditLog,
    Document,
    DocumentVersion,
    Review,
    ReviewerCopy,
    ReviewerNote,
    ReviewMember,
    ReviewStatus,
    RidChange,
    User,
)
from malus.db.rtd_io import export_rtd
from malus.harvest import HarvestResult, build_rtd
from malus.lifecycle import (
    TraceabilityReport,
    pending_for_reviewer,
    reopen_rid,
    verify_rid,
)
from malus.models import RID as RidDTO
from malus.models import RTD, transition
from malus.report import render_report, validate
from malus.repo import (
    AuditRepo,
    ReviewerCopyRepo,
    ReviewRepo,
    RidRepo,
    UserRepo,
    VersionRepo,
)
from malus.triage import (
    AUTO_THRESHOLD,
    CLUSTER_THRESHOLD,
    ClusterProposal,
    SuggResult,
    apply_clusters,
    apply_suggs,
    propose_clusters,
)
from malus.services.sync import sync_rtd_to_review


def _find(rtd: RTD, rid_id: str) -> RidDTO:
    for rid in rtd.rids:
        if rid.rid == rid_id:
            return rid
    raise ValueError(f"no such RID: {rid_id}")


# --------------------------------------------------------------------------- #
# review setup: create, freeze, reviewer copies, versions
# --------------------------------------------------------------------------- #


def create_review(
    session: Session,
    *,
    review_id: str,
    document_name: str,
    owner: str,
    reviewers: Optional[list[str]] = None,
    title: Optional[str] = None,
    rid_prefix: Optional[str] = None,
    created: Optional[dt.date] = None,
) -> Review:
    users, reviews, audit = UserRepo(session), ReviewRepo(session), AuditRepo(session)
    owner_user = users.get_or_create(owner)
    review = reviews.create(
        review_id,
        owner=owner_user,
        document_name=document_name,
        title=title,
        rid_prefix=rid_prefix,
        created=created,
    )
    reviews.add_member(review, owner_user, Role.OWNER.value)
    for name in reviewers or []:
        reviews.add_member(review, users.get_or_create(name), Role.REVIEWER.value)
    audit.log(action="create_review", target=f"review:{review_id}", actor=owner_user)
    return review


def freeze_baseline(
    session: Session, review: Review, content: str, *, by=None
) -> DocumentVersion:
    version = VersionRepo(session).freeze(review, content, by=by)
    AuditRepo(session).log(
        action="freeze",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"content_hash": version.content_hash},
    )
    return version


def add_reviewer_copy(
    session: Session,
    review: Review,
    reviewer_name: str,
    content: str,
    *,
    based_on: Optional[DocumentVersion] = None,
    submitted: bool = True,
) -> ReviewerCopy:
    """Persist a reviewer's copy. ``submitted=True`` (default) marks it submitted
    (``submitted_at = now``); ``submitted=False`` saves it as a draft
    (``submitted_at = None``) so a reviewer can keep editing across sessions."""
    user = UserRepo(session).get_or_create(reviewer_name)
    base = based_on or VersionRepo(session).baseline(review)
    submitted_at = dt.datetime.now(dt.timezone.utc) if submitted else None
    return ReviewerCopyRepo(session).upsert(
        review, user, content, based_on=base, submitted_at=submitted_at
    )


def save_version(
    session: Session, review: Review, content: str, *, by=None, is_final: bool = False
) -> DocumentVersion:
    """Record an owner-edited document version (an implementation edit)."""
    version = VersionRepo(session).add_version(review, content, by=by, is_final=is_final)
    AuditRepo(session).log(
        action="save_version",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"ordinal": version.ordinal},
    )
    return version


def export(session: Session, review: Review) -> RTD:
    return export_rtd(session, review)


# --------------------------------------------------------------------------- #
# pipeline: harvest, triage, apply suggestions
# --------------------------------------------------------------------------- #


def harvest(session: Session, review: Review, *, by=None) -> HarvestResult:
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise ValueError("cannot harvest before the baseline is frozen")
    existing = export_rtd(session, review)
    copies = {c.user.display_name: c.content for c in ReviewerCopyRepo(session).list(review)}
    result = build_rtd(baseline.content, existing.meta, copies, existing=existing)
    sync_rtd_to_review(session, review, result.rtd)
    AuditRepo(session).log(
        action="harvest",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"rids": len(result.rtd.rids), "violations": len(result.violations)},
    )
    return result


def triage(
    session: Session,
    review: Review,
    *,
    auto: bool = False,
    threshold: float = CLUSTER_THRESHOLD,
    auto_threshold: float = AUTO_THRESHOLD,
    by=None,
) -> tuple[list[ClusterProposal], int]:
    rtd = export_rtd(session, review)
    proposals = propose_clusters(rtd, threshold=threshold)
    applied = 0
    if auto:
        confident = [
            ClusterProposal(p.master, [l for l in p.links if l.confidence >= auto_threshold])
            for p in proposals
        ]
        applied = apply_clusters(rtd, [p for p in confident if p.links])
        if applied:
            sync_rtd_to_review(session, review, rtd)
            AuditRepo(session).log(
                action="triage",
                target=f"review:{review.review_id_str}",
                actor=by,
                detail={"applied": applied},
            )
    return proposals, applied


def apply_suggestions(
    session: Session, review: Review, *, by=None
) -> tuple[DocumentVersion, list[SuggResult]]:
    baseline = VersionRepo(session).baseline(review)
    rtd = export_rtd(session, review)
    new_text, results = apply_suggs(baseline.content, rtd)
    version = VersionRepo(session).add_version(review, new_text, by=by)
    AuditRepo(session).log(
        action="apply_suggs",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"ordinal": version.ordinal, "applied": sum(1 for r in results if r.applied)},
    )
    return version, results


# --------------------------------------------------------------------------- #
# lifecycle: answer, implement, verify, reopen, traceability
# --------------------------------------------------------------------------- #


def answer(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    disposition: Disposition,
    reply: Optional[str] = None,
    by=None,
):
    rtd = export_rtd(session, review)
    rid = _find(rtd, rid_id)
    rid.disposition = disposition
    rid.reply = reply
    transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name=review.owner.display_name)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="answer", target=f"rid:{rid_id}", actor=by, detail={"disposition": disposition.value}
    )
    return RidRepo(session).get(review, rid_id)


def update_rid(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    reply: Optional[str] = None,
    resolution: Optional[str] = None,
    disposition: Optional[Disposition] = None,
    by=None,
):
    """Edit a RID's owner-side fields in place (no status transition)."""
    rtd = export_rtd(session, review)
    rid = _find(rtd, rid_id)
    if reply is not None:
        rid.reply = reply
    if resolution is not None:
        rid.resolution = resolution
    if disposition is not None:
        rid.disposition = disposition
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(action="update_rid", target=f"rid:{rid_id}", actor=by)
    return RidRepo(session).get(review, rid_id)


def _post_baseline_changes(session: Session, review: Review, row) -> list[RidChange]:
    baseline = VersionRepo(session).baseline(review)
    base_ordinal = baseline.ordinal if baseline else 0
    return [
        c
        for c in RidRepo(session).changes_for(row)
        if c.version and c.version.ordinal > base_ordinal
    ]


def implement(session: Session, review: Review, rid_id: str, *, by=None):
    """Move an accepted RID answered -> implemented.

    Traceability gate (the DB analogue of the commit-reference rule): requires at
    least one ``RidChange`` linking the RID to a version newer than the baseline.
    """
    row = RidRepo(session).get(review, rid_id)
    if row is None:
        raise ValueError(f"no such RID: {rid_id}")
    if not _post_baseline_changes(session, review, row):
        raise ValueError(
            f"cannot implement {rid_id}: no change links it to a post-baseline version"
        )
    rtd = export_rtd(session, review)
    rid = _find(rtd, rid_id)
    transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name=review.owner.display_name)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(action="implement", target=f"rid:{rid_id}", actor=by)
    return RidRepo(session).get(review, rid_id)


def verify(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    reviewer: str,
    moderator: bool = False,
    on: Optional[dt.date] = None,
):
    rtd = export_rtd(session, review)
    verify_rid(rtd, rid_id, reviewer=reviewer, moderator=moderator, on=on)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="verify",
        target=f"rid:{rid_id}",
        actor=UserRepo(session).get_or_create(reviewer),
        detail={"moderator": moderator},
    )
    return RidRepo(session).get(review, rid_id)


def reopen(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    reviewer: str,
    reason: str,
    moderator: bool = False,
):
    rtd = export_rtd(session, review)
    reopen_rid(rtd, rid_id, reviewer=reviewer, reason=reason, moderator=moderator)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="reopen",
        target=f"rid:{rid_id}",
        actor=UserRepo(session).get_or_create(reviewer),
        detail={"reason": reason},
    )
    return RidRepo(session).get(review, rid_id)


def pending(session: Session, review: Review, reviewer: str) -> list[RidDTO]:
    return pending_for_reviewer(export_rtd(session, review), reviewer)


def link_change(
    session: Session,
    review: Review,
    rid_id: str,
    version: DocumentVersion,
    *,
    note: Optional[str] = None,
    by=None,
) -> RidChange:
    row = RidRepo(session).get(review, rid_id)
    if row is None:
        raise ValueError(f"no such RID: {rid_id}")
    change = RidRepo(session).add_change(row, version, note=note)
    AuditRepo(session).log(
        action="link_change", target=f"rid:{rid_id}", actor=by, detail={"ordinal": version.ordinal}
    )
    return change


def check_traceability(session: Session, review: Review) -> TraceabilityReport:
    rids, versions = RidRepo(session), VersionRepo(session)
    baseline = versions.baseline(review)
    base_ordinal = baseline.ordinal if baseline else 0
    rows = rids.list(review)
    referenced: dict[str, list[str]] = {}
    for row in rows:
        linked = [
            f"v{c.version.ordinal}"
            for c in rids.changes_for(row)
            if c.version and c.version.ordinal > base_ordinal
        ]
        if linked:
            referenced[row.rid_str] = linked
    accepted = {r.rid_str for r in rows if r.disposition == Disposition.ACCEPTED.value}
    return TraceabilityReport(
        referenced=referenced,
        accepted_unreferenced=sorted(a for a in accepted if a not in referenced),
        referenced_not_accepted=sorted(r for r in referenced if r not in accepted),
    )


# --------------------------------------------------------------------------- #
# report, finalize
# --------------------------------------------------------------------------- #


def report(session: Session, review: Review) -> tuple[list[str], str]:
    rtd = export_rtd(session, review)
    errors = validate(rtd)
    return errors, ("" if errors else render_report(rtd))


def finalize(
    session: Session, review: Review, *, final_content: Optional[str] = None, by=None
) -> list[str]:
    rtd = export_rtd(session, review)
    errors: list[str] = []
    open_rids = [
        r.rid for r in rtd.rids if r.status not in (Status.VERIFIED, Status.WITHDRAWN)
    ]
    if open_rids:
        errors.append("findings not yet verified/withdrawn: " + ", ".join(open_rids))
    errors += validate(rtd)
    if errors:
        return errors

    content = final_content
    if content is None:
        latest = VersionRepo(session).latest(review)
        content = latest.content if latest else ""
    VersionRepo(session).add_version(review, content, by=by, is_final=True)
    ReviewRepo(session).set_status(review, ReviewStatus.FINALIZED.value)
    AuditRepo(session).log(
        action="finalize",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"deferred": sum(1 for r in rtd.rids if r.disposition is Disposition.DEFERRED)},
    )
    return []


# --------------------------------------------------------------------------- #
# account erasure (v1.3): hard-delete a user, reassigning every reference
# --------------------------------------------------------------------------- #

SENTINEL_USERNAME = "deleted-user"


def sentinel_user(session: Session) -> User:
    """The shared, login-less 'Deleted user' that inherits the anonymized
    attributions of every hard-deleted account (created on first use)."""
    ghost = session.exec(select(User).where(User.username == SENTINEL_USERNAME)).first()
    if ghost is None:
        ghost = User(username=SENTINEL_USERNAME, display_name="Deleted user", is_active=False)
        session.add(ghost)
        session.flush()
    return ghost


def delete_user(
    session: Session, target: User, *, new_owners: dict[int, User], by: User
) -> None:
    """Hard-delete ``target``. Reviews it primary-owns are transferred to the
    admin-chosen new owner (``new_owners`` keyed by ``Review.id``); its findings,
    verifications, versions and audit entries are reassigned to the shared
    sentinel; its memberships and reviewer copies are dropped; then the row is
    removed and the erasure is audited. The caller commits."""
    reviews = ReviewRepo(session)
    # 1) transfer owned reviews to the chosen new owner (owner_id + owner seat)
    for review in session.exec(select(Review).where(Review.owner_id == target.id)).all():
        new_owner = new_owners.get(review.id)
        if new_owner is None:
            raise ValueError(f"no new owner supplied for review {review.review_id_str}")
        review.owner_id = new_owner.id
        session.add(review)
        reviews.set_member_role(review, new_owner, Role.OWNER.value)
    # 2) anonymize historical attributions onto the sentinel
    ghost = sentinel_user(session)
    for rid in session.exec(select(RID).where(RID.reviewer_id == target.id)).all():
        rid.reviewer_id = ghost.id
        session.add(rid)
    for rid in session.exec(select(RID).where(RID.verified_by_id == target.id)).all():
        rid.verified_by_id = ghost.id
        session.add(rid)
    for v in session.exec(
        select(DocumentVersion).where(DocumentVersion.created_by_id == target.id)
    ).all():
        v.created_by_id = ghost.id
        session.add(v)
    for entry in session.exec(select(AuditLog).where(AuditLog.actor_id == target.id)).all():
        entry.actor_id = ghost.id
        session.add(entry)
    # 3) drop the target's transient rows (memberships, raw copies)
    for m in session.exec(select(ReviewMember).where(ReviewMember.user_id == target.id)).all():
        session.delete(m)
    for copy in session.exec(select(ReviewerCopy).where(ReviewerCopy.user_id == target.id)).all():
        session.delete(copy)
    session.flush()
    # 4) delete the account, then record the erasure (actor is the admin, never target)
    username = target.username
    session.delete(target)
    session.flush()
    AuditRepo(session).log(action="delete_user", target=f"user:{username}", actor=by)


def delete_review(session: Session, review: Review, *, by: User) -> None:
    """Hard-delete a review and ALL its data (transactional). Children are removed
    in FK-safe order, then the Review; a ``delete_review`` audit entry is written.
    ``AuditLog`` rows are kept (they reference the review by string, not FK). The
    caller commits."""
    rids = session.exec(select(RID).where(RID.review_id == review.id)).all()
    rid_ids = [r.id for r in rids]
    if rid_ids:  # RidChange (child of RID + DocumentVersion)
        for ch in session.exec(select(RidChange).where(RidChange.rid_id.in_(rid_ids))).all():
            session.delete(ch)
    for r in rids:  # clear the master_id self-reference before deleting the RIDs
        r.master_id = None
        session.add(r)
    session.flush()
    for r in rids:
        session.delete(r)
    for copy in session.exec(select(ReviewerCopy).where(ReviewerCopy.review_id == review.id)).all():
        session.delete(copy)
    for note in session.exec(select(ReviewerNote).where(ReviewerNote.review_id == review.id)).all():
        session.delete(note)
    for member in session.exec(select(ReviewMember).where(ReviewMember.review_id == review.id)).all():
        session.delete(member)
    docs = session.exec(select(Document).where(Document.review_id == review.id)).all()
    doc_ids = [d.id for d in docs]
    if doc_ids:
        for v in session.exec(
            select(DocumentVersion).where(DocumentVersion.document_id.in_(doc_ids))
        ).all():
            session.delete(v)
    for d in docs:
        session.delete(d)
    session.flush()
    review_str = review.review_id_str
    session.delete(review)
    session.flush()
    AuditRepo(session).log(action="delete_review", target=f"review:{review_str}", actor=by)
