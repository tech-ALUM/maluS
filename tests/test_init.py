"""Tests for `malus init` — creating a new review instance from a source DUR."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from malus.cli import app
from malus.harvest import freeze_review, harvest_review, init_review, make_copies
from malus.models import RTD

runner = CliRunner()

DOC = "# Title\n\nSome requirement text.\n"


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "source.md"
    path.write_text(DOC, encoding="utf-8")
    return path


def test_init_creates_layout(tmp_path: Path) -> None:
    review = init_review(
        "SIN-SRS-R1",
        _source(tmp_path),
        reviews_root=tmp_path / "reviews",
        owner="A. Boffi",
        reviewers=["F. Miccoli", "R. Bianchi"],
    )
    assert (review / "baseline.md").read_text(encoding="utf-8") == DOC
    assert (review / "reviewers").is_dir()
    rtd = RTD.from_yaml((review / "rtd.yaml").read_text(encoding="utf-8"))
    assert rtd.meta.review_id == "SIN-SRS-R1"
    assert rtd.meta.document == "baseline.md"
    assert rtd.meta.owner == "A. Boffi"
    assert rtd.meta.reviewers == ["F. Miccoli", "R. Bianchi"]
    assert rtd.meta.baseline_sha == ""  # filled in later by `freeze`
    assert rtd.rids == []


def test_init_refuses_to_overwrite_existing_review(tmp_path: Path) -> None:
    init_review("R1", _source(tmp_path), reviews_root=tmp_path / "reviews")
    with pytest.raises(FileExistsError):
        init_review("R1", _source(tmp_path), reviews_root=tmp_path / "reviews")


def test_init_errors_on_missing_document(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        init_review("R1", tmp_path / "nope.md", reviews_root=tmp_path / "reviews")


def test_full_pipeline_init_freeze_copies_harvest(tmp_path: Path) -> None:
    review = init_review(
        "SIN-SRS-R1",
        _source(tmp_path),
        reviews_root=tmp_path / "reviews",
        reviewers=["F. Miccoli"],
    )
    freeze_review(review)
    created = make_copies(review)
    assert len(created) == 1
    copy = review / "reviewers" / "F. Miccoli.md"
    copy.write_text(
        copy.read_text(encoding="utf-8").replace(
            "requirement text.", "requirement text. {COMM: unclear}"
        ),
        encoding="utf-8",
    )
    result = harvest_review(review)
    assert not result.violations
    assert [r.rid for r in result.rtd.rids] == ["SIN-SRS-0001"]
    assert result.rtd.rids[0].comment == "unclear"


def test_cli_init(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "SIN-SRS-R1",
            "--document",
            str(_source(tmp_path)),
            "--dir",
            str(tmp_path / "reviews"),
            "--reviewers",
            "F. Miccoli,R. Bianchi",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "reviews" / "SIN-SRS-R1" / "rtd.yaml").exists()
