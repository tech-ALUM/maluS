"""Reviewer-side verification and reopen (the reusable lifecycle core).

Verification is reviewer-side — the owner identity can never issue a verdict —
and reopening sends a RID back to ``open`` with a mandatory reason appended to
its thread. The closure-authority invariant (D3) is enforced by
``malus.models.transition``, which these helpers wrap.

This module is storage-agnostic (operates on :class:`RTD`). In v1 the
commit↔RID traceability check moved to the database (``RidChange`` rows) in
``malus.services``; :class:`TraceabilityReport` is kept here as the shared
result shape.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from .constants import Role, Status
from .models import RID, RTD, ClosureAuthorityError, TransitionError, transition


@dataclass
class TraceabilityReport:
    referenced: dict[str, list[str]] = field(default_factory=dict)
    accepted_unreferenced: list[str] = field(default_factory=list)
    referenced_not_accepted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.accepted_unreferenced and not self.referenced_not_accepted


def _find(rtd: RTD, rid_id: str) -> RID:
    for rid in rtd.rids:
        if rid.rid == rid_id:
            return rid
    raise ValueError(f"no such RID: {rid_id}")


def pending_for_reviewer(rtd: RTD, reviewer: str) -> list[RID]:
    """That reviewer's RIDs awaiting their verdict: answered = awaiting
    accept-disposition; implemented = awaiting verification."""
    return [
        r
        for r in rtd.rids
        if r.reviewer == reviewer and r.status in (Status.ANSWERED, Status.IMPLEMENTED)
    ]


def accept_disposition_rid(
    rtd: RTD, rid_id: str, *, reviewer: str, moderator: bool = False
) -> RID:
    """Close a finding: the reviewer accepts the owner's disposition (v3).

    The review-phase endpoint of a discussion; verification of the actual
    document edit happens later, in closeout, for accepted RIDs only."""
    if not reviewer:
        raise ValueError("a reviewer name is required to accept a disposition")
    if reviewer == rtd.meta.owner:
        raise ClosureAuthorityError("the owner identity may never close a finding")
    rid = _find(rtd, rid_id)
    role = Role.MODERATOR if moderator else Role.REVIEWER
    transition(rid, Status.CLOSED, actor_role=role, actor_name=reviewer)
    return rid


def request_changes_rid(
    rtd: RTD, rid_id: str, *, reviewer: str, reason: str, moderator: bool = False
) -> RID:
    """Send an implemented (or verified) RID back to ``closed`` for rework (v3),
    with a mandatory reason appended to its thread."""
    if not reviewer:
        raise ValueError("a reviewer name is required to request changes")
    if not reason or not reason.strip():
        raise ValueError("requesting changes requires a reason")
    rid = _find(rtd, rid_id)
    if reviewer == rtd.meta.owner:
        raise ClosureAuthorityError("the owner identity may never issue a verdict")
    if not moderator and rid.reviewer != reviewer:
        raise ClosureAuthorityError(
            f"only the RID's own reviewer ({rid.reviewer!r}) may request changes"
        )
    if rid.status not in (Status.IMPLEMENTED, Status.VERIFIED):
        raise TransitionError(
            f"cannot request changes on a RID in status {rid.status.value!r}"
        )
    note = f"[changes requested by {reviewer}: {reason.strip()}]"
    rid.reply = f"{rid.reply}\n{note}" if rid.reply else note
    rid.status = Status.CLOSED
    rid.verified_by = None
    rid.verified_on = None
    return rid


def verify_rid(
    rtd: RTD,
    rid_id: str,
    *,
    reviewer: str,
    moderator: bool = False,
    on: _dt.date | None = None,
) -> RID:
    """Verify a RID as a reviewer (or moderator on their behalf)."""
    if not reviewer:
        raise ValueError("a reviewer name is required to verify")
    if reviewer == rtd.meta.owner:
        raise ClosureAuthorityError("the owner identity may never issue a verdict")
    rid = _find(rtd, rid_id)
    role = Role.MODERATOR if moderator else Role.REVIEWER
    transition(rid, Status.VERIFIED, actor_role=role, actor_name=reviewer, on=on)
    return rid


def reopen_rid(
    rtd: RTD,
    rid_id: str,
    *,
    reviewer: str,
    reason: str,
    moderator: bool = False,
) -> RID:
    """Send a RID back to ``open`` with a mandatory reason appended to its thread."""
    if not reviewer:
        raise ValueError("a reviewer name is required to reopen")
    if not reason or not reason.strip():
        raise ValueError("reopening a RID requires a reason")
    rid = _find(rtd, rid_id)
    if reviewer == rtd.meta.owner:
        raise ClosureAuthorityError("the owner identity may never reopen a RID")
    if not moderator and rid.reviewer != reviewer:
        raise ClosureAuthorityError(
            f"only the RID's own reviewer ({rid.reviewer!r}) may reopen it"
        )
    if rid.status not in (
        Status.ANSWERED,
        Status.CLOSED,
        Status.IMPLEMENTED,
        Status.VERIFIED,
    ):
        raise TransitionError(f"cannot reopen a RID in status {rid.status.value!r}")
    note = f"[reopened by {reviewer}: {reason.strip()}]"
    rid.reply = f"{rid.reply}\n{note}" if rid.reply else note
    rid.status = Status.OPEN
    rid.verified_by = None
    rid.verified_on = None
    return rid
