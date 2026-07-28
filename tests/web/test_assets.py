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


# --------------------------------------------------------------------------- #
# v2.0.1: cache correctness — Safari/Opera served a stale v1.9 stylesheet via
# HTTP heuristic caching (no Cache-Control on /static), breaking the v2 shell.
# --------------------------------------------------------------------------- #


def test_static_responses_always_revalidate(client: TestClient):
    r = client.get("/static/app.css")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"  # revalidate every use
    assert "etag" in r.headers  # so revalidation stays a cheap 304


def test_asset_links_are_version_busted(client: TestClient):
    from malus import __version__

    login = client.get("/ui/login").text
    assert f"/static/app.css?v={__version__}" in login
    assert f"/static/vendor/htmx.min.js?v={__version__}" in login
