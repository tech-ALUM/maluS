"""Review phases + phase-gated services (v3): DRAFT -> IN_REVIEW -> CLOSEOUT ->
FINALIZED, plus the reviewer verdicts ``accept_disposition``/``request_changes``
that replace v2's direct ``answer -> verify``.

Modeled on ``tests/db/test_services.py``'s session/review fixtures — the
service layer sits directly on the DB session, no git, no filesystem.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session

from malus import services as svc
from malus.constants import Disposition, Status
from malus.db.models import ReviewStatus
from malus.repo import ReviewRepo, RidRepo, UserRepo

RID_ID = "SIN-SRS-0001"


def _section(i: int) -> str:
    return f"## Section {i}\n\nFinding text body number {i}."


def _baseline(n: int) -> str:
    return "\n\n".join(_section(i) for i in range(1, n + 1)) + "\n"


def _copy(n: int) -> str:
    parts = [
        f"## Section {i}\n\nFinding text body number {i}. {{COMM: reviewer note {i}}}"
        for i in range(1, n + 1)
    ]
    return "\n\n".join(parts) + "\n"


# --------------------------------------------------------------------------- #
# fixtures — follow the tests/db/test_services.py style (a plain seed helper),
# but parameterized per the brief so each test drives its own phase/RID setup.
# --------------------------------------------------------------------------- #


@pytest.fixture
def owner_name() -> str:
    return "A. Boffi"


@pytest.fixture
def reviewer_name() -> str:
    return "F. Miccoli"


@pytest.fixture
def owner(session: Session, owner_name: str):
    return UserRepo(session).get_or_create(owner_name)


@pytest.fixture
def review_factory(session: Session, owner_name: str, reviewer_name: str):
    """Wraps ``svc.create_review``: a fresh DRAFT review, no baseline frozen."""

    def _make(**kwargs):
        kwargs.setdefault("review_id", "SIN-SRS-R1")
        kwargs.setdefault("document_name", "baseline.md")
        kwargs.setdefault("owner", owner_name)
        kwargs.setdefault("reviewers", [reviewer_name])
        kwargs.setdefault("rid_prefix", "SIN-SRS")
        review = svc.create_review(session, **kwargs)
        session.commit()
        return review

    return _make


@pytest.fixture
def review_with_rids(session: Session, review_factory, reviewer_name: str):
    """A frozen, harvested review with one RID per requested status.

    Freezes a baseline with one section per status, harvests one reviewer
    comment per section (real pipeline — every RID starts ``open``), then
    force-sets each RID's status through the repo (bypassing the real
    transitions, which the phase-gate tests exercise separately)."""

    def _make(statuses: list[str], **factory_kwargs):
        review = review_factory(**factory_kwargs)
        n = len(statuses)
        svc.freeze_baseline(session, review, _baseline(n))
        svc.add_reviewer_copy(session, review, reviewer_name, _copy(n))
        svc.harvest(session, review)
        session.commit()
        rows = RidRepo(session).list(review)
        assert len(rows) == n
        for row, status in zip(rows, statuses):
            row.status = status
            # rid-schema.md invariants (report.validate): answered/closed/
            # implemented/verified all require a disposition; verified also
            # requires a (non-owner) verified_by.
            if status in (
                Status.ANSWERED.value,
                Status.CLOSED.value,
                Status.IMPLEMENTED.value,
                Status.VERIFIED.value,
            ):
                row.disposition = Disposition.ACCEPTED.value
                row.reply = "noted"
            if status == Status.VERIFIED.value:
                row.verified_by_id = row.reviewer_id
                row.verified_on = dt.date(2026, 7, 9)
            session.add(row)
        session.flush()
        session.commit()
        return review

    return _make


# --------------------------------------------------------------------------- #
# freeze_baseline: DRAFT -> IN_REVIEW
# --------------------------------------------------------------------------- #


def test_freeze_moves_review_to_in_review(session: Session, review_factory):
    review = review_factory()  # created draft
    assert review.status == ReviewStatus.DRAFT.value
    svc.freeze_baseline(session, review, "# doc", by=None)
    assert review.status == ReviewStatus.IN_REVIEW.value


def test_freeze_requires_draft_phase(session: Session, review_factory):
    review = review_factory()
    svc.freeze_baseline(session, review, "# doc")
    with pytest.raises(svc.PhaseError):
        svc.freeze_baseline(session, review, "# doc v2")


# --------------------------------------------------------------------------- #
# closeout_gate + start_closeout
# --------------------------------------------------------------------------- #


def test_closeout_gate_requires_all_closed(session: Session, review_with_rids):
    review = review_with_rids(statuses=["open"])
    assert svc.closeout_gate(session, review)  # blocked: open RID
    review2 = review_with_rids(statuses=["closed", "withdrawn"], review_id="SIN-SRS-R2")
    assert svc.closeout_gate(session, review2) == []


def test_closeout_gate_requires_at_least_one_finding(session: Session, review_with_rids):
    review = review_with_rids(statuses=["withdrawn"])
    assert svc.closeout_gate(session, review)  # blocked: nothing to review


def test_closeout_gate_blocks_on_answered(session: Session, review_with_rids):
    review = review_with_rids(statuses=["closed", "answered"])
    errors = svc.closeout_gate(session, review)
    assert errors and "SIN-SRS-0002" in errors[0]


def test_start_closeout_sets_phase(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    assert review.status == ReviewStatus.CLOSEOUT.value


def test_start_closeout_blocked_while_findings_open(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["open"])
    with pytest.raises(svc.PhaseError):
        svc.start_closeout(session, review, by=owner)
    assert review.status == ReviewStatus.IN_REVIEW.value  # unchanged


def test_start_closeout_requires_in_review_phase(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.start_closeout(session, review, by=owner)  # already in closeout


# --------------------------------------------------------------------------- #
# reopen_review: the admin escape hatch, CLOSEOUT -> IN_REVIEW
# --------------------------------------------------------------------------- #


def test_reopen_review_returns_to_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    svc.reopen_review(session, review, by=owner)
    assert review.status == ReviewStatus.IN_REVIEW.value


def test_reopen_review_requires_closeout_phase(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    with pytest.raises(svc.PhaseError):
        svc.reopen_review(session, review, by=owner)


# --------------------------------------------------------------------------- #
# accept_disposition: reviewer closes a finding, IN_REVIEW only
# --------------------------------------------------------------------------- #


def test_accept_disposition_only_in_review_phase(
    session: Session, review_with_rids, reviewer_name
):
    review = review_with_rids(statuses=["answered"])
    ReviewRepo(session).set_status(review, ReviewStatus.CLOSEOUT.value)  # force phase
    with pytest.raises(svc.PhaseError):
        svc.accept_disposition(session, review, RID_ID, reviewer=reviewer_name)


def test_accept_disposition_closes_the_rid(session: Session, review_with_rids, reviewer_name):
    review = review_with_rids(statuses=["answered"])
    row = svc.accept_disposition(session, review, RID_ID, reviewer=reviewer_name)
    assert row.status == Status.CLOSED.value


# --------------------------------------------------------------------------- #
# implement / verify / link_change / request_changes: CLOSEOUT only
# --------------------------------------------------------------------------- #


def test_verify_only_in_closeout(session: Session, review_with_rids, reviewer_name):
    review = review_with_rids(statuses=["implemented"])  # phase still in_review
    with pytest.raises(svc.PhaseError):
        svc.verify(session, review, RID_ID, reviewer=reviewer_name)


def test_implement_only_in_closeout(session: Session, review_with_rids):
    review = review_with_rids(statuses=["closed"])  # phase still in_review
    with pytest.raises(svc.PhaseError):
        svc.implement(session, review, RID_ID)


def test_link_change_only_in_closeout(session: Session, review_with_rids):
    review = review_with_rids(statuses=["closed"])
    version = svc.save_version(session, review, "# doc v2")
    with pytest.raises(svc.PhaseError):
        svc.link_change(session, review, RID_ID, version)


def test_request_changes_only_in_closeout(session: Session, review_with_rids, reviewer_name):
    review = review_with_rids(statuses=["implemented"])  # phase still in_review
    with pytest.raises(svc.PhaseError):
        svc.request_changes(session, review, RID_ID, reviewer=reviewer_name, reason="rework")


def test_request_changes_sends_implemented_back_to_closed(
    session: Session, review_with_rids, reviewer_name, owner
):
    review = review_with_rids(statuses=["implemented"])
    ReviewRepo(session).set_status(review, ReviewStatus.CLOSEOUT.value)
    row = svc.request_changes(
        session, review, RID_ID, reviewer=reviewer_name, reason="not quite right"
    )
    assert row.status == Status.CLOSED.value
    assert "not quite right" in row.reply


# --------------------------------------------------------------------------- #
# other IN_REVIEW-gated services: add_reviewer_copy, harvest, answer,
# update_rid, discard_disposition_draft, apply_suggestions, reopen
# --------------------------------------------------------------------------- #


def test_harvest_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.harvest(session, review)


def test_answer_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed", "closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.answer(session, review, "SIN-SRS-0002", disposition=Disposition.ACCEPTED)


def test_apply_suggestions_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.apply_suggestions(session, review)


def test_triage_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.triage(session, review)


def test_reopen_rid_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.reopen(session, review, RID_ID, reviewer="F. Miccoli", reason="reconsider")


def test_add_reviewer_copy_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.add_reviewer_copy(session, review, "F. Miccoli", "some content")


def test_update_rid_blocked_outside_in_review(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.update_rid(session, review, RID_ID, resolution="done")


def test_discard_disposition_draft_blocked_outside_in_review(
    session: Session, review_with_rids, owner
):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.discard_disposition_draft(session, review, RID_ID)


# --------------------------------------------------------------------------- #
# finalize: v3 gate — CLOSEOUT phase, accepted -> verified, rejected/deferred
# -> closed
# --------------------------------------------------------------------------- #


def test_finalize_requires_closeout_phase(session: Session, review_with_rids):
    review = review_with_rids(statuses=["verified"])  # phase still in_review
    with pytest.raises(svc.PhaseError):
        svc.finalize(session, review)


def test_finalize_blocks_accepted_but_not_yet_verified(
    session: Session, review_with_rids, owner
):
    review = review_with_rids(statuses=["closed"])  # accepted, awaiting implement/verify
    svc.start_closeout(session, review, by=owner)
    errors = svc.finalize(session, review)
    assert errors and RID_ID in errors[0]


def test_finalize_accepts_verified_and_rejected_closed(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["verified", "closed", "withdrawn"])
    row2 = RidRepo(session).list(review)[1]
    row2.disposition = Disposition.REJECTED.value  # closed + rejected: a legitimate finalize state
    session.add(row2)
    session.flush()
    session.commit()
    svc.start_closeout(session, review, by=owner)
    assert svc.finalize(session, review) == []
    assert review.status == ReviewStatus.FINALIZED.value
