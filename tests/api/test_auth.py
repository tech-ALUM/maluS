"""Authentication and permission-boundary tests (v1 Step 4)."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"


def test_unauthenticated_requests_are_401(client: TestClient):
    assert client.get("/reviews").status_code == 401
    assert client.post("/reviews", json={"review_id": "X"}).status_code == 401
    assert client.get(f"/reviews/{R}/rids").status_code == 401


def test_openapi_and_docs_are_public(client: TestClient):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_login_me_logout(mkuser):
    alice = mkuser("alice", "Alice")
    me = alice.get("/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "alice"
    assert alice.post("/auth/logout").status_code == 200
    assert alice.get("/auth/me").status_code == 401  # cookie cleared


def test_bad_login_is_401(client: TestClient):
    assert client.post("/auth/login", json={"username": "nope", "password": "x"}).status_code == 401


def test_user_management_is_admin_only(admin, mkuser):
    alice = mkuser("alice", "Alice")  # not an admin
    assert alice.get("/users").status_code == 403
    assert alice.post("/users", json={"username": "x", "password": "p"}).status_code == 403
    assert admin.get("/users").status_code == 200


def test_change_password(mkuser, login):
    bob = mkuser("bob", "Bob", password="old-pw")
    assert bob.post(
        "/auth/change-password", json={"old_password": "wrong", "new_password": "new-pw"}
    ).status_code == 403
    assert bob.post(
        "/auth/change-password", json={"old_password": "old-pw", "new_password": "new-pw"}
    ).status_code == 200
    login("bob", "new-pw")  # the new password works


def test_reviewer_cannot_edit_another_reviewers_copy(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    r = mkuser("rbianchi", "R. Bianchi")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    for name in ("F. Miccoli", "R. Bianchi"):
        owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})

    assert f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]}).status_code == 200
    # R may not write F's copy
    assert r.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": "x"}).status_code == 403


def test_reviewer_cannot_run_harvest(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    # harvest is moderator-only
    assert f.post(f"/reviews/{R}/harvest").status_code == 403


def test_ai_principal_cannot_verify(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    ai = mkuser("aibot", "AI Bot", is_ai=True)

    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    for name, role in [("F. Miccoli", "reviewer"), ("M. Mod", "moderator"), ("AI Bot", "reviewer")]:
        owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": role})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")

    # an AI principal is refused verify regardless of role (403)
    assert ai.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 403


def test_audit_log_records_the_actor(app, mkuser, docs):
    from sqlmodel import Session, select

    from malus.db.models import AuditLog

    owner = mkuser("owner", "A. Boffi")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})

    with Session(app.state.engine) as session:
        entries = session.exec(select(AuditLog).where(AuditLog.action == "freeze")).all()
        assert entries
        assert all(e.actor is not None and e.actor.display_name == "A. Boffi" for e in entries)
