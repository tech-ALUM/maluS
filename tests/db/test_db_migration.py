"""The Alembic migration applies on a fresh SQLite file and produces exactly the
schema described by the SQLModel metadata (Step-1 Definition of Done)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import malus.db.models  # noqa: F401  populate SQLModel.metadata

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


def test_migration_downgrades_to_base(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set()
