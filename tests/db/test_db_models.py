"""Schema tests: create/query the full review graph, relationships,
constraints, and enum ``.value`` round-trips.

The DB stores the *values* of the frozen domain enums in
``malus.constants`` (ADR 0002); these tests prove a stored value reconstructs
its enum member.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from malus.constants import CommentType, Disposition, Kind, Role, Severity, Status
from malus.db.models import (
    RID,
    AuditLog,
    Document,
    DocumentVersion,
    Review,
    ReviewerCopy,
    ReviewMember,
    ReviewStatus,
    RidChange,
    User,
)


def _make_graph(session: Session) -> Review:
    """Build one review with a version, a copy, a RID, a change and an audit row."""
    owner = User(username="aboffi", display_name="A. Boffi", email="a@example.com")
    reviewer = User(username="fmiccoli", display_name="F. Miccoli")
    review = Review(
        review_id_str="SIN-SRS-R1",
        title="SRS review",
        owner=owner,
        status=ReviewStatus.DRAFT.value,
        created=dt.date(2026, 7, 3),
    )
    doc = Document(review=review, name="reviews/SIN-SRS-R1/baseline.md")
    version = DocumentVersion(
        document=doc,
        ordinal=1,
        content="# SRS\n...",
        content_hash="9f1c2ab",
        is_baseline=True,
        created_by=owner,
    )
    copy = ReviewerCopy(
        review=review, user=reviewer, based_on_version=version, content="# SRS\n...{COMM}"
    )
    rid = RID(
        review=review,
        rid_str="SIN-SRS-0042",
        reviewer=reviewer,
        created=dt.date(2026, 7, 3),
        anchor_json={"section": "3.2.1", "quote": "…timeout…", "line_hint": 142},
        kind=Kind.COMM.value,
        type=CommentType.TECHNICAL.value,
        severity=Severity.MAJOR.value,
        status=Status.OPEN.value,
        comment="The timeout must be bounded.",
    )
    change = RidChange(rid=rid, version=version, note="bounded the timeout")
    audit = AuditLog(
        actor=owner, action="freeze", target="review:SIN-SRS-R1", detail_json={"ordinal": 1}
    )
    member = ReviewMember(review=review, user=reviewer, role=Role.REVIEWER.value)
    session.add_all([owner, reviewer, review, doc, version, copy, rid, change, audit, member])
    session.commit()
    return review


def test_create_and_query_full_review_graph(session: Session):
    review = _make_graph(session)
    review_id = review.id
    session.expire_all()

    got = session.get(Review, review_id)
    assert got is not None
    assert got.review_id_str == "SIN-SRS-R1"
    assert got.owner.display_name == "A. Boffi"
    assert len(got.documents) == 1
    assert len(got.documents[0].versions) == 1
    assert got.documents[0].versions[0].is_baseline is True
    assert got.documents[0].versions[0].content_hash == "9f1c2ab"
    assert len(got.reviewer_copies) == 1
    assert len(got.rids) == 1
    assert len(got.members) == 1
    # audit rows are queryable
    assert session.exec(select(AuditLog).where(AuditLog.action == "freeze")).one().target == (
        "review:SIN-SRS-R1"
    )


def test_relationships_navigable_both_ways(session: Session):
    review = _make_graph(session)
    session.expire_all()

    rid = session.exec(select(RID)).one()
    assert rid.review.review_id_str == "SIN-SRS-R1"
    assert rid.reviewer.display_name == "F. Miccoli"
    assert rid.anchor_json["line_hint"] == 142
    assert len(rid.changes) == 1
    assert rid.changes[0].version.ordinal == 1
    # version -> its implementing changes back-reference
    assert rid.changes[0].rid.rid_str == "SIN-SRS-0042"
    copy = session.exec(select(ReviewerCopy)).one()
    assert copy.based_on_version.is_baseline is True
    assert copy.user.username == "fmiccoli"


def test_master_duplicate_self_relationship(session: Session):
    review = _make_graph(session)
    master = session.exec(select(RID).where(RID.rid_str == "SIN-SRS-0042")).one()
    dup = RID(
        review_id=review.id,
        rid_str="SIN-SRS-0043",
        reviewer_id=master.reviewer_id,
        created=dt.date(2026, 7, 4),
        anchor_json={"section": None, "quote": None, "line_hint": None},
        kind=Kind.COMM.value,
        status=Status.OPEN.value,
        master=master,
    )
    session.add(dup)
    session.commit()
    session.expire_all()

    master = session.exec(select(RID).where(RID.rid_str == "SIN-SRS-0042")).one()
    assert [d.rid_str for d in master.duplicates] == ["SIN-SRS-0043"]
    dup = session.exec(select(RID).where(RID.rid_str == "SIN-SRS-0043")).one()
    assert dup.master.rid_str == "SIN-SRS-0042"


def test_unique_username(session: Session):
    session.add(User(username="dup", display_name="One"))
    session.commit()
    session.add(User(username="dup", display_name="Two"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_unique_rid_str_per_review(session: Session):
    review = _make_graph(session)
    session.add(
        RID(
            review_id=review.id,
            rid_str="SIN-SRS-0042",  # already used in this review
            reviewer_id=review.owner_id,
            created=dt.date(2026, 7, 3),
            anchor_json={},
            kind=Kind.COMM.value,
            status=Status.OPEN.value,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_unique_reviewer_copy_per_user(session: Session):
    review = _make_graph(session)
    version = session.exec(select(DocumentVersion)).one()
    reviewer = session.exec(select(User).where(User.username == "fmiccoli")).one()
    session.add(
        ReviewerCopy(
            review_id=review.id,
            user_id=reviewer.id,  # already has a copy in this review
            based_on_version_id=version.id,
            content="dup",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_enum_values_round_trip(session: Session):
    """Stored columns hold the enum ``.value``; the value reconstructs the member."""
    _make_graph(session)
    session.expire_all()
    rid = session.exec(select(RID).where(RID.rid_str == "SIN-SRS-0042")).one()

    # columns hold the plain string values ...
    assert rid.kind == "COMM"
    assert rid.type == "technical"
    assert rid.severity == "major"
    assert rid.status == "open"
    # ... and each reconstructs its frozen domain enum member
    assert Kind(rid.kind) is Kind.COMM
    assert CommentType(rid.type) is CommentType.TECHNICAL
    assert Severity(rid.severity) is Severity.MAJOR
    assert Status(rid.status) is Status.OPEN

    member = session.exec(select(ReviewMember)).one()
    assert Role(member.role) is Role.REVIEWER

    review = session.exec(select(Review)).one()
    assert ReviewStatus(review.status) is ReviewStatus.DRAFT


def test_optional_disposition_and_verification_fields(session: Session):
    """The owner/verifier FKs and disposition/verified_on are optional and settable."""
    review = _make_graph(session)
    reviewer = session.exec(select(User).where(User.username == "fmiccoli")).one()
    rid = session.exec(select(RID).where(RID.rid_str == "SIN-SRS-0042")).one()
    rid.disposition = Disposition.ACCEPTED.value
    rid.reply = "Agreed."
    rid.status = Status.VERIFIED.value
    rid.verified_by = reviewer
    rid.verified_on = dt.date(2026, 7, 10)
    session.add(rid)
    session.commit()
    session.expire_all()

    rid = session.exec(select(RID).where(RID.rid_str == "SIN-SRS-0042")).one()
    assert Disposition(rid.disposition) is Disposition.ACCEPTED
    assert rid.verified_by.display_name == "F. Miccoli"
    assert rid.verified_on == dt.date(2026, 7, 10)
    assert rid.ai_drafted is False
