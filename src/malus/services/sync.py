"""Reconcile an in-memory :class:`RTD` back into a review's DB rows.

This is the write half of the DB<->RTD bridge (the read half is
``malus.db.rtd_io.export_rtd``). Every mutating service exports the review to an
RTD, mutates it through the *unchanged* domain core, then calls this to persist
the result — upserting RID rows by ``rid_str`` (never deleting; ``withdrawn`` is
a status). ``duplicates`` is derived, so only ``master_id`` is written.
"""

from __future__ import annotations

from sqlmodel import Session

from malus.db.models import RID
from malus.models import RTD
from malus.repo import RidRepo, UserRepo


def _value(member) -> str | None:
    return None if member is None else member.value


def sync_rtd_to_review(session: Session, review, rtd: RTD) -> None:
    users = UserRepo(session)
    rids = RidRepo(session)
    rows: dict[str, RID] = {}

    for r in rtd.rids:
        # Resolve users first: get_or_create runs a SELECT, which would autoflush
        # a half-built RID row (reviewer_id still NULL) if created beforehand.
        reviewer_user = users.get_or_create(r.reviewer)
        verified_user = users.get_or_create(r.verified_by) if r.verified_by else None
        row = rids.get(review, r.rid)
        if row is None:
            row = RID(review=review, rid_str=r.rid, reviewer=reviewer_user)
            session.add(row)
        row.reviewer = reviewer_user
        row.created = r.created
        row.anchor_json = r.anchor.to_dict()
        row.kind = r.kind.value
        row.type = _value(r.type)
        row.severity = _value(r.severity)
        row.status = r.status.value
        row.comment = r.comment
        row.reply = r.reply
        row.disposition = _value(r.disposition)
        row.resolution = r.resolution
        row.verified_by = verified_user
        row.verified_on = r.verified_on
        row.ai_drafted = r.ai_drafted
        session.flush()
        rows[r.rid] = row

    for r in rtd.rids:  # second pass: master links (duplicates are derived)
        rows[r.rid].master_id = rows[r.master].id if r.master else None
    session.flush()
