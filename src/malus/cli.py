"""maluS command-line interface.

Step 1 provides the full command surface as stubs; each subcommand is
implemented in a later step (see ``docs/plan/00-general-plan.md``). The
entry point is ``malus = malus.cli:app`` (see ``pyproject.toml``).
"""

from __future__ import annotations

import typer

from . import __version__

app = typer.Typer(
    name="malus",
    help="maluS — formal RID-based review management for Markdown documents.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"malus {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the maluS version and exit.",
    ),
) -> None:
    """maluS — formal RID-based review management for Markdown documents."""


def _stub(command: str, step: str) -> None:
    """Common body for a not-yet-implemented subcommand."""
    typer.echo(f"malus {command}: not yet implemented ({step}).")
    raise typer.Exit(code=1)


@app.command("init")
def init() -> None:
    """Create a review instance: the reviews/<review-id>/ layout."""
    _stub("init", "Step 2")


@app.command("freeze")
def freeze() -> None:
    """Freeze the DUR baseline and record its git SHA."""
    _stub("freeze", "Step 2")


@app.command("copies")
def copies() -> None:
    """Create one frozen per-reviewer copy of the baseline."""
    _stub("copies", "Step 2")


@app.command("harvest")
def harvest() -> None:
    """Parse reviewer copies and (re)generate rtd.yaml."""
    _stub("harvest", "Step 2")


@app.command("triage")
def triage() -> None:
    """Cluster duplicate findings under master RIDs."""
    _stub("triage", "Step 3")


@app.command("apply-suggs")
def apply_suggs() -> None:
    """Batch-apply accepted mechanical {SUGG} replacements."""
    _stub("apply-suggs", "Step 3")


@app.command("report")
def report() -> None:
    """Generate the review report/dashboard from rtd.yaml."""
    _stub("report", "Step 5")


@app.command("verify")
def verify() -> None:
    """Reviewer-side verification and closure of RIDs."""
    _stub("verify", "Step 5")


@app.command("finalize")
def finalize() -> None:
    """Produce the new baseline plus review minutes."""
    _stub("finalize", "Step 5")


@app.command("ai")
def ai() -> None:
    """Drive an AI in the owner / reviewer / moderator seat."""
    _stub("ai", "Step 6")


if __name__ == "__main__":  # pragma: no cover
    app()
