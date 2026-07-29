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

from malus.constants import Disposition, Kind, Role, Status
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
from malus.parser import scan
from malus.lifecycle import (
    TraceabilityReport,
    accept_disposition_rid,
    pending_for_reviewer,
    reopen_rid,
    request_changes_rid,
    verify_rid,
)
from malus.models import RID as RidDTO
from malus.models import RTD, ClosureAuthorityError, TransitionError, transition
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


class PhaseError(TransitionError):
    """The review is not in the phase this action requires (v3) → HTTP 409."""


def _require_phase(review: Review, *phases: ReviewStatus) -> None:
    if review.status not in {p.value for p in phases}:
        allowed = " | ".join(p.value for p in phases)
        raise PhaseError(
            f"review {review.review_id_str} is in phase {review.status!r}; "
            f"this action requires {allowed}"
        )


def _forbid_ai_commit(by) -> None:
    """An AI principal may DRAFT but never COMMIT an owner decision (v1.7):
    answer / implement / finalize. Drafting (``update_rid``, no transition) stays
    allowed. Raises :class:`ClosureAuthorityError` (→ 403), mirroring the closure
    invariant — only a human owner confirms."""
    if by is not None and getattr(by, "is_ai", False):
        raise ClosureAuthorityError(
            "AI principals may only draft a disposition; every committing owner "
            "action (freeze, document edits, apply-suggs, answer/implement/finalize) "
            "is reserved to a human owner"
        )


def _sugg_repr(old: str, new: str) -> str:
    """Render a SUGG's operands exactly as harvest stores them in ``comment``
    (mirrors ``harvest._render_sugg``), so a parsed block can be matched to its RID."""
    esc = lambda s: s.replace("}", "\\}").replace('"', '\\"')  # noqa: E731
    return f'"{esc(old)}" -> "{esc(new)}"'


def _block_matches(block, dto) -> bool:
    """True if a parsed copy block is the source of RID ``dto`` (same identity)."""
    if block.kind is not dto.kind:
        return False
    if block.kind is Kind.COMM:
        return (
            block.text == dto.comment
            and block.comment_type == dto.type
            and block.severity == dto.severity
        )
    return _sugg_repr(block.old, block.new) == dto.comment


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
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.DRAFT)
    version = VersionRepo(session).freeze(review, content, by=by)
    ReviewRepo(session).set_status(review, ReviewStatus.IN_REVIEW.value)
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
    _require_phase(review, ReviewStatus.IN_REVIEW)
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
    _forbid_ai_commit(by)
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


def _purge_retracted(session: Session, review: Review) -> None:
    """Hard-delete ``withdrawn`` RID rows that are *pristine* — retracted before
    the owner ever engaged (no disposition/reply/resolution, not verified, no
    linked change, not part of a cluster). A withdrawn RID that carries owner
    history is kept (its trace cannot be erased). The pure ``build_rtd`` core still
    only withdraws; this DB cleanup is what makes a retracted comment disappear."""
    rows = RidRepo(session).list(review)
    masters = {r.master_id for r in rows if r.master_id is not None}
    for row in rows:
        if row.status != Status.WITHDRAWN.value:
            continue
        pristine = (
            not row.disposition
            and not row.reply
            and not row.resolution
            and row.verified_by_id is None
            and row.master_id is None
            and row.id not in masters
            and not RidRepo(session).changes_for(row)
        )
        if pristine:
            session.delete(row)
    session.flush()


def harvest(session: Session, review: Review, *, by=None) -> HarvestResult:
    _require_phase(review, ReviewStatus.IN_REVIEW)
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise ValueError("cannot harvest before the baseline is frozen")
    existing = export_rtd(session, review)
    copies = {c.user.display_name: c.content for c in ReviewerCopyRepo(session).list(review)}
    result = build_rtd(baseline.content, existing.meta, copies, existing=existing)
    sync_rtd_to_review(session, review, result.rtd)
    _purge_retracted(session, review)
    AuditRepo(session).log(
        action="harvest",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"rids": len(result.rtd.rids), "violations": len(result.violations)},
    )
    return result


# in_review only: the admin any-phase path is reopen_review → withdraw → start_closeout; purge stays any-phase
def retract_comment(session: Session, review: Review, rid_id: str, *, by=None):
    """Retract a reviewer's own comment: remove its block from their copy, then
    re-harvest (→ withdraw → purge if pristine). Ownership and OPEN status are
    enforced by the caller (the route)."""
    _require_phase(review, ReviewStatus.IN_REVIEW)
    row = RidRepo(session).get(review, rid_id)
    if row is None:
        raise ValueError(f"no such RID: {rid_id}")
    copy = next(
        (c for c in ReviewerCopyRepo(session).list(review) if c.user_id == row.reviewer_id),
        None,
    )
    if copy is not None:
        dto = _find(export_rtd(session, review), rid_id)
        target = next((b for b in scan(copy.content) if _block_matches(b, dto)), None)
        if target is not None:
            new_content = copy.content[: target.start] + copy.content[target.end :]
            add_reviewer_copy(
                session,
                review,
                row.reviewer.display_name,
                new_content,
                submitted=copy.submitted_at is not None,
            )
    harvest(session, review, by=by)
    AuditRepo(session).log(action="retract_comment", target=f"rid:{rid_id}", actor=by)


def reopen_submission(session: Session, review: Review, reviewer_name: str, *, by=None):
    """Un-submit a reviewer's copy (``submitted_at`` → None) so they can edit and
    resubmit — an admin superuser action (v1.10)."""
    user = UserRepo(session).by_display_name(reviewer_name)
    if user is None:
        raise ValueError(f"unknown reviewer: {reviewer_name}")
    copy = next(
        (c for c in ReviewerCopyRepo(session).list(review) if c.user_id == user.id), None
    )
    if copy is None:
        raise ValueError(f"no copy for {reviewer_name}")
    copy.submitted_at = None
    session.add(copy)
    session.flush()
    AuditRepo(session).log(
        action="reopen_submission",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"reviewer": reviewer_name},
    )
    return copy


def purge_rid(session: Session, review: Review, rid_id: str, *, by: User) -> None:
    """PERMANENTLY remove a finding (v2.2) — an advanced admin action.

    Normal deletion keeps the v1.8 semantics (pristine → hard-delete,
    acted-upon → ``withdrawn``); purge erases the RID and its traceability
    links regardless of status. The route gates on a human global admin;
    re-checked here (defense-in-depth). The ``purge_rid`` audit row — with
    the comment text — is the only remaining trace."""
    if by is None or not getattr(by, "is_admin", False) or getattr(by, "is_ai", False):
        raise ClosureAuthorityError("only a human global admin may purge a comment permanently")
    row = RidRepo(session).get(review, rid_id)
    if row is None:
        raise ValueError(f"no such RID: {rid_id}")
    for change in session.exec(select(RidChange).where(RidChange.rid_id == row.id)).all():
        session.delete(change)
    for dup in session.exec(select(RID).where(RID.master_id == row.id)).all():
        dup.master_id = None
        session.add(dup)
    session.flush()
    detail = {
        "reviewer": row.reviewer.display_name if row.reviewer else None,
        "comment": row.comment,
        "status": row.status,
    }
    session.delete(row)
    session.flush()
    AuditRepo(session).log(action="purge_rid", target=f"rid:{rid_id}", actor=by, detail=detail)


def transfer_ownership(
    session: Session, review: Review, new_owner: User, old_owner_fate: str, *, by: User
) -> Review:
    """Transfer primary ownership to ``new_owner`` (v2 step 2).

    The transferrer chose the ex-owner's fate: ``"remove"`` (drop their
    membership) or ``"reviewer"`` (demote — from then on they may verify,
    legitimately: they are no longer the owner). The target must be an
    active **human** account. Route-level authorization (current owner or
    global admin) mirrors the members page; the AI guard is re-checked here
    (defense-in-depth: transfer is a committing owner action).
    """
    _forbid_ai_commit(by)
    if old_owner_fate not in ("remove", "reviewer"):
        raise ValueError(f"invalid owner fate: {old_owner_fate!r} (use remove or reviewer)")
    if new_owner.is_ai:
        raise ValueError("primary ownership is human — an AI principal cannot own a review")
    if not new_owner.is_active:
        raise ValueError(f"inactive account: {new_owner.username!r}")
    if review.owner_id == new_owner.id:
        raise ValueError(f"{new_owner.display_name} already owns this review")
    reviews = ReviewRepo(session)
    old_owner = session.get(User, review.owner_id)
    review.owner_id = new_owner.id
    session.add(review)
    session.flush()
    reviews.set_member_role(review, new_owner, Role.OWNER.value)
    if old_owner is not None:
        if old_owner_fate == "remove":
            reviews.remove_member(review, old_owner)
        else:
            reviews.set_member_role(review, old_owner, Role.REVIEWER.value)
    AuditRepo(session).log(
        action="transfer_ownership",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={
            "from": old_owner.display_name if old_owner else None,
            "to": new_owner.display_name,
            "old_owner_fate": old_owner_fate,
        },
    )
    return review


def triage(
    session: Session,
    review: Review,
    *,
    auto: bool = False,
    threshold: float = CLUSTER_THRESHOLD,
    auto_threshold: float = AUTO_THRESHOLD,
    by=None,
) -> tuple[list[ClusterProposal], int]:
    _require_phase(review, ReviewStatus.IN_REVIEW)
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
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.IN_REVIEW)
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


def _reviewer_copy_submitted(session: Session, review: Review, reviewer_name: str) -> bool:
    user = UserRepo(session).by_display_name(reviewer_name)
    if user is None:
        return False
    copy = next(
        (c for c in ReviewerCopyRepo(session).list(review) if c.user_id == user.id), None
    )
    return bool(copy and copy.submitted_at)


def answer(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    disposition: Disposition,
    reply: Optional[str] = None,
    by=None,
):
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.IN_REVIEW)
    rtd = export_rtd(session, review)
    rid = _find(rtd, rid_id)
    # v3: a draft comment (unsubmitted copy) can still change — dispose waits
    if not _reviewer_copy_submitted(session, review, rid.reviewer):
        raise PhaseError(
            f"{rid_id} is a draft comment — its reviewer has not submitted their copy yet"
        )
    rid.disposition = disposition
    rid.reply = reply
    transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name=review.owner.display_name)
    sync_rtd_to_review(session, review, rtd)
    detail: dict = {"disposition": disposition.value}
    if reply:
        detail["reply"] = reply
    AuditRepo(session).log(action="answer", target=f"rid:{rid_id}", actor=by, detail=detail)
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
    """Edit a RID's owner-side fields in place (no status transition).

    Allowed in ``in_review`` OR ``closeout`` (v3 plan-table amendment): this
    only widens *editing* reply/resolution/disposition on an existing RID —
    e.g. recording ``resolution`` while implementing, in closeout. Drafting a
    fresh disposition from ``open`` (``answer``/dispose) stays IN_REVIEW-only,
    untouched. A disposition is editable only while ``open``/``answered``:
    once the reviewer accepted it (``closed`` and beyond) it is settled and
    changes only through the formal reopen."""
    _require_phase(review, ReviewStatus.IN_REVIEW, ReviewStatus.CLOSEOUT)
    rtd = export_rtd(session, review)
    rid = _find(rtd, rid_id)
    if disposition is not None and rid.status not in (Status.OPEN, Status.ANSWERED):
        raise TransitionError(
            f"{rid_id} is {rid.status.value}; a settled disposition changes only through reopen"
        )
    if reply is not None:
        rid.reply = reply
    if resolution is not None:
        rid.resolution = resolution
    if disposition is not None:
        rid.disposition = disposition
    if by is not None and getattr(by, "is_ai", False):
        rid.ai_drafted = True  # v1.7: an AI-written disposition is a draft awaiting human confirm
    sync_rtd_to_review(session, review, rtd)
    changed: dict = {}  # v2.1: the timeline records WHAT changed, per event
    if reply is not None:
        changed["reply"] = reply
    if resolution is not None:
        changed["resolution"] = resolution
    if disposition is not None:
        changed["disposition"] = disposition.value
    AuditRepo(session).log(
        action="update_rid", target=f"rid:{rid_id}", actor=by,
        detail={"changed": changed} if changed else None,
    )
    return RidRepo(session).get(review, rid_id)


def discard_disposition_draft(session: Session, review: Review, rid_id: str, *, by=None):
    """Discard an AI-drafted proposal, clearing it back to a plain OPEN finding
    (v1.7). The RID keeps its identity; only the drafted owner-fields and the
    ``ai_drafted`` flag are cleared."""
    _require_phase(review, ReviewStatus.IN_REVIEW)
    rtd = export_rtd(session, review)
    rid = _find(rtd, rid_id)
    rid.disposition = None
    rid.reply = None
    rid.resolution = None
    rid.ai_drafted = False
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(action="discard_draft", target=f"rid:{rid_id}", actor=by)
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
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.CLOSEOUT)
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
    _require_phase(review, ReviewStatus.CLOSEOUT)
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
    _require_phase(review, ReviewStatus.IN_REVIEW)
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


def accept_disposition(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    reviewer: str,
    moderator: bool = False,
):
    """The reviewer closes a finding: they accept the owner's disposition
    (v3). The review-phase endpoint of a discussion; verification of the
    actual document edit happens later, in closeout, for accepted RIDs only."""
    _require_phase(review, ReviewStatus.IN_REVIEW)
    rtd = export_rtd(session, review)
    accept_disposition_rid(rtd, rid_id, reviewer=reviewer, moderator=moderator)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="accept_disposition",
        target=f"rid:{rid_id}",
        actor=UserRepo(session).get_or_create(reviewer),
        detail={"moderator": moderator},
    )
    return RidRepo(session).get(review, rid_id)


def request_changes(
    session: Session,
    review: Review,
    rid_id: str,
    *,
    reviewer: str,
    reason: str,
    moderator: bool = False,
):
    """Send an implemented (or verified) RID back to ``closed`` for rework
    (v3), with a mandatory reason appended to its thread. Closeout-only: the
    review-level analogue of ``reopen`` once the review has left IN_REVIEW."""
    _require_phase(review, ReviewStatus.CLOSEOUT)
    rtd = export_rtd(session, review)
    request_changes_rid(rtd, rid_id, reviewer=reviewer, reason=reason, moderator=moderator)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="request_changes",
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
    _require_phase(review, ReviewStatus.CLOSEOUT)
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
# review phases: closeout gate, start/reopen (v3)
# --------------------------------------------------------------------------- #


def closeout_gate(session: Session, review: Review) -> list[str]:
    """Empty list when closeout may start (spec §Closeout entry): ≥1
    non-withdrawn finding and none still open/answered (legacy v2
    implemented/verified rows pass)."""
    rows = RidRepo(session).list(review)
    errors: list[str] = []
    live = [r for r in rows if r.status != Status.WITHDRAWN.value]
    if not live:
        errors.append("closeout needs at least one non-withdrawn finding")
    stuck = [r.rid_str for r in live if r.status in (Status.OPEN.value, Status.ANSWERED.value)]
    if stuck:
        errors.append("findings not yet closed: " + ", ".join(sorted(stuck)))
    return errors


def start_closeout(session: Session, review: Review, *, by=None) -> Review:
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.IN_REVIEW)
    errors = closeout_gate(session, review)
    if errors:
        raise PhaseError("; ".join(errors))
    ReviewRepo(session).set_status(review, ReviewStatus.CLOSEOUT.value)
    AuditRepo(session).log(
        action="start_closeout", target=f"review:{review.review_id_str}", actor=by
    )
    return review


def reopen_review(session: Session, review: Review, *, by=None) -> Review:
    """Admin escape hatch: closeout → in_review (spec §Closeout entry)."""
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.CLOSEOUT)
    ReviewRepo(session).set_status(review, ReviewStatus.IN_REVIEW.value)
    AuditRepo(session).log(
        action="reopen_review", target=f"review:{review.review_id_str}", actor=by
    )
    return review


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
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.CLOSEOUT)
    rtd = export_rtd(session, review)
    errors: list[str] = []
    blocking = [
        r.rid
        for r in rtd.rids
        if not (
            r.status in (Status.VERIFIED, Status.WITHDRAWN)
            or (
                r.status is Status.CLOSED
                and r.disposition in (Disposition.REJECTED, Disposition.DEFERRED)
            )
        )
    ]
    if blocking:
        errors.append("findings not yet verified/closed: " + ", ".join(blocking))
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
