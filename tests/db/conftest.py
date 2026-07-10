"""Shared fixtures for the DB-layer tests: a fresh in-memory SQLite session."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from malus.db.session import create_all, make_engine


@pytest.fixture
def engine():
    """A fresh in-memory SQLite engine with the schema created."""
    eng = make_engine("sqlite://")  # in-memory, StaticPool so the schema persists
    create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
