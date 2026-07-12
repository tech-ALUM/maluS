"""Admin hard-delete of a user from the GUI (v1.3): guards, the new-owner
picker flow for owned reviews, anonymization end-to-end, and the sentinel."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"
SENTINEL = "deleted-user"


def _onboard(client: TestClient, current: str, new: str = "new-pw") -> TestClient:
    r = client.post(
        "/ui/account/password", data={"current": current, "new_password": new}, follow_redirects=False
    )
    assert r.status_code == 303
    return client


def test_admin_deletes_an_unused_user(app, admin, mkuser):
    a = _onboard(admin, "admin-pw")
    mkuser("temp", "Temp User")  # created + onboarded, no attributions
    assert a.get("/ui/admin/users/temp/delete").status_code == 200  # confirm page
    assert a.post("/ui/admin/users/temp/delete", follow_redirects=False).status_code == 303
    assert "/ui/admin/users/temp/delete" not in a.get("/ui/admin/users").text  # row gone
    assert TestClient(app).post("/auth/login", json={"username": "temp", "password": "pw"}).status_code == 401


def test_admin_cannot_delete_self(admin):
    a = _onboard(admin, "admin-pw")
    assert a.post("/ui/admin/users/admin/delete", follow_redirects=False).status_code == 409


def test_delete_is_admin_gated(mkuser):
    alice = _onboard(mkuser("alice", "Alice"), "pw")  # non-admin
    assert alice.get("/ui/admin/users/admin/delete").status_code == 403
    assert alice.post("/ui/admin/users/admin/delete").status_code == 403


def test_owned_review_requires_a_valid_new_owner(app, admin, mkuser):
    a = _onboard(admin, "admin-pw")
    owner = mkuser("owner", "A. Boffi")
    mkuser("succ", "Succ Essor")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})

    # missing new owner for the owned review -> 422, nothing deleted
    assert a.post("/ui/admin/users/owner/delete", follow_redirects=False).status_code == 422
    assert "/ui/admin/users/owner/delete" in a.get("/ui/admin/users").text  # still present
    # new owner cannot be the user being deleted -> 422
    assert a.post(
        "/ui/admin/users/owner/delete", data={f"owner_for_{R}": "owner"}, follow_redirects=False
    ).status_code == 422
    # a valid new owner -> deleted, ownership transferred
    assert a.post(
        "/ui/admin/users/owner/delete", data={f"owner_for_{R}": "succ"}, follow_redirects=False
    ).status_code == 303
    assert "/ui/admin/users/owner/delete" not in a.get("/ui/admin/users").text  # row gone


def test_new_owner_can_act_as_owner_after_transfer(app, admin, mkuser):
    a = _onboard(admin, "admin-pw")
    owner = mkuser("owner", "A. Boffi")
    succ = _onboard(mkuser("succ", "Succ Essor"), "pw")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    assert a.post(
        "/ui/admin/users/owner/delete", data={f"owner_for_{R}": "succ"}, follow_redirects=False
    ).status_code == 303
    # succ is now the owner: the owner-gated Members page is reachable
    assert succ.get(f"/ui/reviews/{R}/members").status_code == 200


def test_delete_reviewer_anonymizes_their_findings(app, admin, mkuser, docs):
    a = _onboard(admin, "admin-pw")
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "fmiccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"]})  # RID authored by F. Miccoli
    before = owner.get(f"/reviews/{R}/rids").json()
    assert any(x["reviewer"] == "F. Miccoli" for x in before)

    assert a.post("/ui/admin/users/fmiccoli/delete", follow_redirects=False).status_code == 303
    after = owner.get(f"/reviews/{R}/rids").json()
    assert len(after) == len(before)  # findings preserved
    assert any(x["reviewer"] == "Deleted user" for x in after)  # author anonymized
    assert not any(x["reviewer"] == "F. Miccoli" for x in after)


def test_sentinel_is_hidden_and_not_deletable(app, admin, mkuser):
    a = _onboard(admin, "admin-pw")
    mkuser("temp", "Temp User")
    a.post("/ui/admin/users/temp/delete")  # first deletion materializes the sentinel
    page = a.get("/ui/admin/users").text
    assert "Deleted user" not in page and SENTINEL not in page  # sentinel hidden from the list
    assert a.post(f"/ui/admin/users/{SENTINEL}/delete", follow_redirects=False).status_code == 409
