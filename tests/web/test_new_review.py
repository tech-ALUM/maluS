"""Step 12: create a review from the GUI + login error feedback."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"
BASELINE = "# SRS\n\n## 1 Timeouts\n\nThe acquisition timeout shall be configurable.\n"


def test_create_review_from_gui(mkuser):
    owner = mkuser("owner", "A. Boffi")
    assert owner.get("/ui/reviews/new").status_code == 200

    r = owner.post(
        "/ui/reviews/new",
        data={"review_id": R, "title": "SRS review", "rid_prefix": "SIN-SRS", "baseline": BASELINE},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == f"/ui/reviews/{R}"

    # it appears in the list, is queryable, and the baseline is frozen
    assert R in owner.get("/ui/reviews").text
    got = owner.get(f"/reviews/{R}")
    assert got.status_code == 200 and got.json()["owner"] == "A. Boffi"
    assert owner.get(f"/reviews/{R}/baseline").json()["content"] == BASELINE


def test_duplicate_review_id_shows_error(mkuser):
    owner = mkuser("owner", "A. Boffi")
    owner.post("/ui/reviews/new", data={"review_id": R, "baseline": BASELINE})
    r = owner.post("/ui/reviews/new", data={"review_id": R, "baseline": BASELINE})
    assert r.status_code == 409 and "already exists" in r.text


def test_login_with_wrong_credentials_shows_error(client: TestClient):
    r = client.post(
        "/ui/login", data={"username": "nobody", "password": "wrong"}, follow_redirects=False
    )
    assert r.status_code == 401
    assert "Invalid username or password" in r.text
