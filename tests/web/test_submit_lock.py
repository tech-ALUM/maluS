"""v3: Submit copy is irreversible — after submitting, a reviewer edits again
only by requesting a reopen that the owner (or an admin) approves."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_submitted(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "submit"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return owner, f


def test_submitted_copy_is_locked(mkuser, docs):
    _owner, f = _seed_submitted(mkuser, docs)
    edited = docs["copy_f"].replace(
        "CSV format.", "CSV format. {COMM|type=editorial: another note}"
    )
    for action in ("save", "submit"):
        r = f.post(
            f"/ui/reviews/{R}/edit-copy",
            data={"content": edited, "action": action},
        )
        assert r.status_code == 409, action


def test_reopen_request_then_owner_approval_unlocks(mkuser, docs):
    owner, f = _seed_submitted(mkuser, docs)

    r = f.post(f"/ui/reviews/{R}/request-reopen", follow_redirects=False)
    assert r.status_code == 303
    assert "reopen requested" in owner.get(f"/ui/reviews/{R}").text

    r = owner.post(f"/ui/reviews/{R}/approve-reopen/F. Miccoli", follow_redirects=False)
    assert r.status_code == 303

    # unlocked: the copy is a draft again and saves work
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "save"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "<b>Draft</b>" in f.get(f"/ui/reviews/{R}/document").text


def test_approve_without_a_request_is_refused(mkuser, docs):
    owner, _f = _seed_submitted(mkuser, docs)
    r = owner.post(f"/ui/reviews/{R}/approve-reopen/F. Miccoli")
    assert r.status_code == 409


def test_only_the_copy_owner_requests_and_only_owner_or_admin_approves(mkuser, docs):
    owner, f = _seed_submitted(mkuser, docs)
    other = mkuser("rbianchi", "R. Bianchi")
    owner.post(f"/reviews/{R}/reviewers", json={"name": "R. Bianchi", "role": "reviewer"})

    assert other.post(f"/ui/reviews/{R}/request-reopen").status_code == 409  # no submitted copy of their own
    f.post(f"/ui/reviews/{R}/request-reopen")
    assert other.post(f"/ui/reviews/{R}/approve-reopen/F. Miccoli").status_code == 403


def test_admin_reopen_submission_still_works_without_request(admin, mkuser, docs):
    _owner, f = _seed_submitted(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    r = admin.post(f"/ui/reviews/{R}/reopen-submission/F.%20Miccoli", follow_redirects=False)
    assert r.status_code == 303
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "save"},
        follow_redirects=False,
    )
    assert r.status_code == 303
