"""Tests for rtd.yaml validation and generated review minutes."""

import datetime as dt

from malus.constants import Disposition, Kind, Severity, Status
from malus.models import RID, RTD, Meta
from malus.report import render_report, validate


def _rtd(rids, owner="A. Boffi"):
    return RTD(
        meta=Meta(
            review_id="SIN-SRS-R1",
            document="baseline.md",
            baseline_sha="abc1234",
            created=dt.date(2026, 7, 3),
            owner=owner,
            reviewers=["F. Miccoli", "R. Bianchi"],
        ),
        rids=rids,
    )


def _rid(rid_id, reviewer="F. Miccoli", status=Status.OPEN, disp=None, verified_by=None, master=None):
    return RID(
        rid=rid_id,
        reviewer=reviewer,
        created=dt.date(2026, 7, 3),
        kind=Kind.COMM,
        type=None,
        severity=Severity.MAJOR,
        status=status,
        disposition=disp,
        verified_by=verified_by,
        master=master,
        comment="finding text",
    )


def _verified(rid_id, by="F. Miccoli"):
    return _rid(rid_id, status=Status.VERIFIED, disp=Disposition.ACCEPTED, verified_by=by)


# --- validate ---


def test_validate_clean() -> None:
    assert validate(_rtd([_verified("SIN-SRS-0001")])) == []


def test_validate_flags_owner_as_verifier() -> None:
    errors = validate(_rtd([_verified("SIN-SRS-0001", by="A. Boffi")]))
    assert any("owner" in e for e in errors)


def test_validate_flags_verified_without_verifier() -> None:
    errors = validate(_rtd([_rid("SIN-SRS-0001", status=Status.VERIFIED, disp=Disposition.ACCEPTED)]))
    assert any("verified_by" in e for e in errors)


def test_validate_flags_answered_without_disposition() -> None:
    errors = validate(_rtd([_rid("SIN-SRS-0001", status=Status.ANSWERED)]))
    assert any("disposition" in e for e in errors)


def test_validate_flags_closed_without_disposition() -> None:
    """v3: a closed RID (reviewer accepted the disposition) must carry one."""
    errors = validate(_rtd([_rid("SIN-SRS-0001", status=Status.CLOSED)]))
    assert any("disposition" in e for e in errors)


def test_validate_flags_dangling_master() -> None:
    errors = validate(_rtd([_rid("SIN-SRS-0001", master="SIN-SRS-9999")]))
    assert any("master" in e for e in errors)


# --- render / write ---


def test_render_report_has_key_sections() -> None:
    text = render_report(_rtd([_verified("SIN-SRS-0001")]))
    for section in ("# Review Minutes — SIN-SRS-R1", "## Status", "## Per reviewer", "## Sources"):
        assert section in text


def test_render_report_settled_metric_counts_closed_verified_withdrawn() -> None:
    """v3: rejected/deferred findings terminate at 'closed' — the settled
    metric (formerly 'Closed (verified or withdrawn)') must count them too."""
    rids = [
        _verified("SIN-SRS-0001"),  # verified -> settled
        _rid("SIN-SRS-0002", status=Status.WITHDRAWN),  # withdrawn -> settled
        _rid("SIN-SRS-0003", status=Status.CLOSED, disp=Disposition.REJECTED),  # v3: closed -> settled
        _rid("SIN-SRS-0004", status=Status.OPEN),  # not settled
    ]
    text = render_report(_rtd(rids))
    assert "Settled (closed, verified or withdrawn): 3 / 4 (75%)" in text
    assert "Closed (verified or withdrawn)" not in text


def test_render_report_per_reviewer_settled_column() -> None:
    rids = [
        _rid("SIN-SRS-0001", reviewer="F. Miccoli", status=Status.CLOSED, disp=Disposition.REJECTED),
        _rid("SIN-SRS-0002", reviewer="F. Miccoli", status=Status.OPEN),
        _rid(
            "SIN-SRS-0003",
            reviewer="R. Bianchi",
            status=Status.VERIFIED,
            disp=Disposition.ACCEPTED,
            verified_by="R. Bianchi",
        ),
    ]
    text = render_report(_rtd(rids))
    assert "| Reviewer | Raised | Settled | Open |" in text
    assert "| F. Miccoli | 2 | 1 | 1 |" in text
    assert "| R. Bianchi | 1 | 1 | 0 |" in text
