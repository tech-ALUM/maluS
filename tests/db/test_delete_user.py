"""Service-level tests for hard-delete of a user (v1.3): every reference is
reassigned (owned reviews to a chosen new owner; findings/verifications/versions/
audit to the shared 'Deleted user' sentinel) before the row is removed."""

from __future__ import annotations

from sqlmodel import select

from malus import services as svc
from malus.db.models import RID, AuditLog, DocumentVersion, ReviewerCopy, ReviewMember, User
from malus.repo import UserRepo

R = "SIN-SRS-R1"
BASELINE = "# Doc\n\nThe timeout shall be configurable.\n"
COPY = "# Doc\n\nThe timeout shall be configurable. {COMM|type=technical|sev=major: bound it}\n"
SENTINEL = "deleted-user"


def _seed_rid_by(session, review, reviewer_user, display):
    svc.add_reviewer_copy(session, review, display, COPY)
    svc.harvest(session, review, by=reviewer_user)
    return session.exec(select(RID).where(RID.review_id == review.id)).first()


def test_delete_user_reassigns_attributions_to_sentinel(session):
    users = UserRepo(session)
    owner = users.get_or_create("A. Boffi", username="owner")
    rev = users.get_or_create("R. Ev", username="rev")
    review = svc.create_review(
        session, review_id=R, document_name="d.md", owner="A. Boffi", reviewers=["R. Ev"]
    )
    svc.freeze_baseline(session, review, BASELINE, by=owner)
    rid = _seed_rid_by(session, review, rev, "R. Ev")  # authored by rev; harvest audited to rev
    rid.verified_by_id = rev.id  # simulate rev having verified something
    session.add(rid)
    version = svc.save_version(session, review, BASELINE + "\nedit\n", by=rev)  # created by rev
    session.flush()
    rev_id = rev.id

    svc.delete_user(session, rev, new_owners={}, by=owner)  # rev owns no review
    session.flush()

    sentinel = session.exec(select(User).where(User.username == SENTINEL)).first()
    assert sentinel is not None and sentinel.is_active is False
    assert session.exec(select(User).where(User.username == "rev")).first() is None  # gone
    assert rid.reviewer_id == sentinel.id and rid.verified_by_id == sentinel.id  # anonymized
    assert version.created_by_id == sentinel.id
    # audit entries preserved but no longer point at the deleted user
    actors = [a.actor_id for a in session.exec(select(AuditLog)).all()]
    assert rev_id not in actors and sentinel.id in actors
    # transient rows removed
    assert session.exec(select(ReviewMember).where(ReviewMember.user_id == rev_id)).first() is None
    assert session.exec(select(ReviewerCopy).where(ReviewerCopy.user_id == rev_id)).first() is None


def test_delete_user_reassigns_owned_review_to_new_owner(session):
    users = UserRepo(session)
    owner = users.get_or_create("A. Boffi", username="owner")
    succ = users.get_or_create("Succ Essor", username="succ")
    review = svc.create_review(
        session, review_id=R, document_name="d.md", owner="A. Boffi", reviewers=[]
    )
    svc.freeze_baseline(session, review, BASELINE, by=owner)
    session.flush()

    svc.delete_user(session, owner, new_owners={review.id: succ}, by=succ)
    session.flush()

    session.refresh(review)
    assert review.owner_id == succ.id  # ownership transferred
    members = session.exec(select(ReviewMember).where(ReviewMember.review_id == review.id)).all()
    assert any(m.user_id == succ.id and m.role == "owner" for m in members)  # succ is owner member
    assert session.exec(select(User).where(User.username == "owner")).first() is None
