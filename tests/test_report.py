"""Tests for rtd.yaml validation and generated review minutes."""

import datetime as dt
from pathlib import Path

from typer.testing import CliRunner

from malus.cli import app
from malus.constants import Disposition, Kind, Severity, Status
from malus.models import RID, RTD, Meta
from malus.report import render_report, report_review, validate

runner = CliRunner()


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


def test_validate_flags_dangling_master() -> None:
    errors = validate(_rtd([_rid("SIN-SRS-0001", master="SIN-SRS-9999")]))
    assert any("master" in e for e in errors)


# --- render / write ---


def test_render_report_has_key_sections() -> None:
    text = render_report(_rtd([_verified("SIN-SRS-0001")]))
    for section in ("# Review Minutes — SIN-SRS-R1", "## Status", "## Per reviewer", "## Sources"):
        assert section in text


def test_report_review_writes_when_clean(tmp_path: Path) -> None:
    (tmp_path / "rtd.yaml").write_text(_rtd([_verified("SIN-SRS-0001")]).to_yaml(), encoding="utf-8")
    assert report_review(tmp_path) == []
    assert (tmp_path / "report.md").exists()


def test_report_review_refuses_when_invalid(tmp_path: Path) -> None:
    (tmp_path / "rtd.yaml").write_text(
        _rtd([_verified("SIN-SRS-0001", by="A. Boffi")]).to_yaml(), encoding="utf-8"
    )
    assert report_review(tmp_path)  # non-empty errors
    assert not (tmp_path / "report.md").exists()


def test_cli_report_writes_and_reports_invalid(tmp_path: Path) -> None:
    (tmp_path / "rtd.yaml").write_text(_rtd([_verified("SIN-SRS-0001")]).to_yaml(), encoding="utf-8")
    assert runner.invoke(app, ["report", "--review", str(tmp_path)]).exit_code == 0
    assert (tmp_path / "report.md").exists()
    (tmp_path / "rtd.yaml").write_text(
        _rtd([_verified("SIN-SRS-0001", by="A. Boffi")]).to_yaml(), encoding="utf-8"
    )
    assert runner.invoke(app, ["report", "--review", str(tmp_path)]).exit_code == 1
