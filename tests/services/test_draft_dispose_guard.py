"""v3 service guard: the owner may answer (dispose) only findings whose
reviewer has SUBMITTED their copy — a draft comment can still change."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from malus import services as svc
from malus.constants import Disposition

BASELINE = "# Doc\n\nThe timeout shall be short.\n"
COPY = (
    "# Doc\n\nThe timeout shall be short."
    "{COMM|type=technical|sev=major: bound it}\n"
)


def _seed(session: Session, *, submitted: bool):
    review = svc.create_review(
        session, review_id="DR-R1", document_name="d.md",
        owner="own", reviewers=["rev"],
    )
    svc.freeze_baseline(session, review, BASELINE)
    svc.add_reviewer_copy(session, review, "rev", COPY, submitted=submitted)
    svc.harvest(session, review)
    rid = review.rids[0].rid_str
    return review, rid


def test_answer_refused_while_copy_is_draft(session: Session):
    review, rid = _seed(session, submitted=False)
    with pytest.raises(ValueError, match="draft"):
        svc.answer(session, review, rid, disposition=Disposition.ACCEPTED)


def test_answer_allowed_once_submitted(session: Session):
    review, rid = _seed(session, submitted=True)
    row = svc.answer(session, review, rid, disposition=Disposition.ACCEPTED)
    assert row.status == "answered"
