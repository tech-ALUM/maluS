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
from .db import DEFAULT_URL, bootstrap_schema, make_engine
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
    bootstrap_schema(engine)  # creates + stamps only if the database is empty
    with Session(engine) as session:
        review = import_review_dir(session, review_dir)
        session.commit()
        typer.echo(f"imported {review.review_id_str} into {db}")


@app.command("init-db")
def init_db(
    db: str = typer.Option(DEFAULT_URL, "--db", help="Database URL (SQLModel/SQLAlchemy)."),
) -> None:
    """Create an empty development database and stamp it at Alembic head.

    Local development only. A deployment migrates with ``alembic upgrade head``
    — the single schema authority (v3.1 step 05); the container entrypoint runs
    it before the server starts.
    """
    if bootstrap_schema(make_engine(db)):
        typer.echo(f"created and stamped schema at head: {db}")
        return
    typer.echo(f"{db} already has tables — run 'alembic upgrade head' instead")
    raise typer.Exit(code=1)


def _require_schema(engine, db: str) -> None:
    """Refuse to serve a database that was never migrated. ``serve`` is
    read-only with respect to the schema (v3.1 step 05) — it must not silently
    invent one, which is how the two schema authorities drifted apart."""
    from sqlalchemy import inspect

    if "users" in inspect(engine).get_table_names():
        return
    typer.secho(
        f"error: no schema in {db}.\n"
        "  deployment: run 'alembic upgrade head' (the container entrypoint does this)\n"
        f"  local dev:  run 'malus init-db --db {db}'",
        err=True,
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=2)


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
    engine = make_engine(db)
    _require_schema(engine, db)
    typer.echo(f"serving maluS API on http://{host}:{port} (db: {db})")
    uvicorn.run(create_app(engine), host=host, port=port)


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
