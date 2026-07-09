"""Status-transition enforcement, incl. the closure-authority invariant (D3).

The owner-cannot-verify test is the proof that owner self-certification is
structurally impossible; it is written before the enforcement exists.
"""

import datetime as dt

import pytest

from malus.constants import Disposition, Kind, Role, Status
from malus.models import RID, TransitionError, transition


def _rid(status: Status = Status.OPEN, reviewer: str = "F. Miccoli") -> RID:
    return RID(
        rid="SIN-SRS-0042",
        reviewer=reviewer,
        created=dt.date(2026, 7, 3),
        kind=Kind.COMM,
        status=status,
    )


# --- Closure-authority invariant (the critical control, D3) ---


def test_owner_can_never_verify() -> None:
    """From any pre-state, the owner cannot set a RID to verified."""
    for pre in (Status.ANSWERED, Status.IMPLEMENTED):
        rid = _rid(status=pre)
        with pytest.raises(TransitionError):
            transition(rid, Status.VERIFIED, actor_role=Role.OWNER, actor_name="A. Boffi")
        assert rid.status is pre  # left untouched


def test_ai_can_never_verify_even_in_reviewer_seat() -> None:
    rid = _rid(status=Status.IMPLEMENTED)
    with pytest.raises(TransitionError):
        transition(
            rid,
            Status.VERIFIED,
            actor_role=Role.REVIEWER,
            actor_name="F. Miccoli",
            actor_is_ai=True,
        )
    assert rid.status is Status.IMPLEMENTED


def test_reviewer_verifies_own_rid_and_is_stamped() -> None:
    rid = _rid(status=Status.IMPLEMENTED, reviewer="F. Miccoli")
    transition(
        rid,
        Status.VERIFIED,
        actor_role=Role.REVIEWER,
        actor_name="F. Miccoli",
        on=dt.date(2026, 7, 9),
    )
    assert rid.status is Status.VERIFIED
    assert rid.verified_by == "F. Miccoli"
    assert rid.verified_on == dt.date(2026, 7, 9)


def test_reviewer_cannot_verify_another_reviewers_rid() -> None:
    rid = _rid(status=Status.IMPLEMENTED, reviewer="F. Miccoli")
    with pytest.raises(TransitionError):
        transition(rid, Status.VERIFIED, actor_role=Role.REVIEWER, actor_name="R. Bianchi")
    assert rid.status is Status.IMPLEMENTED


def test_moderator_may_verify_on_behalf() -> None:
    rid = _rid(status=Status.IMPLEMENTED, reviewer="F. Miccoli")
    transition(rid, Status.VERIFIED, actor_role=Role.MODERATOR, actor_name="Moderator")
    assert rid.status is Status.VERIFIED
    assert rid.verified_by == "Moderator"


# --- Status graph ---


def test_legal_forward_path() -> None:
    rid = _rid(status=Status.OPEN)
    rid.disposition = Disposition.ACCEPTED  # a decision is required to answer
    transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.ANSWERED
    transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.IMPLEMENTED
    transition(rid, Status.VERIFIED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.VERIFIED


def test_rejected_or_deferred_path_skips_implemented() -> None:
    rid = _rid(status=Status.ANSWERED)
    rid.disposition = Disposition.REJECTED
    transition(rid, Status.VERIFIED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.VERIFIED


def test_answering_requires_a_disposition() -> None:
    rid = _rid(status=Status.OPEN)  # disposition is None
    with pytest.raises(TransitionError):
        transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.OPEN


def test_only_accepted_may_be_implemented() -> None:
    rid = _rid(status=Status.ANSWERED)
    rid.disposition = Disposition.REJECTED
    with pytest.raises(TransitionError):
        transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    rid.disposition = Disposition.ACCEPTED
    transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.IMPLEMENTED


def test_answered_to_verified_only_for_rejected_or_deferred() -> None:
    rid = _rid(status=Status.ANSWERED)
    rid.disposition = Disposition.ACCEPTED  # accepted must go through implemented
    with pytest.raises(TransitionError):
        transition(rid, Status.VERIFIED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.ANSWERED


@pytest.mark.parametrize("target", [Status.VERIFIED, Status.IMPLEMENTED])
def test_illegal_transition_from_open(target: Status) -> None:
    rid = _rid(status=Status.OPEN)
    with pytest.raises(TransitionError):
        transition(rid, target, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.OPEN


def test_no_transition_out_of_terminal_state() -> None:
    rid = _rid(status=Status.VERIFIED)
    with pytest.raises(TransitionError):
        transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name="A. Boffi")


# --- Withdraw (reviewer-only, from open only) ---


def test_reviewer_withdraws_own_open_rid() -> None:
    rid = _rid(status=Status.OPEN, reviewer="F. Miccoli")
    transition(rid, Status.WITHDRAWN, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.WITHDRAWN


def test_owner_cannot_withdraw() -> None:
    rid = _rid(status=Status.OPEN)
    with pytest.raises(TransitionError):
        transition(rid, Status.WITHDRAWN, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.OPEN


def test_cannot_withdraw_once_past_open() -> None:
    rid = _rid(status=Status.ANSWERED, reviewer="F. Miccoli")
    with pytest.raises(TransitionError):
        transition(rid, Status.WITHDRAWN, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.ANSWERED
