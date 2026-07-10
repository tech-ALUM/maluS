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


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", help="Bind port."),
    db: str = typer.Option(DEFAULT_URL, "--db", help="Database URL."),
) -> None:
    """Run the HTTP API server (uvicorn)."""
    import uvicorn

    from .api import create_app
    from .logging import configure_logging

    configure_logging()
    typer.echo(f"serving maluS API on http://{host}:{port} (db: {db})")
    uvicorn.run(create_app(make_engine(db)), host=host, port=port)


@app.command("mcp")
def mcp() -> None:
    """Run the maluS MCP server (stdio) for an interactive AI reviewer.

    Authenticates to a running maluS via MALUS_URL / MALUS_AI_USER /
    MALUS_AI_PASSWORD. maluS makes no model calls (the free path).
    """
    from .mcp.server import run

    run()


if __name__ == "__main__":  # pragma: no cover
    app()
