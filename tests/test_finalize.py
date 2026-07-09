"""Tests for finalize: closed-only gating and generated outputs."""

import datetime as dt
from pathlib import Path

import yaml
from typer.testing import CliRunner

from malus.cli import app
from malus.constants import Disposition, Kind, Severity, Status
from malus.lifecycle import finalize_review
from malus.models import RID, RTD, Meta

runner = CliRunner()


def _rtd(rids):
    return RTD(
        meta=Meta(
            review_id="SIN-SRS-R1",
            document="baseline.md",
            baseline_sha="abc1234",
            created=dt.date(2026, 7, 3),
            owner="A. Boffi",
            reviewers=["F. Miccoli"],
        ),
        rids=rids,
    )


def _rid(rid_id, status, disp):
    return RID(
        rid=rid_id,
        reviewer="F. Miccoli",
        created=dt.date(2026, 7, 3),
        kind=Kind.COMM,
        type=None,
        severity=Severity.MAJOR,
        status=status,
        disposition=disp,
        verified_by="F. Miccoli" if status is Status.VERIFIED else None,
        comment="finding text",
    )


def _write(tmp_path, rtd, baseline="BASELINE\n", working=None):
    (tmp_path / "baseline.md").write_text(baseline, encoding="utf-8")
    if working is not None:
        (tmp_path / "working.md").write_text(working, encoding="utf-8")
    (tmp_path / "rtd.yaml").write_text(rtd.to_yaml(), encoding="utf-8")
    return tmp_path


def test_finalize_refuses_when_a_finding_is_open(tmp_path: Path):
    _write(tmp_path, _rtd([_rid("SIN-SRS-0001", Status.OPEN, None)]))
    assert finalize_review(tmp_path)  # non-empty errors
    assert not (tmp_path / "final.md").exists()


def test_finalize_writes_outputs_from_working_copy(tmp_path: Path):
    _write(
        tmp_path,
        _rtd([_rid("SIN-SRS-0001", Status.VERIFIED, Disposition.ACCEPTED)]),
        working="FINALIZED DOC\n",
    )
    assert finalize_review(tmp_path) == []
    assert (tmp_path / "final.md").read_text(encoding="utf-8") == "FINALIZED DOC\n"
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "carryover.yaml").exists()
    assert (tmp_path / "FINALIZED").exists()


def test_finalize_final_md_falls_back_to_baseline(tmp_path: Path):
    _write(tmp_path, _rtd([_rid("SIN-SRS-0001", Status.WITHDRAWN, None)]), baseline="ONLY BASE\n")
    assert finalize_review(tmp_path) == []
    assert (tmp_path / "final.md").read_text(encoding="utf-8") == "ONLY BASE\n"


def test_finalize_carryover_lists_deferred(tmp_path: Path):
    _write(tmp_path, _rtd([_rid("SIN-SRS-0001", Status.VERIFIED, Disposition.DEFERRED)]))
    finalize_review(tmp_path)
    carry = yaml.safe_load((tmp_path / "carryover.yaml").read_text(encoding="utf-8"))
    assert carry["source_review"] == "SIN-SRS-R1"
    assert [d["rid"] for d in carry["deferred"]] == ["SIN-SRS-0001"]


def test_cli_finalize_exit_codes(tmp_path: Path):
    _write(tmp_path, _rtd([_rid("SIN-SRS-0001", Status.VERIFIED, Disposition.ACCEPTED)]))
    assert runner.invoke(app, ["finalize", "--review", str(tmp_path)]).exit_code == 0
    _write(tmp_path, _rtd([_rid("SIN-SRS-0001", Status.OPEN, None)]))
    assert runner.invoke(app, ["finalize", "--review", str(tmp_path)]).exit_code == 1
