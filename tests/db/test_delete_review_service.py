"""Service-level test for deleting a whole review (v1.5): every dependent row is
removed in FK-safe order, then the Review; audit keeps a delete_review entry."""

from __future__ import annotations

from sqlmodel import select

from malus import services as svc
from malus.db.models import (
    RID,
    AuditLog,
    Document,
    DocumentVersion,
    Review,
    ReviewerCopy,
    ReviewerNote,
    ReviewMember,
    RidChange,
)
from malus.repo import ReviewerNoteRepo, UserRepo

R = "SIN-SRS-R1"
BASELINE = "# Doc\n\nThe timeout shall be configurable.\n"
COPY = "# Doc\n\nThe timeout shall be configurable. {COMM|type=technical|sev=major: bound it}\n"


def test_delete_review_removes_all_dependent_rows(session):
    users = UserRepo(session)
    owner = users.get_or_create("A. Boffi", username="owner")
    rev = users.get_or_create("R. Ev", username="rev")
    review = svc.create_review(
        session, review_id=R, document_name="d.md", owner="A. Boffi", reviewers=["R. Ev"]
    )
    svc.freeze_baseline(session, review, BASELINE, by=owner)
    svc.add_reviewer_copy(session, review, "R. Ev", COPY)
    svc.harvest(session, review, by=rev)  # -> a RID
    version = svc.save_version(session, review, BASELINE + "\nedit\n", by=owner)
    ReviewerNoteRepo(session).upsert(review, rev, "12", "check later")  # a private note
    rid = session.exec(select(RID).where(RID.review_id == review.id)).first()
    session.add(RidChange(rid_id=rid.id, version_id=version.id, note="impl"))  # a RID change
    session.flush()
    review_id = review.id

    svc.delete_review(session, review, by=owner)
    session.flush()

    assert session.exec(select(Review).where(Review.id == review_id)).first() is None
    # every child table is empty of this review's rows (they belonged only to it)
    for model in (RID, RidChange, ReviewerCopy, ReviewerNote, ReviewMember, DocumentVersion, Document):
        assert session.exec(select(model)).first() is None, model.__name__
    # the audit trail keeps a delete_review entry
    assert any(a.action == "delete_review" for a in session.exec(select(AuditLog)).all())
