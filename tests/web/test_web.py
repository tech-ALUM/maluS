"""Web GUI (server-rendered) tests: login, dashboard, and the disposition +
verification cycle done entirely in the browser, role-gated (v1 Step 5)."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    """Seed a review with one harvested RID via the API; return role clients."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")
    return owner, f, mod


def test_login_page_renders(client: TestClient):
    r = client.get("/ui/login")
    assert r.status_code == 200
    assert "Sign in" in r.text and "malu" in r.text


def test_root_redirects_to_login_when_anonymous(client: TestClient):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/login"


def test_login_flow_and_review_list(app, mkuser, docs):
    owner, _f, _mod = _seed(mkuser, docs)
    # a browser client logs in via the HTML form
    browser = TestClient(app)
    r = browser.post("/ui/login", data={"username": "owner", "password": "pw"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/reviews"
    page = browser.get("/ui/reviews")
    assert page.status_code == 200 and R in page.text and "owner" in page.text


def test_dashboard_and_rtd_table_render(mkuser, docs):
    owner, _f, _mod = _seed(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}")
    assert page.status_code == 200
    assert "SIN-SRS-0001" in page.text  # the harvested RID
    assert "findings" in page.text  # dashboard metric


def test_disposition_and_verification_cycle_in_browser(mkuser, docs, app):
    owner, f, _mod = _seed(mkuser, docs)

    # owner sees a disposition form but NOT a verify control
    owner_view = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert "/dispose" in owner_view
    assert "/verify" not in owner_view  # closure authority: owner never gets a verify control

    # owner rejects the finding via the browser form
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "rejected", "reply": "out of scope", "resolution": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # the reviewer sees a verify control but NOT a disposition form
    rev_view = f.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert "/verify" in rev_view and "/dispose" not in rev_view

    # reviewer verifies via the browser
    r = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/verify", follow_redirects=False)
    assert r.status_code == 303
    detail = f.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert "verified" in detail

    # audit recorded the verifier
    from sqlmodel import Session, select

    from malus.db.models import AuditLog

    with Session(app.state.engine) as session:
        verify_entries = session.exec(select(AuditLog).where(AuditLog.action == "verify")).all()
        assert verify_entries and verify_entries[-1].actor.display_name == "F. Miccoli"


def test_owner_cannot_force_verify_server_side(mkuser, docs):
    owner, _f, _mod = _seed(mkuser, docs)
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "rejected", "reply": "n/a", "resolution": ""},
    )
    # even if the owner forges the verify POST, the server refuses (403)
    r = owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/verify", follow_redirects=False)
    assert r.status_code == 403


def test_static_css_served(client: TestClient):
    r = client.get("/static/app.css")
    assert r.status_code == 200 and "--coral" in r.text
