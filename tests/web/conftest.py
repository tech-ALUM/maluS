"""Web GUI test fixtures (mirror the API fixtures: auth over a fresh in-mem DB)."""

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
        https_only=False,
        session_secret="test-secret",
        bootstrap_admin=ADMIN,
    )


@pytest.fixture
def client(app):
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
    def _mk(
        username: str, display_name: str, password: str = "pw", onboard: bool = True, **flags
    ) -> TestClient:
        r = admin.post(
            "/users",
            json={"username": username, "password": password, "display_name": display_name, **flags},
        )
        assert r.status_code == 201, r.text
        client = login(username, password)
        if onboard:  # clear must_change_password (the normal post-first-login state)
            client.post("/ui/account/password", data={"current": password, "new_password": password})
        return client

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


@pytest.fixture
def docs():
    return {"baseline": BASELINE, "copy_f": COPY_F}
