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


def test_init_db_creates_and_stamps(tmp_path):
    from sqlalchemy import create_engine

    from malus.db import current_revision

    db = tmp_path / "dev.db"
    result = runner.invoke(app, ["init-db", "--db", f"sqlite:///{db}"])

    assert result.exit_code == 0, result.stdout
    assert current_revision(create_engine(f"sqlite:///{db}")) is not None


def test_init_db_refuses_an_existing_database(tmp_path):
    db = tmp_path / "dev.db"
    assert runner.invoke(app, ["init-db", "--db", f"sqlite:///{db}"]).exit_code == 0

    result = runner.invoke(app, ["init-db", "--db", f"sqlite:///{db}"])

    assert result.exit_code == 1
    assert "alembic upgrade head" in result.stdout


def test_serve_refuses_a_database_without_schema(tmp_path):
    """Fail fast with an actionable message instead of half-booting: the
    serving path never creates a schema (v3.1 step 05)."""
    result = runner.invoke(app, ["serve", "--db", f"sqlite:///{tmp_path / 'empty.db'}"])

    assert result.exit_code == 2
    assert "alembic upgrade head" in result.output
    assert "malus init-db" in result.output
