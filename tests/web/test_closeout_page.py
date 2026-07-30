"""Closeout workspace page (v3 step 02 task 2): GET/POST
``/ui/reviews/{id}/closeout`` — the owner's work queue + linked-save editor —
plus the explicit per-RID ``POST .../rids/{rid}/implement`` action, and the
legacy v2 ``/implement`` route now redirecting here.

Mirrors ``tests/web/test_lifecycle_v3_web.py``'s seed-helper style (each test
module owns its own fixtures over the shared ``mkuser``/``docs`` fixtures)."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_answered(mkuser, docs):
    """Owner + reviewer + moderator; freeze, harvest one COMM RID
    (SIN-SRS-0001), owner accepts it (still in_review)."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
    )
    return owner, f, mod


def _to_closeout(owner, f, mod):
    """Accept the (already answered) RID and flip the review into closeout."""
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")


# --------------------------------------------------------------------------- #
# GET /closeout
# --------------------------------------------------------------------------- #


def test_get_closeout_page_as_owner_shows_queue_and_editor(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    page = owner.get(f"/ui/reviews/{R}/closeout")
    assert page.status_code == 200
    assert "SIN-SRS-0001" in page.text          # queued finding
    assert "To implement" in page.text          # queue group label
    assert 'id="editor"' in page.text and 'id="preview"' in page.text  # editor grid


def test_get_closeout_page_reviewer_is_403(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    assert f.get(f"/ui/reviews/{R}/closeout").status_code == 403


def test_get_closeout_page_blocked_outside_closeout(mkuser, docs):
    owner, f, _mod = _seed_answered(mkuser, docs)
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")  # closed, but still in_review

    assert owner.get(f"/ui/reviews/{R}/closeout").status_code == 409


# --------------------------------------------------------------------------- #
# POST /closeout (save)
# --------------------------------------------------------------------------- #


def test_post_closeout_save_with_ticked_rid_links_version_and_unlocks_mark_implemented(
    mkuser, docs
):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)
    mark_action = f'action="/ui/reviews/{R}/rids/SIN-SRS-0001/implement"'

    before = owner.get(f"/ui/reviews/{R}/closeout").text
    assert mark_action not in before  # nothing linked yet: Mark implemented not offered

    new_content = docs["baseline"] + "\nbounded.\n"
    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": new_content, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/closeout"

    # the RID queue moved: it now carries a linked change, so Mark implemented unlocks
    after = owner.get(f"/ui/reviews/{R}/closeout").text
    assert mark_action in after
    assert "SIN-SRS-0001" in owner.get(f"/reviews/{R}/traceability").json()["referenced"]


def test_post_closeout_save_without_rids_is_422_and_preserves_typed_content(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    typed = docs["baseline"] + "\nsome half-finished edit\n"
    r = owner.post(f"/ui/reviews/{R}/closeout", data={"content": typed})
    assert r.status_code == 422
    assert "at least one accepted" in r.text  # the service's ValueError re-rendered
    assert typed in r.text                    # the unsaved editor text is preserved


# --------------------------------------------------------------------------- #
# POST /rids/{rid}/implement (explicit Mark implemented)
# --------------------------------------------------------------------------- #


def test_post_mark_implemented_with_linked_change_succeeds(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": docs["baseline"] + "\nbounded.\n", "rids": ["SIN-SRS-0001"]},
    )

    r = owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement", follow_redirects=False)
    assert r.status_code == 303
    # v3.1 step 01: back to the finding's card in the viewer, not the retired page
    assert r.headers["location"] == f"/ui/reviews/{R}/document?focus=SIN-SRS-0001"
    assert owner.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()["status"] == "implemented"


def test_post_mark_implemented_without_linked_change_is_422(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    r = owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement")
    assert r.status_code == 422


def test_post_mark_implemented_with_resolution_persists_it(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": docs["baseline"] + "\nbounded.\n", "rids": ["SIN-SRS-0001"]},
    )

    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement",
        data={"resolution": "bounded the timeout to 30s"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # the recorded resolution reaches the unified viewer's embedded JSON payload
    viewer = owner.get(f"/ui/reviews/{R}/document?focus=SIN-SRS-0001").text
    assert '"resolution": "bounded the timeout to 30s"' in viewer

    # v3.1 step 01: the queue lives in that payload now (the standalone page is
    # gone) — the RID moved to the "awaiting verification" bucket
    import json

    payload = json.loads(
        viewer.split('<script type="application/json" id="viewer-data">')[1].split("</script>")[0]
    )
    rid = next(x for x in payload["rids"] if x["rid"] == "SIN-SRS-0001")
    assert rid["queue"] == "awaiting"
    assert rid["resolution"] == "bounded the timeout to 30s"


# --------------------------------------------------------------------------- #
# legacy v2 /implement route
# --------------------------------------------------------------------------- #


def test_get_implement_legacy_redirects_to_closeout(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    r = owner.get(f"/ui/reviews/{R}/implement", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/closeout"


def test_post_implement_legacy_route_removed(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    r = owner.post(f"/ui/reviews/{R}/implement", data={"content": "x"})
    assert r.status_code in (404, 405)
