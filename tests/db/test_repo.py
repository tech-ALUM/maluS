"""Repository layer over SQLModel sessions (v1 Step 2)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session

from malus.constants import Role
from malus.db.models import ReviewStatus
from malus.repo import (
    AuditRepo,
    ReviewRepo,
    RidRepo,
    UserRepo,
    VersionRepo,
    content_hash,
)


def test_content_hash_is_sha256_of_utf8():
    import hashlib

    assert content_hash("# SRS\n") == hashlib.sha256(b"# SRS\n").hexdigest()


def test_user_repo_get_or_create_deduplicates(session: Session):
    users = UserRepo(session)
    a = users.get_or_create("F. Miccoli")
    b = users.get_or_create("F. Miccoli")
    assert a.id == b.id
    assert a.display_name == "F. Miccoli"
    assert users.by_username(a.username) is not None


def test_review_repo_create_get_and_members(session: Session):
    users, reviews = UserRepo(session), ReviewRepo(session)
    owner = users.get_or_create("A. Boffi")
    review = reviews.create(
        "SIN-SRS-R1", owner=owner, document_name="baseline.md", created=dt.date(2026, 7, 3)
    )
    reviews.add_member(review, owner, Role.OWNER.value)
    reviews.add_member(review, users.get_or_create("F. Miccoli"), Role.REVIEWER.value)
    session.commit()

    got = reviews.get("SIN-SRS-R1")
    assert got is not None
    assert got.status == ReviewStatus.DRAFT.value
    assert got.owner.display_name == "A. Boffi"
    assert got.documents[0].name == "baseline.md"
    assert {m.role for m in got.members} == {"owner", "reviewer"}


def test_version_repo_freeze_is_baseline_hash_pinned(session: Session):
    users, reviews, versions = UserRepo(session), ReviewRepo(session), VersionRepo(session)
    owner = users.get_or_create("A. Boffi")
    review = reviews.create("SIN-SRS-R1", owner=owner, document_name="baseline.md")
    base = versions.freeze(review, "# SRS\nbody\n", by=owner)
    session.commit()

    assert base.is_baseline is True
    assert base.ordinal == 1
    assert base.content_hash == content_hash("# SRS\nbody\n")
    assert versions.baseline(review).id == base.id


def test_version_repo_add_version_increments_ordinal(session: Session):
    users, reviews, versions = UserRepo(session), ReviewRepo(session), VersionRepo(session)
    review = reviews.create("R", owner=users.get_or_create("O"), document_name="d.md")
    versions.freeze(review, "base\n")
    v2 = versions.add_version(review, "working\n")
    session.commit()

    assert v2.ordinal == 2
    assert v2.is_baseline is False
    assert versions.latest(review).id == v2.id


def test_rid_repo_get_and_list(session: Session):
    from malus.db.models import RID

    users, reviews = UserRepo(session), ReviewRepo(session)
    review = reviews.create("R", owner=users.get_or_create("O"), document_name="d.md")
    reviewer = users.get_or_create("Rev")
    session.add(
        RID(review=review, rid_str="R-0001", reviewer=reviewer, kind="COMM", status="open")
    )
    session.commit()

    rids = RidRepo(session)
    assert rids.get(review, "R-0001") is not None
    assert rids.get(review, "R-9999") is None
    assert [r.rid_str for r in rids.list(review)] == ["R-0001"]


def test_rid_repo_add_change_links_rid_to_version(session: Session):
    from malus.db.models import RID

    users, reviews, versions = UserRepo(session), ReviewRepo(session), VersionRepo(session)
    review = reviews.create("R", owner=users.get_or_create("O"), document_name="d.md")
    versions.freeze(review, "base\n")
    v2 = versions.add_version(review, "fixed\n")
    reviewer = users.get_or_create("Rev")
    rid = RID(review=review, rid_str="R-0001", reviewer=reviewer, kind="COMM", status="open")
    session.add(rid)
    session.commit()

    rids = RidRepo(session)
    change = rids.add_change(rid, v2, note="fixed it")
    session.commit()
    assert change.version.ordinal == 2
    assert [c.id for c in rids.changes_for(rid)] == [change.id]


def test_audit_repo_log(session: Session):
    users, reviews, audit = UserRepo(session), ReviewRepo(session), AuditRepo(session)
    actor = users.get_or_create("A. Boffi")
    review = reviews.create("R", owner=actor, document_name="d.md")
    session.commit()
    entry = audit.log(action="freeze", target="review:R", actor=actor, detail={"ordinal": 1})
    session.commit()

    assert entry.action == "freeze"
    assert entry.actor.display_name == "A. Boffi"
    assert audit.list(action="freeze")[0].detail_json == {"ordinal": 1}
