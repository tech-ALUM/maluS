"""Web GUI wiring for the v3 lifecycle actions (Task 7): accept, request-changes,
start-closeout, reopen-review — the same services + authorization as the JSON
API (mirrors ``tests/api/test_lifecycle_v3.py``), driven through the
``/ui/...`` browser routes, plus the phase-aware dashboard rendering."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_open(mkuser, docs):
    """Owner + reviewer + moderator; freeze, harvest one open COMM RID
    (SIN-SRS-0001)."""
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


def _seed_answered(mkuser, docs, *, disposition: str = "accepted"):
    """``_seed_open`` plus the owner answering the RID via the browser form."""
    owner, f, mod = _seed_open(mkuser, docs)
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": disposition, "reply": "ok", "resolution": ""},
    )
    return owner, f, mod


def _to_closeout(owner, f, mod):
    """Accept the (already answered) RID and flip the review into closeout."""
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")


# --------------------------------------------------------------------------- #
# accept
# --------------------------------------------------------------------------- #


def test_accept_web_reviewer_closes_and_redirects_to_focus(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    r = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("?focus=SIN-SRS-0001")
    assert owner.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()["status"] == "closed"


def test_accept_web_owner_is_403(mkuser, docs):
    owner, _f, _mod = _seed_answered(mkuser, docs)
    r = owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept", follow_redirects=False)
    assert r.status_code == 403


def test_accept_web_unknown_rid_is_404(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    r = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-9999/accept", follow_redirects=False)
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# start-closeout
# --------------------------------------------------------------------------- #


def test_start_closeout_web_gate_satisfied_flips_phase(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")

    r = owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    assert r.status_code == 303
    assert owner.get(f"/reviews/{R}").json()["status"] == "closeout"


def test_start_closeout_web_gate_unsatisfied_is_409(mkuser, docs):
    owner, _f, _mod = _seed_open(mkuser, docs)  # RID still open: gate unmet
    r = owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    assert r.status_code == 409


def test_start_closeout_web_forbidden_for_non_owner(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    r = f.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# request-changes
# --------------------------------------------------------------------------- #


def test_request_changes_web_in_closeout_returns_rid_to_closed(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, _mod)
    owner.post(
        f"/reviews/{R}/changes",
        json={"content": docs["baseline"] + "\nbounded.\n", "rids": ["SIN-SRS-0001"]},
    )
    owner.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"status": "implemented"})

    r = f.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/request-changes",
        data={"reason": "still not bounded"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"].endswith("?focus=SIN-SRS-0001")
    detail = owner.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()
    assert detail["status"] == "closed"
    assert "still not bounded" in detail["reply"]


def test_request_changes_web_before_closeout_is_409(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")  # closed, but still in_review

    r = f.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/request-changes",
        data={"reason": "too soon"},
        follow_redirects=False,
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# reopen-review
# --------------------------------------------------------------------------- #


def test_reopen_review_web_non_admin_is_403(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    assert owner.post(f"/ui/reviews/{R}/reopen-review", follow_redirects=False).status_code == 403
    assert f.post(f"/ui/reviews/{R}/reopen-review", follow_redirects=False).status_code == 403


def test_reopen_review_web_admin_success(mkuser, docs, admin):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    r = admin.post(f"/ui/reviews/{R}/reopen-review", follow_redirects=False)
    assert r.status_code == 303
    assert owner.get(f"/reviews/{R}").json()["status"] == "in_review"


# --------------------------------------------------------------------------- #
# dashboard: Start closeout button / gate hint / closeout workspace link
# --------------------------------------------------------------------------- #


def test_dashboard_shows_start_closeout_only_for_owner_when_gate_satisfied(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")  # gate satisfied: RID closed

    owner_page = owner.get(f"/ui/reviews/{R}").text
    assert "Start closeout" in owner_page

    rev_page = f.get(f"/ui/reviews/{R}").text
    assert "Start closeout" not in rev_page  # not the owner


def test_dashboard_hides_start_closeout_button_when_gate_unmet(mkuser, docs):
    owner, _f, _mod = _seed_open(mkuser, docs)  # RID still open
    page = owner.get(f"/ui/reviews/{R}").text
    assert "Start closeout" not in page
    assert "Closeout unlocks" in page


def test_dashboard_shows_closeout_workspace_link_and_admin_back_to_review(mkuser, docs, admin):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    owner_page = owner.get(f"/ui/reviews/{R}").text
    assert "Closeout workspace" in owner_page
    assert "Start closeout" not in owner_page
    assert "Back to review" not in owner_page  # owner is not an admin

    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    admin_page = admin.get(f"/ui/reviews/{R}").text
    assert "Back to review" in admin_page


# --------------------------------------------------------------------------- #
# closeout: the save is phase-gated to closeout only (v3); since v3.1 step 01
# the workspace GET redirects into the document viewer — see also the dedicated
# tests/web/test_closeout_page.py for the full route surface.
# --------------------------------------------------------------------------- #


def test_closeout_save_blocked_outside_closeout(mkuser, docs):
    """v3.1 step 01: the GET is a plain redirect into the viewer now, so the
    phase gate that matters is on the save (the service's ``PhaseError``)."""
    owner, f, _mod = _seed_answered(mkuser, docs)
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")  # closed, but still in_review

    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": docs["baseline"], "rids": []},
        follow_redirects=False,
    )
    assert r.status_code == 409


def test_closeout_get_redirects_into_the_viewer(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    r = owner.get(f"/ui/reviews/{R}/closeout", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/document"
