"""Tests for the Typer CLI skeleton: every subcommand present as a stub."""

import pytest
from typer.testing import CliRunner

from malus import __version__
from malus.cli import app

runner = CliRunner()

# Wide terminal so rich never truncates command names in help output.
_WIDE = {"COLUMNS": "200"}

SUBCOMMANDS = [
    "init",
    "freeze",
    "copies",
    "harvest",
    "triage",
    "apply-suggs",
    "report",
    "verify",
    "finalize",
    "ai",
]


def test_root_help_lists_all_subcommands() -> None:
    result = runner.invoke(app, ["--help"], env=_WIDE)
    assert result.exit_code == 0
    for name in SUBCOMMANDS:
        assert name in result.output


@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_each_subcommand_has_help(name: str) -> None:
    result = runner.invoke(app, [name, "--help"], env=_WIDE)
    assert result.exit_code == 0
    assert name in result.output


def test_version_option() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


