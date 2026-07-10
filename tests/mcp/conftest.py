"""MCP test fixtures (auth over a fresh in-memory DB; AI reviewer content)."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from malus.api import create_app
from malus.db import make_engine

ADMIN = ("admin", "admin-pw")


@pytest.fixture
def app():
    return create_app(
        make_engine("sqlite://"), https_only=False, session_secret="test-secret", bootstrap_admin=ADMIN
    )


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
    def _mk(username: str, display_name: str, password: str = "pw", **flags) -> TestClient:
        r = admin.post(
            "/users",
            json={"username": username, "password": password, "display_name": display_name, **flags},
        )
        assert r.status_code == 201, r.text
        return login(username, password)

    return _mk


@pytest.fixture
def basic_client(app):
    """A programmatic client authenticated with HTTP Basic (the AI-agent path)."""

    def _mk(username: str, password: str) -> TestClient:
        c = TestClient(app)
        c.headers["Authorization"] = "Basic " + base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()
        return c

    return _mk


BASELINE = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.
"""

AI_COPY = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout needs an upper bound}
"""


@pytest.fixture
def docs():
    return {"baseline": BASELINE, "ai_copy": AI_COPY}
