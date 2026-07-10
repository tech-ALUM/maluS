"""End-to-end fixtures (auth over a fresh in-memory DB; human + AI content)."""

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
        assert c.post("/auth/login", json={"username": username, "password": password}).status_code == 200
        return c

    return _login


@pytest.fixture
def admin(login):
    return login(*ADMIN)


@pytest.fixture
def mkuser(admin, login):
    def _mk(username: str, display_name: str, password: str = "pw", **flags) -> TestClient:
        assert admin.post(
            "/users",
            json={"username": username, "password": password, "display_name": display_name, **flags},
        ).status_code == 201
        return login(username, password)

    return _mk


@pytest.fixture
def basic_client(app):
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

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

COPY_F = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: bound the timeout}

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

AI_COPY = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.

## 3.3 Logging

All measurements are written to disk in CSV format. {COMM|type=editorial|sev=minor: name the CSV columns}
"""


@pytest.fixture
def docs():
    return {"baseline": BASELINE, "copy_f": COPY_F, "ai_copy": AI_COPY}
