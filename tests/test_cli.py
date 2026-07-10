"""CLI (v1): the version flag and the legacy v0-directory import command."""

from pathlib import Path

from typer.testing import CliRunner

from malus import __version__
from malus.cli import app

runner = CliRunner()

SAMPLE = Path(__file__).parent / "fixtures" / "sample-review"


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_import_seeds_the_database(tmp_path):
    db = tmp_path / "malus.db"
    result = runner.invoke(app, ["import", str(SAMPLE), "--db", f"sqlite:///{db}"])
    assert result.exit_code == 0, result.stdout
    assert "SIN-SRS-R1" in result.stdout
    assert db.exists()
