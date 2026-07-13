"""Delete a review from the GUI (v1.5): owner/admin only, with a confirm step."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"


def _onboard(client: TestClient, current: str, new: str = "new-pw") -> TestClient:
    r = client.post(
        "/ui/account/password", data={"current": current, "new_password": new}, follow_redirects=False
    )
    assert r.status_code == 303
    return client


def _seed(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("frev", "F. Rev")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "frev", "role": "reviewer"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner, f, mod


def test_owner_deletes_review_with_findings(mkuser, docs):
    owner, f, _mod = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"]})  # harvest a RID
    assert owner.get(f"/ui/reviews/{R}/delete").status_code == 200  # confirm page
    assert owner.post(f"/ui/reviews/{R}/delete", follow_redirects=False).status_code == 303
    assert owner.get(f"/ui/reviews/{R}").status_code == 404  # gone
    assert f"/ui/reviews/{R}" not in owner.get("/ui/reviews").text  # not in the list


def test_admin_can_delete_review(admin, mkuser, docs):
    _owner, _f, _mod = _seed(mkuser, docs)
    a = _onboard(admin, "admin-pw")
    assert a.post(f"/ui/reviews/{R}/delete", follow_redirects=False).status_code == 303
    assert a.get(f"/ui/reviews/{R}").status_code == 404


def test_reviewer_and_moderator_cannot_delete(mkuser, docs):
    owner, f, mod = _seed(mkuser, docs)
    assert f.get(f"/ui/reviews/{R}/delete").status_code == 403
    assert f.post(f"/ui/reviews/{R}/delete").status_code == 403
    assert mod.post(f"/ui/reviews/{R}/delete").status_code == 403
    # the control is shown to the owner but not to a reviewer
    assert f"/ui/reviews/{R}/delete" in owner.get(f"/ui/reviews/{R}").text
    assert f"/ui/reviews/{R}/delete" not in f.get(f"/ui/reviews/{R}").text
