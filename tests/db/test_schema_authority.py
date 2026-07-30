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


# --- v3.1 step 05 task 3: bootstrap_schema creates AND stamps ---------------

from malus.db import bootstrap_schema  # noqa: E402


def test_bootstrap_schema_creates_and_stamps_an_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")

    assert bootstrap_schema(engine) is True

    insp = inspect(engine)
    assert set(insp.get_table_names()) - {"alembic_version"} == set(SQLModel.metadata.tables)
    assert current_revision(engine) == "c4d5e6f7a8b9"  # never left unstamped


def test_bootstrap_schema_refuses_a_populated_database(tmp_path):
    """A database that already has tables belongs to Alembic. Stamping it head
    would skip every pending migration — the 2026-07-30 failure mode, inverted."""
    url = f"sqlite:///{tmp_path / 'existing.db'}"
    engine = create_engine(url)
    upgrade_head(engine)

    assert bootstrap_schema(engine) is False
    assert current_revision(engine) == "c4d5e6f7a8b9"


def test_bootstrap_schema_refuses_a_stamped_but_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'weird.db'}")
    stamp_head(engine)

    with pytest.raises(RuntimeError, match="stamped at"):
        bootstrap_schema(engine)


def test_create_all_does_not_stamp(tmp_path):
    """`create_all` stays the raw test helper: no stamp, no backfill. The
    a5a0125 regression test depends on being able to reproduce exactly that."""
    from malus.db import create_all

    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    create_all(engine)

    assert current_revision(engine) is None


# --- v3.1 step 05 task 4: the serving path creates nothing ------------------

def test_create_app_creates_no_schema(tmp_path):
    """The boot path is read-only with respect to the schema. In production the
    entrypoint has already run `alembic upgrade head`; anything create_app did
    on top of that could only be drift."""
    from malus.api import create_app

    engine = create_engine(f"sqlite:///{tmp_path / 'untouched.db'}")
    create_app(engine, https_only=False, session_secret="s", bootstrap_admin=None)

    assert inspect(engine).get_table_names() == []


def test_create_app_has_no_create_schema_switch():
    import inspect as pyinspect

    from malus.api import create_app

    assert "create_schema" not in pyinspect.signature(create_app).parameters
