"""Member management from the GUI (v1.2 Step 1): assign by real account
(username), searchable candidate list, inline role change, member removal, and
the owner-safety guard. Complements the Step-10 tests in ``test_accounts.py``."""

from __future__ import annotations

from fastapi.testclient import TestClient

R = "SIN-SRS-R1"


def _onboard(client: TestClient, current: str, new: str = "new-pw") -> TestClient:
    r = client.post(
        "/ui/account/password", data={"current": current, "new_password": new}, follow_redirects=False
    )
    assert r.status_code == 303
    return client


def _owner_with_review(mkuser) -> TestClient:
    owner = _onboard(mkuser("owner", "A. Boffi"), "pw")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    return owner


def test_owner_assigns_reviewer_by_username(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("rev", "R. Ev"), "pw")  # a real, existing account

    r = owner.post(
        f"/ui/reviews/{R}/members",
        data={"username": "rev", "role": "reviewer"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    page = owner.get(f"/ui/reviews/{R}/members")
    assert page.status_code == 200 and "R. Ev" in page.text and "reviewer" in page.text


def test_unknown_username_is_rejected_and_creates_no_phantom(admin, mkuser):
    owner = _owner_with_review(mkuser)
    r = owner.post(f"/ui/reviews/{R}/members", data={"username": "ghost", "role": "reviewer"})
    assert r.status_code == 422
    _onboard(admin, "admin-pw")
    assert "ghost" not in admin.get("/ui/admin/users").text  # no placeholder user spawned


def test_inactive_account_cannot_be_assigned(admin, mkuser):
    owner = _owner_with_review(mkuser)
    mkuser("gone", "Gone Away")  # a real account, then deactivated
    admin_c = _onboard(admin, "admin-pw")
    assert admin_c.post("/ui/admin/users/gone/deactivate", follow_redirects=False).status_code == 303
    r = owner.post(f"/ui/reviews/{R}/members", data={"username": "gone", "role": "reviewer"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# searchable candidate picker (over existing active accounts)
# --------------------------------------------------------------------------- #


def test_candidate_search_lists_active_non_members(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("alice", "Alice Smith"), "pw")
    _onboard(mkuser("bob", "Bob Jones"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "alice", "role": "reviewer"})

    res = owner.get(f"/ui/reviews/{R}/members/search?q=")
    assert res.status_code == 200
    assert "bob" in res.text and "Bob Jones" in res.text  # an available candidate
    assert "Alice Smith" not in res.text  # already a member -> excluded from the picker


def test_candidate_search_filters_by_query_case_insensitive(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("alice", "Alice Smith"), "pw")
    _onboard(mkuser("bob", "Bob Jones"), "pw")
    res = owner.get(f"/ui/reviews/{R}/members/search?q=ALI")
    assert "Alice Smith" in res.text and "Bob Jones" not in res.text


def test_candidate_search_is_owner_admin_gated(mkuser):
    owner = _owner_with_review(mkuser)
    reviewer = _onboard(mkuser("rev", "R. Ev"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "rev", "role": "reviewer"})
    assert reviewer.get(f"/ui/reviews/{R}/members/search?q=").status_code == 403


# --------------------------------------------------------------------------- #
# inline role change + member removal
# --------------------------------------------------------------------------- #


def test_owner_changes_a_member_role_inline(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("rev", "R. Ev"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "rev", "role": "reviewer"})
    # re-assign the same account to a different role (the inline control reuses the endpoint)
    r = owner.post(
        f"/ui/reviews/{R}/members", data={"username": "rev", "role": "moderator"}, follow_redirects=False
    )
    assert r.status_code == 303
    page = owner.get(f"/ui/reviews/{R}/members").text
    assert "moderator" in page and page.count("R. Ev") == 1  # role changed, not duplicated


def test_owner_removes_a_member(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("rev", "R. Ev"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "rev", "role": "reviewer"})
    assert "R. Ev" in owner.get(f"/ui/reviews/{R}/members").text

    r = owner.post(f"/ui/reviews/{R}/members/rev/remove", follow_redirects=False)
    assert r.status_code == 303
    assert "R. Ev" not in owner.get(f"/ui/reviews/{R}/members").text


# --------------------------------------------------------------------------- #
# owner-safety guard (a review must always keep its primary owner)
# --------------------------------------------------------------------------- #


def test_primary_owner_cannot_be_demoted(mkuser):
    owner = _owner_with_review(mkuser)
    r = owner.post(f"/ui/reviews/{R}/members", data={"username": "owner", "role": "reviewer"})
    assert r.status_code == 409


def test_primary_owner_cannot_be_removed(mkuser):
    owner = _owner_with_review(mkuser)
    assert owner.post(f"/ui/reviews/{R}/members/owner/remove").status_code == 409


def test_co_owner_can_be_removed_leaving_the_primary(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("alice", "Alice"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "alice", "role": "owner"})  # co-owner
    r = owner.post(f"/ui/reviews/{R}/members/alice/remove", follow_redirects=False)
    assert r.status_code == 303
    assert "Alice" not in owner.get(f"/ui/reviews/{R}/members").text  # co-owner gone; primary stays


def test_removing_a_member_keeps_their_harvested_rids(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "fmiccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"]})  # harvest -> a COMM RID
    assert any(x["kind"] == "COMM" for x in f.get(f"/reviews/{R}/rids").json())

    assert owner.post(f"/ui/reviews/{R}/members/fmiccoli/remove", follow_redirects=False).status_code == 303
    # membership is revoked, but the harvested finding survives (no cascade delete)
    assert any(x["kind"] == "COMM" for x in owner.get(f"/reviews/{R}/rids").json())


# --------------------------------------------------------------------------- #
# Members page wiring (picker + inline row controls)
# --------------------------------------------------------------------------- #


def test_members_page_wires_picker_and_row_controls(mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("rev", "R. Ev"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "rev", "role": "reviewer"})
    page = owner.get(f"/ui/reviews/{R}/members").text
    assert f"/ui/reviews/{R}/members/search" in page  # picker is wired to the search endpoint
    assert 'name="username"' in page  # assignment submits a stable username, not free text
    assert f"/ui/reviews/{R}/members/rev/remove" in page  # each non-primary member is removable


def test_members_page_does_not_offer_to_remove_the_primary_owner(mkuser):
    owner = _owner_with_review(mkuser)
    page = owner.get(f"/ui/reviews/{R}/members").text
    assert f"/ui/reviews/{R}/members/owner/remove" not in page  # primary owner has no remove control
