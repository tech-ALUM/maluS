"""The Alembic migration applies on a fresh SQLite file and produces exactly the
schema described by the SQLModel metadata (Step-1 Definition of Done)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import malus.db.models  # noqa: F401  populate SQLModel.metadata
from malus.db import create_all

ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_creates_full_schema(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    command.upgrade(_alembic_config(url), "head")

    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(SQLModel.metadata.tables)


def test_upgrade_head_after_create_all_already_ran(tmp_path):
    """The state that took the server down on 2026-07-30: the app had booted
    while Alembic was still at ``a7c31e90d412``, so ``create_all`` had already
    made ``review_artifacts`` (and the reopen column) without stamping the
    revision. The next ``upgrade head`` must converge on the same schema, not
    collide with ``table review_artifacts already exists``.

    Two schema authorities coexist by design here (``create_all`` bootstraps,
    Alembic migrates) — every revision therefore has to tolerate the objects
    it creates being already present."""
    url = f"sqlite:///{tmp_path / 'drifted.db'}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "a7c31e90d412")
    create_all(create_engine(url))  # the app's own bootstrap path

    command.upgrade(cfg, "head")

    insp = inspect(create_engine(url))
    assert "review_artifacts" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("reviewer_copies")}
    assert "reopen_requested_at" in cols


def test_migration_downgrades_to_base(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set()
