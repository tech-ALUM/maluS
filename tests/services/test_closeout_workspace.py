"""Step 02 Task 1: ``save_closeout_version`` — a closeout edit is a new
document version linked to the accepted RIDs it resolves (v3 closeout
workspace). Traceability by construction: no RIDs selected -> no save;
unchanged content -> no save; a non-accepted RID -> no save. Saving never
advances a RID's status (``implement`` does that, explicitly, once linked).

Fixtures follow ``tests/services/test_phases.py``'s style, seeded through the
real pipeline per ``tests/services/test_disposition_immutable.py``'s
``_seed_closed`` (freeze -> reviewer copy (submitted) -> harvest -> answer ->
accept_disposition -> start_closeout), not the force-set-status shortcut,
since this test needs the *accepted* vs *rejected* split on real RIDs.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from malus import services as svc
from malus.constants import Disposition
from malus.repo import RidRepo, UserRepo, VersionRepo

OWNER_NAME = "A. Boffi"
REVIEWER_NAME = "F. Miccoli"

BASELINE = (
    "## Section 1\n\nFinding text body number 1.\n\n"
    "## Section 2\n\nFinding text body number 2.\n\n"
    "## Section 3\n\nFinding text body number 3.\n"
)
COPY = (
    "## Section 1\n\nFinding text body number 1. {COMM: reviewer note 1}\n\n"
    "## Section 2\n\nFinding text body number 2. {COMM: reviewer note 2}\n\n"
    "## Section 3\n\nFinding text body number 3. {COMM: reviewer note 3}\n"
)

# harvested in baseline order (rid_prefix="SIN-SRS", matches test_phases.py's RID_ID)
RID_A = "SIN-SRS-0001"
RID_B = "SIN-SRS-0002"
REJECTED_RID = "SIN-SRS-0003"
ACCEPTED_RID = RID_A


@pytest.fixture
def owner(session: Session):
    return UserRepo(session).get_or_create(OWNER_NAME)


def _seed(session: Session, review_id: str, owner):
    """freeze -> reviewer copy (submitted) -> harvest -> answer + accept each
    of the 3 harvested RIDs: RID_A/RID_B accepted, REJECTED_RID rejected."""
    review = svc.create_review(
        session,
        review_id=review_id,
        document_name="baseline.md",
        owner=OWNER_NAME,
        reviewers=[REVIEWER_NAME],
        rid_prefix="SIN-SRS",
    )
    svc.freeze_baseline(session, review, BASELINE, by=owner)
    svc.add_reviewer_copy(session, review, REVIEWER_NAME, COPY, submitted=True)
    svc.harvest(session, review)
    svc.answer(session, review, RID_A, disposition=Disposition.ACCEPTED, by=owner)
    svc.accept_disposition(session, review, RID_A, reviewer=REVIEWER_NAME)
    svc.answer(session, review, RID_B, disposition=Disposition.ACCEPTED, by=owner)
    svc.accept_disposition(session, review, RID_B, reviewer=REVIEWER_NAME)
    svc.answer(session, review, REJECTED_RID, disposition=Disposition.REJECTED, by=owner)
    svc.accept_disposition(session, review, REJECTED_RID, reviewer=REVIEWER_NAME)
    session.commit()
    return review


@pytest.fixture
def closeout_review(session: Session, owner):
    """A CLOSEOUT-phase review: RID_A/RID_B (== ACCEPTED_RID) accepted+closed,
    REJECTED_RID rejected+closed, one version on record (the baseline)."""
    review = _seed(session, "SIN-SRS-R1", owner)
    svc.start_closeout(session, review, by=owner)
    session.commit()
    return review


@pytest.fixture
def in_review_review(session: Session, owner):
    """Same seed, still IN_REVIEW (no ``start_closeout``) — wrong-phase case."""
    return _seed(session, "SIN-SRS-R2", owner)


# --------------------------------------------------------------------------- #
# save_closeout_version
# --------------------------------------------------------------------------- #


def test_save_requires_a_rid(session: Session, closeout_review, owner):
    with pytest.raises(ValueError):
        svc.save_closeout_version(
            session, closeout_review, "# doc v2", rid_ids=[], by=owner
        )


def test_save_rejects_unchanged_content(session: Session, closeout_review, owner):
    latest = VersionRepo(session).latest(closeout_review)
    with pytest.raises(ValueError):
        svc.save_closeout_version(
            session, closeout_review, latest.content, rid_ids=[ACCEPTED_RID], by=owner
        )


def test_save_rejects_non_accepted_rid(session: Session, closeout_review, owner):
    with pytest.raises(ValueError):
        svc.save_closeout_version(
            session, closeout_review, "# doc v2", rid_ids=[REJECTED_RID], by=owner
        )


def test_save_rejects_unknown_rid(session: Session, closeout_review, owner):
    with pytest.raises(ValueError):
        svc.save_closeout_version(
            session, closeout_review, "# doc v2", rid_ids=["SIN-SRS-9999"], by=owner
        )


def test_save_links_every_selected_rid(session: Session, closeout_review, owner):
    version = svc.save_closeout_version(
        session, closeout_review, "# doc v2", rid_ids=[RID_A, RID_B], by=owner
    )
    for rid in (RID_A, RID_B):
        row = RidRepo(session).get(closeout_review, rid)
        assert any(c.version_id == version.id for c in RidRepo(session).changes_for(row))
        assert row.status == "closed"  # saving does NOT advance status


def test_save_forbidden_in_review_phase(session: Session, in_review_review, owner):
    with pytest.raises(svc.PhaseError):
        svc.save_closeout_version(
            session, in_review_review, "# doc v2", rid_ids=[RID_A], by=owner
        )


# --------------------------------------------------------------------------- #
# rid_has_change (Task 2 dependency): a public wrapper over the traceability
# check already used internally by ``implement``.
# --------------------------------------------------------------------------- #


def test_rid_has_change_reflects_linked_saves(session: Session, closeout_review, owner):
    assert svc.rid_has_change(session, closeout_review, RID_A) is False
    svc.save_closeout_version(
        session, closeout_review, "# doc v2", rid_ids=[RID_A], by=owner
    )
    assert svc.rid_has_change(session, closeout_review, RID_A) is True
