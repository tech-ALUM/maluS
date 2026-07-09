"""Traceability, reviewer-side verification, and reopen (needs a real git repo)."""

import datetime as dt
import subprocess

import pytest
from typer.testing import CliRunner

from malus.cli import app
from malus.constants import Disposition, Kind, Status
from malus.lifecycle import (
    check_traceability,
    pending_for_reviewer,
    reopen_rid,
    verify_rid,
)
from malus.models import RID, RTD, Meta, TransitionError


def _git(repo, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "doc.md").write_text("baseline")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "baseline")
    sha = subprocess.run(
        ["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    return r, sha


def _commit(repo, message: str) -> None:
    (repo / "doc.md").write_text((repo / "doc.md").read_text() + "\nx")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _rtd(sha, rids):
    return RTD(
        meta=Meta(
            review_id="SIN-SRS-R1",
            document="doc.md",
            baseline_sha=sha,
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


# --- traceability ---


def test_accepted_unreferenced_is_flagged(repo):
    r, sha = repo
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.ANSWERED)])
    report = check_traceability(rtd, r)
    assert report.accepted_unreferenced == ["SIN-SRS-0001"]
    assert not report.ok


def test_referenced_accepted_is_clean(repo):
    r, sha = repo
    _commit(r, "fix(doc): bound the timeout — SIN-SRS-0001")
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    report = check_traceability(rtd, r)
    assert report.accepted_unreferenced == []
    assert "SIN-SRS-0001" in report.referenced
    assert report.ok


def test_referenced_but_not_accepted_is_an_anomaly(repo):
    r, sha = repo
    _commit(r, "chore: mention SIN-SRS-0002 without accepting it")
    rtd = _rtd(sha, [_rid("SIN-SRS-0002", Disposition.REJECTED, Status.ANSWERED)])
    report = check_traceability(rtd, r)
    assert report.referenced_not_accepted == ["SIN-SRS-0002"]


# --- verification / reopen ---


def test_reviewer_verifies_own_implemented_rid(repo):
    r, sha = repo
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    verify_rid(rtd, "SIN-SRS-0001", reviewer="F. Miccoli", on=dt.date(2026, 7, 9))
    assert rtd.rids[0].status is Status.VERIFIED
    assert rtd.rids[0].verified_by == "F. Miccoli"


def test_owner_identity_cannot_verify(repo):
    r, sha = repo
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    with pytest.raises(TransitionError):
        verify_rid(rtd, "SIN-SRS-0001", reviewer="A. Boffi")  # the owner's name
    assert rtd.rids[0].status is Status.IMPLEMENTED


def test_reopen_sends_back_to_open_with_reason(repo):
    r, sha = repo
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    reopen_rid(rtd, "SIN-SRS-0001", reviewer="F. Miccoli", reason="fix is incomplete")
    assert rtd.rids[0].status is Status.OPEN
    assert "fix is incomplete" in (rtd.rids[0].reply or "")


def test_reopen_requires_a_reason(repo):
    r, sha = repo
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    with pytest.raises(ValueError):
        reopen_rid(rtd, "SIN-SRS-0001", reviewer="F. Miccoli", reason="   ")


def test_pending_lists_only_answered_or_implemented(repo):
    r, sha = repo
    rtd = _rtd(
        sha,
        [
            _rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED),
            _rid("SIN-SRS-0002", status=Status.OPEN),
        ],
    )
    assert [x.rid for x in pending_for_reviewer(rtd, "F. Miccoli")] == ["SIN-SRS-0001"]


def test_cli_verify_check_blocks_then_passes(repo):
    r, sha = repo
    rtd = _rtd(sha, [_rid("SIN-SRS-0001", Disposition.ACCEPTED, Status.IMPLEMENTED)])
    (r / "rtd.yaml").write_text(rtd.to_yaml(), encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(app, ["verify", "--review", str(r), "--check"]).exit_code == 1
    _commit(r, "fix(doc): bound the timeout — SIN-SRS-0001")
    assert runner.invoke(app, ["verify", "--review", str(r), "--check"]).exit_code == 0
