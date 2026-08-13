"""App icon + web-app manifest are served and linked (v1.4.1).

v3.2: the icon set is a family of PNGs generated from ``docs/brand/`` by
``scripts/gen_brand_assets.py``. The failure these tests guard is a renamed or
un-regenerated file 404ing behind a favicon the browser has already cached, so
they walk every icon URL the app actually publishes rather than naming one.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

ICON_URL = re.compile(r'/static/(?:icon|alum)[\w.-]*\.(?:png|svg)')


def test_every_icon_the_manifest_publishes_is_served(client: TestClient):
    r = client.get("/static/manifest.json")
    assert r.status_code == 200 and r.json()["name"] == "maluS"

    icons = r.json()["icons"]
    assert icons, "the manifest must publish at least one icon"
    for entry in icons:
        assert client.get(entry["src"]).status_code == 200, entry["src"]

    purposes = {entry.get("purpose") for entry in icons}
    assert "maskable" in purposes  # Android crops to a circle without one


def test_every_icon_the_pages_link_is_served(client: TestClient):
    login = client.get("/ui/login").text  # public page, extends base.html
    assert "/static/manifest.json" in login

    urls = set(ICON_URL.findall(login))
    assert urls, "base.html must link at least one icon"
    for url in urls:
        assert client.get(url).status_code == 200, url


def test_signed_in_pages_link_the_alum_mark(admin: TestClient):
    page = admin.get("/ui/reviews").text  # the shell, with the sidebar
    urls = set(ICON_URL.findall(page))
    assert any("alum-mark" in u for u in urls), "the sidebar mark is missing"
    for url in urls:
        assert admin.get(url).status_code == 200, url


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
