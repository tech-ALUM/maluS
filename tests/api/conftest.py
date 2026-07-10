"""API test fixtures: a TestClient over a fresh in-memory database per test."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from malus.api import create_app
from malus.db import make_engine


def build_client() -> TestClient:
    return TestClient(create_app(make_engine("sqlite://")))


@pytest.fixture
def client() -> TestClient:
    return build_client()
