"""Alembic is the single schema authority (v3.1 step 05).

These tests pin the boot contract that the 2026-07-30 incident broke: the
serving path never creates schema, anything that does create schema stamps it,
and a database is reachable from `alembic upgrade head` alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import malus.db.models  # noqa: F401  populate SQLModel.metadata
from malus.db.migrations import alembic_ini, current_revision, stamp_head, upgrade_head

ROOT = Path(__file__).resolve().parents[2]


def test_alembic_ini_is_discoverable_from_the_package():
    assert alembic_ini() == ROOT / "alembic.ini"


def test_stamp_head_marks_an_unstamped_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'plain.db'}"
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    assert current_revision(engine) is None

    stamp_head(engine)

    assert current_revision(engine) == "c4d5e6f7a8b9"  # head


def test_injected_connection_wins_over_MALUS_DB_URL(tmp_path, monkeypatch):
    """env.py reads MALUS_DB_URL first (alembic/env.py:28). A programmatic
    upgrade must go to the engine it was handed, never to whatever the
    environment happens to point at — otherwise a developer with MALUS_DB_URL
    exported migrates the wrong database."""
    decoy = tmp_path / "decoy.db"
    target = tmp_path / "target.db"
    monkeypatch.setenv("MALUS_DB_URL", f"sqlite:///{decoy}")

    upgrade_head(create_engine(f"sqlite:///{target}"))

    assert "users" in inspect(create_engine(f"sqlite:///{target}")).get_table_names()
    assert not decoy.exists()
