"""Reviewer-side verification and reopen (the pure lifecycle core).

DB-backed verify/reopen/traceability are covered in tests/db/test_services.py;
these exercise the storage-agnostic helpers directly.
"""

import datetime as dt

import pytest

from malus.constants import Disposition, Kind, Status
from malus.lifecycle import pending_for_reviewer, reopen_rid, verify_rid
from malus.models import RID, RTD, Meta, TransitionError


def _rtd(rids):
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


def _rid(rid_id, disp=None, status=Status.OPEN, reviewer="F. Miccoli"):
    return RID(
        rid=rid_id,
        reviewer=reviewer,
        created=dt.date(2026, 7, 3),
        kind=Kind.COMM,
        status=status,
        disposition=disp,
        comment="finding text",
    )


def test_reviewer_verifies_own_implemented_rid():
    rtd = _rtd([_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    verify_rid(rtd, "SIN-SRS-0001", reviewer="F. Miccoli", on=dt.date(2026, 7, 9))
    assert rtd.rids[0].status is Status.VERIFIED
    assert rtd.rids[0].verified_by == "F. Miccoli"


def test_owner_identity_cannot_verify():
    rtd = _rtd([_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    with pytest.raises(TransitionError):
        verify_rid(rtd, "SIN-SRS-0001", reviewer="A. Boffi")  # the owner's name
    assert rtd.rids[0].status is Status.IMPLEMENTED


def test_reviewer_cannot_verify_another_reviewers_rid():
    rtd = _rtd([_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    with pytest.raises(TransitionError):
        verify_rid(rtd, "SIN-SRS-0001", reviewer="R. Bianchi")


def test_moderator_may_verify_on_behalf():
    rtd = _rtd([_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    verify_rid(rtd, "SIN-SRS-0001", reviewer="R. Bianchi", moderator=True)
    assert rtd.rids[0].status is Status.VERIFIED


def test_reopen_sends_back_to_open_with_reason():
    rtd = _rtd([_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    reopen_rid(rtd, "SIN-SRS-0001", reviewer="F. Miccoli", reason="fix is incomplete")
    assert rtd.rids[0].status is Status.OPEN
    assert "fix is incomplete" in (rtd.rids[0].reply or "")


def test_reopen_requires_a_reason():
    rtd = _rtd([_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    with pytest.raises(ValueError):
        reopen_rid(rtd, "SIN-SRS-0001", reviewer="F. Miccoli", reason="   ")


def test_pending_lists_only_answered_or_implemented():
    rtd = _rtd(
        [
            _rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED),
            _rid("SIN-SRS-0002", status=Status.OPEN),
        ]
    )
    assert [x.rid for x in pending_for_reviewer(rtd, "F. Miccoli")] == ["SIN-SRS-0001"]
