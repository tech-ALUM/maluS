"""maluS command-line interface.

Step 1 provides the full command surface as stubs; each subcommand is
implemented in a later step (see ``docs/plan/00-general-plan.md``). The
entry point is ``malus = malus.cli:app`` (see ``pyproject.toml``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .harvest import freeze_review, harvest_review, init_review, make_copies

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
def init(
    review_id: str = typer.Argument(..., help="Review id, e.g. SIN-SRS-R1."),
    document: Path = typer.Option(
        ..., "--document", "-d", help="Path to the source Markdown document (DUR)."
    ),
    reviews_root: Path = typer.Option(
        Path("reviews"), "--dir", help="Root folder that holds reviews."
    ),
    owner: Optional[str] = typer.Option(None, "--owner", help="Document owner name."),
    reviewers: Optional[str] = typer.Option(
        None, "--reviewers", help="Comma-separated reviewer names."
    ),
) -> None:
    """Create a new review instance (baseline.md, rtd.yaml, reviewers/)."""
    names = [r.strip() for r in reviewers.split(",") if r.strip()] if reviewers else None
    try:
        review_dir = init_review(
            review_id, document, reviews_root=reviews_root, owner=owner, reviewers=names
        )
    except (FileExistsError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None
    typer.echo(f"created review {review_dir}")
    typer.echo(f"next: malus freeze --review {review_dir}")


@app.command("freeze")
def freeze(
    review: Path = typer.Option(Path("."), "--review", help="Review directory."),
    review_id: Optional[str] = typer.Option(None, "--review-id", help="Set the review id."),
    owner: Optional[str] = typer.Option(None, "--owner", help="Set the document owner."),
    reviewers: Optional[str] = typer.Option(
        None, "--reviewers", help="Comma-separated reviewer names."
    ),
) -> None:
    """Freeze the DUR baseline and record its git SHA into the review meta."""
    names = [r.strip() for r in reviewers.split(",") if r.strip()] if reviewers else None
    sha = freeze_review(review, review_id=review_id, owner=owner, reviewers=names)
    typer.echo(f"baseline frozen: {sha}")


@app.command("copies")
def copies(
    review: Path = typer.Option(Path("."), "--review", help="Review directory."),
) -> None:
    """Create one frozen per-reviewer copy of the baseline."""
    created = make_copies(review)
    if not created:
        typer.echo("no copies created (reviewer files already exist)")
    for path in created:
        typer.echo(f"created {path}")


@app.command("harvest")
def harvest(
    review: Path = typer.Option(Path("."), "--review", help="Review directory."),
) -> None:
    """Parse reviewer copies and (re)generate rtd.yaml."""
    try:
        result = harvest_review(review)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None
    typer.echo(f"harvested {len(result.rtd.rids)} RID(s) from {review}")
    for violation in result.violations:
        where = f" (baseline line {violation.line})" if violation.line else ""
        typer.echo(
            f"VIOLATION [{violation.reviewer}]{where}: {violation.message}", err=True
        )
    if result.violations:
        raise typer.Exit(code=1)


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
