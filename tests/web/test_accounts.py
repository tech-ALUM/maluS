"""Account-management GUI tests (v1 Step 10): self-service password, force-change
at first login, admin user CRUD (gated), and per-review role assignment."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"


def _onboard(client: TestClient, current: str, new: str = "new-pw") -> TestClient:
    """Clear must_change_password via the self-service page (needed before GUI use)."""
    r = client.post(
        "/ui/account/password", data={"current": current, "new_password": new}, follow_redirects=False
    )
    assert r.status_code == 303
    return client


def test_force_password_change_at_first_login(mkuser):
    bob = mkuser("bob", "Bob", onboard=False)  # admin-created -> must_change_password
    # any /ui page redirects to the password page until it is changed
    r = bob.get("/ui/reviews", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/account/password"
    # the password page itself is reachable
    assert bob.get("/ui/account/password").status_code == 200
    _onboard(bob, "pw")
    assert bob.get("/ui/reviews", follow_redirects=False).status_code == 200


def test_self_service_wrong_current_password_is_403(mkuser):
    bob = mkuser("bob", "Bob")
    r = bob.post("/ui/account/password", data={"current": "WRONG", "new_password": "x"})
    assert r.status_code == 403


def test_admin_users_page_is_admin_gated(admin, mkuser):
    _onboard(admin, "admin-pw")
    assert admin.get("/ui/admin/users").status_code == 200
    alice = _onboard(mkuser("alice", "Alice"), "pw")  # non-admin, onboarded
    assert alice.get("/ui/admin/users").status_code == 403


def test_admin_creates_user_and_ai_reviewer(app, admin):
    _onboard(admin, "admin-pw")
    assert admin.post(
        "/ui/admin/users/new",
        data={"username": "newbie", "display_name": "New Bie", "password": "tmp", "kind": "regular"},
        follow_redirects=False,
    ).status_code == 303
    assert "newbie" in admin.get("/ui/admin/users").text

    # an AI reviewer account is created from this GUI
    assert admin.post(
        "/ui/admin/users/new",
        data={"username": "aibot", "display_name": "AI Bot", "password": "tmp", "kind": "ai"},
        follow_redirects=False,
    ).status_code == 303
    ai = TestClient(app)
    ai.post("/auth/login", json={"username": "aibot", "password": "tmp"})
    assert ai.get("/auth/me").json()["is_ai"] is True


def test_admin_deactivate_and_reactivate(app, admin, mkuser):
    _onboard(admin, "admin-pw")
    mkuser("carl", "Carl", password="tmp")
    assert admin.post("/ui/admin/users/carl/deactivate", follow_redirects=False).status_code == 303
    assert TestClient(app).post("/auth/login", json={"username": "carl", "password": "tmp"}).status_code == 401
    assert admin.post("/ui/admin/users/carl/activate", follow_redirects=False).status_code == 303
    assert TestClient(app).post("/auth/login", json={"username": "carl", "password": "tmp"}).status_code == 200


def test_admin_reset_password(app, admin, mkuser):
    _onboard(admin, "admin-pw")
    mkuser("dan", "Dan", password="old-tmp")
    assert admin.post(
        "/ui/admin/users/dan/reset-password", data={"password": "fresh-tmp"}, follow_redirects=False
    ).status_code == 303
    assert TestClient(app).post("/auth/login", json={"username": "dan", "password": "old-tmp"}).status_code == 401
    assert TestClient(app).post("/auth/login", json={"username": "dan", "password": "fresh-tmp"}).status_code == 200


def test_admin_cannot_deactivate_self(admin):
    _onboard(admin, "admin-pw")
    assert admin.post("/ui/admin/users/admin/deactivate", follow_redirects=False).status_code == 409


def test_per_review_role_assignment_from_gui(mkuser):
    owner = _onboard(mkuser("owner", "A. Boffi"), "pw")
    mkuser("mod", "M. Mod")
    reviewer = _onboard(mkuser("rev", "R. Ev"), "pw")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})

    # owner assigns a moderator via the members GUI (by stable username)
    assert owner.post(
        f"/ui/reviews/{R}/members", data={"username": "mod", "role": "moderator"}, follow_redirects=False
    ).status_code == 303
    page = owner.get(f"/ui/reviews/{R}/members")
    assert page.status_code == 200 and "M. Mod" in page.text and "moderator" in page.text

    # a non-owner, non-admin cannot manage members
    assert reviewer.get(f"/ui/reviews/{R}/members").status_code == 403
