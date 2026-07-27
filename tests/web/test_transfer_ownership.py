"""Ownership transfer from the GUI (v2 step 2).

The current owner or a global admin transfers primary ownership; the
transferrer chooses the ex-owner's fate: removed from the review or demoted
to reviewer (never auto-moderator). Target must be an active human account.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from malus.db.models import AuditLog, Review, ReviewMember, User

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


def _transfer(client: TestClient, username: str, fate: str):
    return client.post(
        f"/ui/reviews/{R}/transfer-owner",
        data={"username": username, "fate": fate},
        follow_redirects=False,
    )


def _db_state(app):
    with Session(app.state.engine) as s:
        review = s.exec(select(Review).where(Review.review_id_str == R)).one()
        owner = s.get(User, review.owner_id)
        members = {
            s.get(User, m.user_id).username: m.role
            for m in s.exec(select(ReviewMember).where(ReviewMember.review_id == review.id)).all()
        }
        return owner.username, members


def test_owner_transfers_and_becomes_reviewer(app, mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("nova", "N. Ova"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "nova", "role": "reviewer"})

    assert _transfer(owner, "nova", "reviewer").status_code == 303
    new_owner, members = _db_state(app)
    assert new_owner == "nova"
    assert members == {"nova": "owner", "owner": "reviewer"}

    with Session(app.state.engine) as s:
        entry = s.exec(select(AuditLog).where(AuditLog.action == "transfer_ownership")).one()
        assert entry.actor is not None and entry.actor.username == "owner"
        assert entry.detail_json["to"] == "N. Ova"
        assert entry.detail_json["old_owner_fate"] == "reviewer"


def test_owner_transfers_and_is_removed(app, mkuser):
    owner = _owner_with_review(mkuser)
    _onboard(mkuser("nova", "N. Ova"), "pw")

    # target is NOT yet a member: the transfer adds them as owner
    assert _transfer(owner, "nova", "remove").status_code == 303
    new_owner, members = _db_state(app)
    assert new_owner == "nova"
    assert members == {"nova": "owner"}  # ex-owner gone
    # the ex-owner lost owner powers: managing members is now refused
    assert owner.get(f"/ui/reviews/{R}/members").status_code == 403


def test_admin_can_transfer_without_membership(app, admin, mkuser):
    _owner_with_review(mkuser)
    _onboard(mkuser("nova", "N. Ova"), "pw")
    admin_c = _onboard(admin, "admin-pw")

    assert _transfer(admin_c, "nova", "reviewer").status_code == 303
    new_owner, members = _db_state(app)
    assert new_owner == "nova" and members["owner"] == "reviewer"


def test_reviewer_and_moderator_cannot_transfer(mkuser):
    owner = _owner_with_review(mkuser)
    rev = _onboard(mkuser("rev", "R. Ev"), "pw")
    mod = _onboard(mkuser("mod", "M. Od"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "rev", "role": "reviewer"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "mod", "role": "moderator"})

    assert _transfer(rev, "mod", "reviewer").status_code == 403
    assert _transfer(mod, "rev", "reviewer").status_code == 403


def test_invalid_targets_are_rejected(app, mkuser):
    owner = _owner_with_review(mkuser)
    mkuser("bot", "AI Bot", is_ai=True)
    _onboard(mkuser("gone", "Gone Away"), "pw")

    assert _transfer(owner, "bot", "reviewer").status_code == 422  # AI target
    assert _transfer(owner, "owner", "reviewer").status_code == 422  # self
    assert _transfer(owner, "ghost", "reviewer").status_code == 422  # unknown
    assert _transfer(owner, "gone", "banana").status_code == 422  # bad fate
    new_owner, _ = _db_state(app)
    assert new_owner == "owner"  # nothing changed


def test_owner_visible_in_list_and_dashboard(mkuser):
    # viewed by ANOTHER user, so the owner's name cannot come from the topbar
    owner = _owner_with_review(mkuser)
    viewer = _onboard(mkuser("viewer", "V. Iewer"), "pw")
    owner.post(f"/ui/reviews/{R}/members", data={"username": "viewer", "role": "reviewer"})

    lst = viewer.get("/ui/reviews")
    assert lst.status_code == 200 and "A. Boffi" in lst.text
    dash = viewer.get(f"/ui/reviews/{R}")
    assert dash.status_code == 200 and "A. Boffi" in dash.text
