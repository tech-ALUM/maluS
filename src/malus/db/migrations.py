"""Programmatic access to Alembic — the single schema authority (v3.1 step 05).

maluS used to keep two authorities: Alembic, and ``create_all`` running on
every ``malus serve``. On 2026-07-30 that drift took the server down (a table
created by ``create_all`` with ``alembic_version`` left behind, so the next
``alembic upgrade head`` collided with it). Alembic now owns the production
schema alone, and everything that still creates a schema — only the developer
bootstrap — stamps it here, immediately.

The Alembic scripts ship next to the repo / image root, not inside the wheel
(``Dockerfile`` copies ``alembic.ini`` and ``alembic/`` into ``/app``, which is
also WORKDIR), so they are resolved in this order:
``MALUS_ALEMBIC_INI`` → the repo root derived from ``malus.__file__`` →
``Path.cwd()``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.engine import Engine

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext

import malus


class AlembicNotFound(RuntimeError):
    """The Alembic scripts are not reachable from this installation."""


def _candidates() -> list[Path]:
    env = os.environ.get("MALUS_ALEMBIC_INI")
    found = [Path(env)] if env else []
    found.append(Path(malus.__file__).resolve().parents[2] / "alembic.ini")
    found.append(Path.cwd() / "alembic.ini")
    return found


def alembic_ini() -> Path:
    """The ``alembic.ini`` whose sibling ``alembic/versions`` actually exists."""
    for candidate in _candidates():
        if candidate.is_file() and (candidate.parent / "alembic" / "versions").is_dir():
            return candidate
    raise AlembicNotFound(
        "alembic.ini not found (looked in: "
        + ", ".join(str(c) for c in _candidates())
        + ") — set MALUS_ALEMBIC_INI"
    )


def alembic_config() -> Config:
    ini = alembic_ini()
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    cfg.attributes["configure_logger"] = False
    return cfg
    # NB: sqlalchemy.url is deliberately left alone — every call below injects a
    # live connection, so no credential is ever copied into the Config object.


def current_revision(engine: Engine) -> Optional[str]:
    """The revision this database is stamped at, or ``None`` if unstamped."""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _with_connection(engine: Engine, run: Callable[[Config], None]) -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        run(cfg)


def stamp_head(engine: Engine) -> None:
    """Write ``alembic_version`` = head without running any migration."""
    _with_connection(engine, lambda cfg: command.stamp(cfg, "head"))


def upgrade_head(engine: Engine) -> None:
    """``alembic upgrade head`` against this engine (tests, tooling)."""
    _with_connection(engine, lambda cfg: command.upgrade(cfg, "head"))
