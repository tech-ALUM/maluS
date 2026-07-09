"""End-to-end file-based harvest on the fixture review, plus freeze/copies."""

import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from malus.cli import app
from malus.constants import Kind
from malus.harvest import freeze_review, harvest_review, make_copies
from malus.models import RTD

FIXTURE = Path(__file__).parent / "fixtures" / "sample-review"
runner = CliRunner()


def _review(tmp_path: Path) -> Path:
    dest = tmp_path / "review"
    shutil.copytree(FIXTURE, dest)
    return dest


def test_harvest_on_fixture(tmp_path: Path) -> None:
    review = _review(tmp_path)
    result = harvest_review(review)
    # two {COMM}s plus one deduped {SUGG}
    assert len(result.rtd.rids) == 3
    assert sum(1 for r in result.rtd.rids if r.kind is Kind.SUGG) == 1
    # the tampering reviewer is rejected with an actionable, located message
    violation = next(v for v in result.violations if v.reviewer == "G. Verdi")
    assert violation.line is not None
    assert (review / "rtd.yaml").exists()


def test_ids_are_prefixed_sequence(tmp_path: Path) -> None:
    rtd = harvest_review(_review(tmp_path)).rtd
    assert [r.rid for r in rtd.rids] == ["SIN-SRS-0001", "SIN-SRS-0002", "SIN-SRS-0003"]


def test_harvest_is_idempotent_on_fixture(tmp_path: Path) -> None:
    review = _review(tmp_path)
    harvest_review(review)
    first = (review / "rtd.yaml").read_text(encoding="utf-8")
    harvest_review(review)
    second = (review / "rtd.yaml").read_text(encoding="utf-8")
    assert first == second


def test_freeze_records_baseline_sha(tmp_path: Path) -> None:
    review = _review(tmp_path)
    sha = freeze_review(review)
    expected = subprocess.run(
        ["git", "hash-object", str(review / "baseline.md")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert sha == expected
    assert RTD.from_yaml((review / "rtd.yaml").read_text()).meta.baseline_sha == expected


def test_make_copies_seeds_missing_only(tmp_path: Path) -> None:
    review = _review(tmp_path)
    shutil.rmtree(review / "reviewers")
    created = make_copies(review)
    assert len(created) == 3
    baseline = (review / "baseline.md").read_text(encoding="utf-8")
    assert (review / "reviewers" / "F. Miccoli.md").read_text(encoding="utf-8") == baseline
    assert make_copies(review) == []  # nothing to do on a second run


def test_cli_harvest_reports_violation_exit_1(tmp_path: Path) -> None:
    review = _review(tmp_path)
    result = runner.invoke(app, ["harvest", "--review", str(review)])
    assert result.exit_code == 1  # a violating copy is present


def test_cli_harvest_clean_review_exit_0(tmp_path: Path) -> None:
    review = _review(tmp_path)
    (review / "reviewers" / "G. Verdi.md").unlink()
    result = runner.invoke(app, ["harvest", "--review", str(review)])
    assert result.exit_code == 0
