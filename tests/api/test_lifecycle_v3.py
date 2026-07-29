"""HTTP tests for the v3 lifecycle endpoints (Task 6, on top of the Task 4
services): accept, request-changes, start-closeout, reopen-review.

Mirrors the multi-actor auth style of ``test_api.py``/``test_auth.py``: a
fresh ``app`` + several ``mkuser`` clients over one in-memory DB.
"""

from __future__ import annotations

R = "SIN-SRS-R1"

BASELINE = """# Doc

Some sentence needing review.
"""

COPY = """# Doc

Some sentence needing review. {COMM|type=technical|sev=major: please clarify}
"""


def _review_with_one_rid(owner, f, mod) -> str:
    """Owner + one reviewer (F) + one moderator; freeze, F submits a single
    ``{COMM}``, moderator harvests. Returns the resulting RID id."""
    assert owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"}).status_code == 201
    assert owner.post(
        f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"}
    ).status_code == 200
    assert owner.post(
        f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"}
    ).status_code == 200
    assert owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE}).status_code == 200
    assert f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": COPY}).status_code == 200
    h = mod.post(f"/reviews/{R}/harvest")
    assert h.status_code == 200, h.text
    rids = h.json()["rids"]
    assert len(rids) == 1, rids
    return rids[0]["rid"]


def _answer(owner, rid_id: str, *, disposition: str = "accepted") -> None:
    resp = owner.patch(
        f"/reviews/{R}/rids/{rid_id}",
        json={"status": "answered", "disposition": disposition, "reply": "ok"},
    )
    assert resp.status_code == 200, resp.text


def _to_closeout_with_implemented_rid(owner, f, mod) -> str:
    """Drive a single-RID review from harvest through 'implemented', ready
    for a request-changes call."""
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 200
    assert owner.post(f"/reviews/{R}/start-closeout").status_code == 200
    assert owner.post(
        f"/reviews/{R}/changes", json={"content": BASELINE + "\nmore\n", "rids": [rid_id]}
    ).status_code == 200
    assert owner.patch(f"/reviews/{R}/rids/{rid_id}", json={"status": "implemented"}).status_code == 200
    return rid_id


# --------------------------------------------------------------------------- #
# accept
# --------------------------------------------------------------------------- #


def test_accept_reviewer_closes_own_rid(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)

    resp = f.post(f"/reviews/{R}/rids/{rid_id}/accept")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"


def test_accept_owner_is_403(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)

    assert owner.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 403


def test_accept_ai_principal_is_403(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    ai = mkuser("aibot", "AI Bot", is_ai=True)
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)

    assert ai.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 403


def test_accept_in_closeout_is_409(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 200
    assert owner.post(f"/reviews/{R}/start-closeout").status_code == 200

    # accept is an in_review-only action: once in closeout it's a phase
    # conflict (409), not a fresh closure-authority violation (403)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 409


# --------------------------------------------------------------------------- #
# start-closeout
# --------------------------------------------------------------------------- #


def test_start_closeout_gate_then_success(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _review_with_one_rid(owner, f, mod)

    # the RID is still open: the gate rejects entry into closeout
    resp = owner.post(f"/reviews/{R}/start-closeout")
    assert resp.status_code == 409
    assert "closed" in resp.json()["detail"]

    _answer(owner, rid_id)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 200

    resp = owner.post(f"/reviews/{R}/start-closeout")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closeout"


def test_start_closeout_forbidden_for_non_owner(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 200

    assert f.post(f"/reviews/{R}/start-closeout").status_code == 403


# --------------------------------------------------------------------------- #
# update_rid widened to in_review|closeout (v3 plan-table amendment)
# --------------------------------------------------------------------------- #


def test_patch_implemented_with_resolution_succeeds_in_closeout(app, mkuser):
    """update_rid (invoked by the PATCH .../implemented branch to persist
    reply/resolution before advancing the RID) used to be IN_REVIEW-only,
    which made recording a resolution at implementation time dead in every
    real flow: closeout PATCHes 409'd before `implement` ever ran. It is now
    allowed in_review OR closeout — only `answer`/dispose-from-open stays
    in_review-only."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 200
    assert owner.post(f"/reviews/{R}/start-closeout").status_code == 200
    assert owner.post(
        f"/reviews/{R}/changes", json={"content": BASELINE + "\nmore\n", "rids": [rid_id]}
    ).status_code == 200

    resp = owner.patch(
        f"/reviews/{R}/rids/{rid_id}",
        json={"status": "implemented", "resolution": "fixed per commit abc123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "implemented"
    assert resp.json()["resolution"] == "fixed per commit abc123"


# --------------------------------------------------------------------------- #
# request-changes
# --------------------------------------------------------------------------- #


def test_request_changes_without_reason_is_422(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _to_closeout_with_implemented_rid(owner, f, mod)

    resp = f.post(f"/reviews/{R}/rids/{rid_id}/request-changes", json={"reason": "   "})
    assert resp.status_code == 422, resp.text


def test_request_changes_success(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    rid_id = _to_closeout_with_implemented_rid(owner, f, mod)

    resp = f.post(f"/reviews/{R}/rids/{rid_id}/request-changes", json={"reason": "please redo it"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"


# --------------------------------------------------------------------------- #
# reopen-review
# --------------------------------------------------------------------------- #


def _to_closeout(owner, f, mod) -> str:
    rid_id = _review_with_one_rid(owner, f, mod)
    _answer(owner, rid_id)
    assert f.post(f"/reviews/{R}/rids/{rid_id}/accept").status_code == 200
    assert owner.post(f"/reviews/{R}/start-closeout").status_code == 200
    return rid_id


def test_reopen_review_non_admin_is_403(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    _to_closeout(owner, f, mod)

    assert owner.post(f"/reviews/{R}/reopen-review").status_code == 403
    assert f.post(f"/reviews/{R}/reopen-review").status_code == 403


def test_reopen_review_admin_success(app, mkuser, admin):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    _to_closeout(owner, f, mod)

    resp = admin.post(f"/reviews/{R}/reopen-review")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_review"


def test_reopen_review_ai_admin_is_403(app, mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    ai_admin = mkuser("aiadmin", "AI Admin", is_admin=True, is_ai=True)
    _to_closeout(owner, f, mod)

    assert ai_admin.post(f"/reviews/{R}/reopen-review").status_code == 403
