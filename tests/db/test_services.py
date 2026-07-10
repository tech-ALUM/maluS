"""DB service layer: the whole v0 pipeline reproduced against the database
(v1 Step 2). The reused pure core is unchanged; these tests exercise the
DB-backed services built on it."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session

from malus import services as svc
from malus.constants import Disposition, Kind, Status
from malus.models import TransitionError
from malus.repo import RidRepo, VersionRepo

BASELINE = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

COPY_F = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout must have an upper bound to avoid an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format. {SUGG: "disk" -> "the configured store"}
"""

COPY_R = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout must have an upper bound to prevent an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format.
"""


def _seed(session: Session):
    review = svc.create_review(
        session,
        review_id="SIN-SRS-R1",
        document_name="baseline.md",
        owner="A. Boffi",
        reviewers=["F. Miccoli", "R. Bianchi"],
        rid_prefix="SIN-SRS",
        created=dt.date(2026, 7, 3),
    )
    svc.freeze_baseline(session, review, BASELINE)
    svc.add_reviewer_copy(session, review, "F. Miccoli", COPY_F)
    svc.add_reviewer_copy(session, review, "R. Bianchi", COPY_R)
    session.commit()
    return review


def test_create_and_freeze(session: Session):
    review = _seed(session)
    base = VersionRepo(session).baseline(review)
    assert base.is_baseline and base.content == BASELINE
    assert {m.role for m in review.members} == {"owner", "reviewer"}


def test_harvest_assigns_stable_ids_and_is_idempotent(session: Session):
    review = _seed(session)
    result = svc.harvest(session, review)
    session.commit()
    assert not result.violations
    rids = RidRepo(session).list(review)
    assert [r.rid_str for r in rids] == ["SIN-SRS-0001", "SIN-SRS-0002", "SIN-SRS-0003"]
    kinds = {r.rid_str: r.kind for r in rids}
    assert kinds["SIN-SRS-0003"] == Kind.SUGG.value  # the SUGG anchors later (logging)

    # Re-harvest: no churn, no new ids.
    svc.harvest(session, review)
    session.commit()
    assert [r.rid_str for r in RidRepo(session).list(review)] == [
        "SIN-SRS-0001",
        "SIN-SRS-0002",
        "SIN-SRS-0003",
    ]


def test_harvest_freeze_violation_is_reported(session: Session):
    review = svc.create_review(
        session, review_id="R", document_name="d.md", owner="O", reviewers=["Bad"]
    )
    svc.freeze_baseline(session, review, BASELINE)
    # edits baseline text (not a pure comment insertion)
    svc.add_reviewer_copy(session, review, "Bad", BASELINE.replace("configurable", "tunable"))
    session.commit()
    result = svc.harvest(session, review)
    assert any(v.reviewer == "Bad" for v in result.violations)


def test_triage_auto_clusters_similar_comments(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    session.commit()
    proposals, applied = svc.triage(session, review, auto=True)
    session.commit()
    assert applied >= 1
    dup = RidRepo(session).get(review, "SIN-SRS-0002")
    master = RidRepo(session).get(review, "SIN-SRS-0001")
    assert dup.master_id == master.id


def test_apply_suggestions_writes_new_version(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    session.commit()
    version, results = svc.apply_suggestions(session, review)
    session.commit()
    assert version.ordinal == 2 and not version.is_baseline
    assert "the configured store" in version.content
    assert any(r.applied for r in results)


def test_owner_answer_then_reviewer_verify(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    session.commit()
    svc.answer(session, review, "SIN-SRS-0001", disposition=Disposition.ACCEPTED, reply="Agreed.")
    session.commit()
    assert RidRepo(session).get(review, "SIN-SRS-0001").status == Status.ANSWERED.value

    # implement requires a linked change to a post-baseline version (traceability gate)
    with pytest.raises(ValueError):
        svc.implement(session, review, "SIN-SRS-0001")
    v = svc.save_version(session, review, BASELINE + "\nbounded.\n")
    svc.link_change(session, review, "SIN-SRS-0001", v, note="added bound")
    svc.implement(session, review, "SIN-SRS-0001")
    session.commit()
    assert RidRepo(session).get(review, "SIN-SRS-0001").status == Status.IMPLEMENTED.value

    # the owner may never verify (closure-authority invariant)
    with pytest.raises(TransitionError):
        svc.verify(session, review, "SIN-SRS-0001", reviewer="A. Boffi")

    # the RID's own reviewer verifies
    svc.verify(session, review, "SIN-SRS-0001", reviewer="F. Miccoli", on=dt.date(2026, 7, 9))
    session.commit()
    row = RidRepo(session).get(review, "SIN-SRS-0001")
    assert row.status == Status.VERIFIED.value
    assert row.verified_by.display_name == "F. Miccoli"


def test_traceability_flags_accepted_without_change(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    svc.answer(session, review, "SIN-SRS-0001", disposition=Disposition.ACCEPTED, reply="ok")
    session.commit()
    report = svc.check_traceability(session, review)
    assert "SIN-SRS-0001" in report.accepted_unreferenced
    assert not report.ok

    v = svc.save_version(session, review, BASELINE + "\nx\n")
    svc.link_change(session, review, "SIN-SRS-0001", v)
    session.commit()
    report = svc.check_traceability(session, review)
    assert "SIN-SRS-0001" not in report.accepted_unreferenced


def test_reopen_clears_verification(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    svc.answer(session, review, "SIN-SRS-0002", disposition=Disposition.REJECTED, reply="no")
    session.commit()
    svc.verify(session, review, "SIN-SRS-0002", reviewer="R. Bianchi")
    session.commit()
    svc.reopen(session, review, "SIN-SRS-0002", reviewer="R. Bianchi", reason="reconsider")
    session.commit()
    row = RidRepo(session).get(review, "SIN-SRS-0002")
    assert row.status == Status.OPEN.value
    assert row.verified_by_id is None


def test_finalize_refuses_until_closed_then_succeeds(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    session.commit()
    errors = svc.finalize(session, review)
    assert errors  # findings still open

    # reject + verify every RID (rejected/deferred go answered -> verified)
    for rid in RidRepo(session).list(review):
        svc.answer(session, review, rid.rid_str, disposition=Disposition.REJECTED, reply="n/a")
    session.commit()
    for rid in RidRepo(session).list(review):
        reviewer = rid.reviewer.display_name
        svc.verify(session, review, rid.rid_str, reviewer=reviewer)
    session.commit()
    assert svc.finalize(session, review) == []
    from malus.db.models import ReviewStatus

    assert review.status == ReviewStatus.FINALIZED.value


def test_report_renders_minutes(session: Session):
    review = _seed(session)
    svc.harvest(session, review)
    session.commit()
    errors, md = svc.report(session, review)
    assert errors == []
    assert "Review Minutes — SIN-SRS-R1" in md
