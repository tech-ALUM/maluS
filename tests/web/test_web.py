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
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
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

    # v2: the finding opens as viewer focus mode; capabilities live in the payload
    owner_view = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"canDispose": true' in owner_view
    assert '"canVerify": false' in owner_view  # closure authority: owner never gets verify

    # owner accepts the finding via the browser form (v3: needed to reach implement/verify)
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # the reviewer gets the verify capability but not the dispose one
    rev_view = f.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"canVerify": true' in rev_view and '"canDispose": false' in rev_view

    # v3: the reviewer accepts the owner's disposition — answered -> closed, in_review only
    r = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept", follow_redirects=False)
    assert r.status_code == 303
    assert '"status": "closed"' in f.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text

    # the owner starts closeout via the browser — the gate is satisfied (RID closed)
    r = owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    assert r.status_code == 303

    # owner closes an implementation session on the accepted finding
    # (v3.2 point 13: one gesture — the save links the change and implements it)
    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": docs["baseline"] + "\nbounded.\n", "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert '"status": "implemented"' in owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text

    # the standalone route survives for pre-v3.2 data, and is idempotent
    r = owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement", follow_redirects=False)
    assert r.status_code == 303
    assert '"status": "implemented"' in owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text

    # reviewer verifies via the browser (closeout only)
    r = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/verify", follow_redirects=False)
    assert r.status_code == 303
    detail = f.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"status": "verified"' in detail

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
