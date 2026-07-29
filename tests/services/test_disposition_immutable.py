"""v3 service guard: a settled disposition (status past `answered`) is
immutable — changing it goes through the formal reopen. Resolution edits stay
legal in closeout (they record what was implemented)."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from malus import services as svc
from malus.constants import Disposition
from malus.models import TransitionError

BASELINE = "# Doc\n\nThe timeout shall be short.\n"
COPY = (
    "# Doc\n\nThe timeout shall be short."
    "{COMM|type=technical|sev=major: bound it}\n"
)


def _seed_closed(session: Session):
    review = svc.create_review(
        session, review_id="IM-R1", document_name="d.md",
        owner="own", reviewers=["rev"],
    )
    svc.freeze_baseline(session, review, BASELINE)
    svc.add_reviewer_copy(session, review, "rev", COPY, submitted=True)
    svc.harvest(session, review)
    rid = review.rids[0].rid_str
    svc.answer(session, review, rid, disposition=Disposition.ACCEPTED, reply="ok")
    svc.accept_disposition(session, review, rid, reviewer="rev")
    return review, rid


def test_answered_disposition_is_editable(session: Session):
    review = svc.create_review(
        session, review_id="IM-R2", document_name="d.md",
        owner="own", reviewers=["rev"],
    )
    svc.freeze_baseline(session, review, BASELINE)
    svc.add_reviewer_copy(session, review, "rev", COPY, submitted=True)
    svc.harvest(session, review)
    rid = review.rids[0].rid_str
    svc.answer(session, review, rid, disposition=Disposition.ACCEPTED)
    row = svc.update_rid(session, review, rid, disposition=Disposition.REJECTED)
    assert row.disposition == "rejected" and row.status == "answered"


def test_settled_disposition_is_immutable(session: Session):
    review, rid = _seed_closed(session)
    with pytest.raises(TransitionError, match="settled"):
        svc.update_rid(session, review, rid, disposition=Disposition.REJECTED)


def test_resolution_still_editable_in_closeout(session: Session):
    review, rid = _seed_closed(session)
    svc.start_closeout(session, review)
    row = svc.update_rid(session, review, rid, resolution="reworded §3")
    assert row.resolution == "reworded §3"
    assert row.disposition == "accepted"  # untouched
