"""App icon + web-app manifest are served and linked (v1.4.1)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_icon_and_manifest_served(client: TestClient):
    assert client.get("/static/icon.svg").status_code == 200
    r = client.get("/static/manifest.json")
    assert r.status_code == 200 and r.json()["name"] == "maluS"


def test_pages_link_favicon_and_manifest(client: TestClient):
    login = client.get("/ui/login").text  # public page, extends base.html
    assert '/static/icon.svg' in login
    assert '/static/manifest.json' in login
