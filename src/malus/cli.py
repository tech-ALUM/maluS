"""maluS command-line interface (v1).

The v0 file/git pipeline commands were retired at v1 Step 2 (ADR 0001): the
review pipeline is now a database service layer (``malus.services``) that Step 3
exposes over HTTP, and the AI seats are rebuilt over MCP in Step 7. What remains
on the CLI is the version flag and a legacy importer that seeds the database
from a v0 file-based review directory.
"""

from __future__ import annotations

from pathlib import Path

import typer
from sqlmodel import Session

from . import __version__
from .db import DEFAULT_URL, create_all, make_engine
from .legacy import import_review_dir

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


@app.command("import")
def import_cmd(
    review_dir: Path = typer.Argument(
        ..., help="A v0 review directory (baseline.md, rtd.yaml, reviewers/)."
    ),
    db: str = typer.Option(DEFAULT_URL, "--db", help="Database URL (SQLModel/SQLAlchemy)."),
) -> None:
    """Import a v0 file-based review into the database."""
    engine = make_engine(db)
    create_all(engine)
    with Session(engine) as session:
        review = import_review_dir(session, review_dir)
        session.commit()
        typer.echo(f"imported {review.review_id_str} into {db}")


if __name__ == "__main__":  # pragma: no cover
    app()
