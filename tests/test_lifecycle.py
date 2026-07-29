"""Status-transition enforcement, incl. the closure-authority invariant (D3).

The owner-cannot-verify test is the proof that owner self-certification is
structurally impossible; it is written before the enforcement exists.
"""

import datetime as dt

import pytest

from malus.constants import Disposition, Kind, Role, Status
from malus.lifecycle import accept_disposition_rid, reopen_rid, request_changes_rid
from malus.models import RID, RTD, ClosureAuthorityError, Meta, TransitionError, transition


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
    """v3: open -> answered -> closed -> implemented -> verified.

    ``closed`` is the reviewer's acceptance of the owner's disposition; only
    from there (and only for an accepted RID) may it become ``implemented``.
    """
    rid = _rid(status=Status.OPEN)
    rid.disposition = Disposition.ACCEPTED  # a decision is required to answer
    transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.ANSWERED
    transition(rid, Status.CLOSED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.CLOSED
    transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.IMPLEMENTED
    transition(rid, Status.VERIFIED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.VERIFIED


def test_rejected_or_deferred_path_terminates_at_closed() -> None:
    """v3: a rejected/deferred RID still closes, but can no longer reach
    ``verified`` — only an accepted RID continues on to implemented/verified."""
    rid = _rid(status=Status.ANSWERED)
    rid.disposition = Disposition.REJECTED
    transition(rid, Status.CLOSED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.CLOSED
    with pytest.raises(TransitionError):
        transition(rid, Status.VERIFIED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    assert rid.status is Status.CLOSED


def test_answering_requires_a_disposition() -> None:
    rid = _rid(status=Status.OPEN)  # disposition is None
    with pytest.raises(TransitionError):
        transition(rid, Status.ANSWERED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.OPEN


def test_only_accepted_may_be_implemented() -> None:
    """v3: 'implemented' is only reachable from 'closed', and only for a RID
    whose disposition is accepted."""
    rid = _rid(status=Status.ANSWERED)
    rid.disposition = Disposition.REJECTED
    with pytest.raises(TransitionError):  # answered -> implemented isn't in the graph at all
        transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    transition(rid, Status.CLOSED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    with pytest.raises(TransitionError):  # closed, but rejected — still not implementable
        transition(rid, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert rid.status is Status.CLOSED

    accepted = _rid(status=Status.ANSWERED)
    accepted.disposition = Disposition.ACCEPTED
    transition(accepted, Status.CLOSED, actor_role=Role.REVIEWER, actor_name="F. Miccoli")
    transition(accepted, Status.IMPLEMENTED, actor_role=Role.OWNER, actor_name="A. Boffi")
    assert accepted.status is Status.IMPLEMENTED


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


# --- accept_disposition_rid / request_changes_rid / reopen_rid (v3 lifecycle helpers) ---


def _rtd(rids: list[RID]) -> RTD:
    return RTD(
        meta=Meta(
            review_id="SIN-SRS-R1",
            document="doc.md",
            baseline_sha="abc1234",
            created=dt.date(2026, 7, 3),
            owner="A. Boffi",
            reviewers=["F. Miccoli"],
        ),
        rids=rids,
    )


def _rtd_answered() -> RTD:
    rid = _rid(status=Status.ANSWERED)
    rid.disposition = Disposition.ACCEPTED
    return _rtd([rid])


def _rtd_closed() -> RTD:
    rid = _rid(status=Status.CLOSED)
    rid.disposition = Disposition.ACCEPTED
    return _rtd([rid])


def _rtd_implemented() -> RTD:
    rid = _rid(status=Status.IMPLEMENTED)
    rid.disposition = Disposition.ACCEPTED
    return _rtd([rid])


def _rtd_verified() -> RTD:
    rid = _rid(status=Status.VERIFIED)
    rid.disposition = Disposition.ACCEPTED
    rid.verified_by = "F. Miccoli"
    rid.verified_on = dt.date(2026, 7, 9)
    return _rtd([rid])


def test_accept_disposition_closes() -> None:
    rtd = _rtd_answered()
    rid = accept_disposition_rid(rtd, "SIN-SRS-0042", reviewer="F. Miccoli")
    assert rid.status is Status.CLOSED


def test_accept_disposition_owner_refused() -> None:
    rtd = _rtd_answered()
    with pytest.raises(ClosureAuthorityError):
        accept_disposition_rid(rtd, "SIN-SRS-0042", reviewer=rtd.meta.owner)


def test_request_changes_needs_reason() -> None:
    rtd = _rtd_implemented()
    with pytest.raises(ValueError):
        request_changes_rid(rtd, "SIN-SRS-0042", reviewer="F. Miccoli", reason="  ")


def test_request_changes_reworks_implemented() -> None:
    rtd = _rtd_implemented()
    rid = request_changes_rid(
        rtd, "SIN-SRS-0042", reviewer="F. Miccoli", reason="heading untouched"
    )
    assert rid.status is Status.CLOSED
    assert "[changes requested by" in rid.reply


def test_request_changes_reworks_verified() -> None:
    rtd = _rtd_verified()
    rid = request_changes_rid(rtd, "SIN-SRS-0042", reviewer="F. Miccoli", reason="regressed")
    assert rid.status is Status.CLOSED and rid.verified_by is None


def test_reopen_from_closed() -> None:
    rtd = _rtd_closed()
    rid = reopen_rid(rtd, "SIN-SRS-0042", reviewer="F. Miccoli", reason="changed my mind")
    assert rid.status is Status.OPEN
