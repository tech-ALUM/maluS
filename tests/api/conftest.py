"""API test fixtures: an authenticated TestClient over a fresh in-memory DB.

Multiple clients over the same ``app`` share one database (StaticPool) but keep
separate cookie jars, so each can be logged in as a different user.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from malus.api import create_app
from malus.db import make_engine

ADMIN = ("admin", "admin-pw")


@pytest.fixture
def app():
    return create_app(
        make_engine("sqlite://"),
        https_only=False,  # TestClient speaks http
        session_secret="test-secret",
        bootstrap_admin=ADMIN,
    )


@pytest.fixture
def client(app):
    """An unauthenticated client."""
    return TestClient(app)


@pytest.fixture
def login(app):
    def _login(username: str, password: str) -> TestClient:
        c = TestClient(app)
        r = c.post("/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return c

    return _login


@pytest.fixture
def admin(login):
    return login(*ADMIN)


@pytest.fixture
def mkuser(admin, login):
    """Create a user (as admin) and return a client logged in as them."""

    def _mk(username: str, display_name: str, password: str = "pw", **flags) -> TestClient:
        r = admin.post(
            "/users",
            json={"username": username, "password": password, "display_name": display_name, **flags},
        )
        assert r.status_code == 201, r.text
        return login(username, password)

    return _mk


BASELINE = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

COPY_F = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout must have an upper bound to avoid an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format. {SUGG: "disk" -> "the configured store"}
"""

COPY_R = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout must have an upper bound to prevent an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format.
"""


@pytest.fixture
def docs():
    return {"baseline": BASELINE, "copy_f": COPY_F, "copy_r": COPY_R}

