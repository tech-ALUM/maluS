"""Step 12 (upload since v2.1): create a review from the GUI + login errors."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"
BASELINE = "# SRS\n\n## 1 Timeouts\n\nThe acquisition timeout shall be configurable.\n"


def _md(name: str = "srs.md", content: str = BASELINE, ctype: str = "text/markdown"):
    return {"baseline": (name, content.encode(), ctype)}


def test_create_review_by_uploading_md(mkuser):
    owner = mkuser("owner", "A. Boffi")
    page = owner.get("/ui/reviews/new")
    assert page.status_code == 200
    assert 'type="file"' in page.text and "multipart/form-data" in page.text
    assert "<textarea" not in page.text  # the paste path is gone

    r = owner.post(
        "/ui/reviews/new",
        data={"review_id": R, "title": "SRS review", "rid_prefix": "SIN-SRS"},
        files=_md(),
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == f"/ui/reviews/{R}"

    # it appears in the list, is queryable, and the baseline is frozen
    assert R in owner.get("/ui/reviews").text
    got = owner.get(f"/reviews/{R}")
    assert got.status_code == 200 and got.json()["owner"] == "A. Boffi"
    assert owner.get(f"/reviews/{R}/baseline").json()["content"] == BASELINE


def test_empty_title_defaults_to_filename_stem(mkuser):
    owner = mkuser("owner", "A. Boffi")
    owner.post(
        "/ui/reviews/new",
        data={"review_id": R, "title": ""},
        files=_md(name="Sensor Requirements.md"),
    )
    assert owner.get(f"/reviews/{R}").json()["title"] == "Sensor Requirements"


def test_upload_validation(mkuser):
    owner = mkuser("owner", "A. Boffi")
    # wrong extension
    r = owner.post("/ui/reviews/new", data={"review_id": R}, files=_md(name="doc.pdf"))
    assert r.status_code == 422 and "Markdown" in r.text
    # oversize (> 2 MB)
    big = "x" * (2 * 1024 * 1024 + 1)
    r = owner.post("/ui/reviews/new", data={"review_id": R}, files=_md(content=big))
    assert r.status_code == 422
    # invalid UTF-8
    r = owner.post(
        "/ui/reviews/new",
        data={"review_id": R},
        files={"baseline": ("srs.md", b"\xff\xfe\x00bad", "text/markdown")},
    )
    assert r.status_code == 422
    # nothing was created by any of the failures
    assert owner.get(f"/reviews/{R}").status_code == 404


def test_duplicate_review_id_shows_error(mkuser):
    owner = mkuser("owner", "A. Boffi")
    owner.post("/ui/reviews/new", data={"review_id": R}, files=_md())
    r = owner.post("/ui/reviews/new", data={"review_id": R}, files=_md())
    assert r.status_code == 409 and "already exists" in r.text


def test_login_with_wrong_credentials_shows_error(client: TestClient):
    r = client.post(
        "/ui/login", data={"username": "nobody", "password": "wrong"}, follow_redirects=False
    )
    assert r.status_code == 401
    assert "Invalid username or password" in r.text
