"""End-to-end AI role commands on the fixture review, with the mock engine."""

import shutil
from pathlib import Path

from typer.testing import CliRunner

from malus.ai import MockEngine, draft_dispositions, write_ai_review
from malus.cli import app
from malus.constants import Status
from malus.harvest import harvest_review
from malus.models import RTD

runner = CliRunner()
FIXTURE = Path(__file__).parent / "fixtures" / "sample-review"


def _review(tmp_path: Path) -> Path:
    dest = tmp_path / "review"
    shutil.copytree(FIXTURE, dest)
    return dest


# --- Mode 2: AI reviewer ---


def test_ai_review_writes_a_valid_reviewer_copy(tmp_path: Path) -> None:
    review = _review(tmp_path)
    path = write_ai_review(review, "claude", MockEngine())
    assert path.name == "claude.md"
    assert path.read_text(encoding="utf-8").startswith("# Sensor Interface Requirements")


def test_ai_review_via_cli(tmp_path: Path) -> None:
    review = _review(tmp_path)
    result = runner.invoke(app, ["ai", "review", "--reviewer", "claude", "--review", str(review)])
    assert result.exit_code == 0
    assert (review / "reviewers" / "claude.md").exists()


# --- Mode 1: AI owner drafting (never closes) ---


def test_ai_disposition_drafts_but_never_advances(tmp_path: Path) -> None:
    review = _review(tmp_path)
    harvest_review(review)  # produce open RIDs
    drafted = draft_dispositions(review, MockEngine())
    assert drafted >= 1
    rtd = RTD.from_yaml((review / "rtd.yaml").read_text(encoding="utf-8"))
    ai_rids = [r for r in rtd.rids if r.ai_drafted]
    assert ai_rids
    assert all(r.disposition is not None for r in ai_rids)
    assert all(r.status is Status.OPEN for r in ai_rids)  # AI never advances or verifies


def test_ai_disposition_via_cli(tmp_path: Path) -> None:
    review = _review(tmp_path)
    harvest_review(review)
    assert runner.invoke(app, ["ai", "disposition", "--review", str(review)]).exit_code == 0


# --- guardrails ---


def test_ai_has_no_verify_or_close_command(tmp_path: Path) -> None:
    review = _review(tmp_path)
    # There is deliberately no `malus ai verify` / `ai close` — closure stays human.
    assert runner.invoke(app, ["ai", "verify", "--review", str(review)]).exit_code != 0
    assert runner.invoke(app, ["ai", "close", "--review", str(review)]).exit_code != 0


def test_ai_triage_cli_default_no_proposals(tmp_path: Path) -> None:
    review = _review(tmp_path)
    harvest_review(review)
    result = runner.invoke(app, ["ai", "triage", "--review", str(review)])
    assert result.exit_code == 0


def test_bad_engine_name_exits_nonzero(tmp_path: Path) -> None:
    review = _review(tmp_path)
    harvest_review(review)
    result = runner.invoke(
        app, ["ai", "disposition", "--review", str(review), "--engine", "bogus"]
    )
    assert result.exit_code != 0
