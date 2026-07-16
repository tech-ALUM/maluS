"""v1.10: a global admin is a superuser over EVERY review — it passes every
review-scoped guard without being a member — including closure. The only hard
limit is is_ai (an AI principal never closes/commits, admin or not)."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    """Owner + one reviewer + a NON-MEMBER admin; one OPEN harvested RID."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    admin = mkuser("suadmin", "SU Admin", is_admin=True)  # not a member of the review
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    return owner, f, admin


def _rids(client):
    return {x["rid"]: x for x in client.get(f"/reviews/{R}/rids").json()}


def test_admin_can_dispose_without_membership(mkuser, docs):
    _owner, _f, admin = _seed(mkuser, docs)
    r = admin.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "rejected", "reply": "n/a"},
    )
    assert r.status_code == 200 and r.json()["status"] == "answered"


def test_admin_can_verify_and_reopen_closure(mkuser, docs):
    _owner, _f, admin = _seed(mkuser, docs)
    admin.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"status": "answered", "disposition": "rejected", "reply": "n/a"})
    assert admin.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 200  # closure
    assert admin.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()["status"] == "verified"
    assert admin.post(f"/reviews/{R}/rids/SIN-SRS-0001/reopen", json={"reason": "recheck"}).status_code == 200


def test_admin_can_freeze_and_edit_document(mkuser, docs):
    _owner, _f, admin = _seed(mkuser, docs)
    assert admin.post(f"/reviews/{R}/document", json={"content": docs["baseline"] + "\nadmin edit\n"}).status_code == 200


def test_admin_retracts_any_reviewers_comment(mkuser, docs):
    _owner, _f, admin = _seed(mkuser, docs)
    assert admin.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract", follow_redirects=False).status_code == 303
    assert "SIN-SRS-0001" not in _rids(admin)


def test_admin_reopens_a_submission(mkuser, docs, app):
    _owner, _f, admin = _seed(mkuser, docs)
    r = admin.post(f"/ui/reviews/{R}/reopen-submission/F. Miccoli", follow_redirects=False)
    assert r.status_code == 303
    from sqlmodel import Session, select

    from malus.db.models import ReviewerCopy

    with Session(app.state.engine) as s:
        assert s.exec(select(ReviewerCopy)).one().submitted_at is None  # back to draft


def test_ai_admin_still_cannot_close(mkuser, docs):
    # the is_ai guard is absolute — even an admin AI principal cannot verify
    _owner, _f, _admin = _seed(mkuser, docs)
    ai_admin = mkuser("aiadmin", "AI Admin", is_ai=True, is_admin=True)
    assert ai_admin.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 403


def test_non_admin_reviewer_still_cannot_dispose(mkuser, docs):
    # regression: non-admin authorization is unchanged
    _owner, f, _admin = _seed(mkuser, docs)
    assert f.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001", json={"status": "answered", "disposition": "accepted"}
    ).status_code == 403


def test_admin_sees_controls_on_finding_and_dashboard(mkuser, docs):
    _owner, _f, admin = _seed(mkuser, docs)
    finding = admin.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert "/dispose" in finding and "/verify" in finding  # admin gets both
    dash = admin.get(f"/ui/reviews/{R}").text
    assert "/retract" in dash and "/reopen-submission" in dash
