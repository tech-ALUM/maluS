"""v3: the owner may edit a disposition (typo, changed mind) while the finding
is still ANSWERED — i.e. until its reviewer accepts it. From `closed` onward a
settled disposition changes only through the formal reopen."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_answered(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return owner, f


def test_owner_edits_answered_disposition(mkuser, docs):
    owner, _f = _seed_answered(mkuser, docs)
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "rejected", "reply": "on second thought, no"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    view = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"status": "answered"' in view  # editing never re-transitions
    assert '"disposition": "rejected"' in view
    assert "on second thought" in view


def test_settled_disposition_is_immutable(mkuser, docs):
    owner, f = _seed_answered(mkuser, docs)
    assert f.post(f"/reviews/{R}/rids/SIN-SRS-0001/accept").status_code == 200
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "rejected", "reply": "too late"},
    )
    assert r.status_code == 409
    view = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"disposition": "accepted"' in view  # unchanged
