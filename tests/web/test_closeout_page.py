"""Closeout endpoints (v3 step 02 task 2, amended by v3.1 step 01): ``POST
/ui/reviews/{id}/closeout`` — the linked save — the explicit per-RID ``POST
.../rids/{rid}/implement`` action, and the two legacy GETs (``/closeout`` and
v2's ``/implement``) that now redirect into the unified document viewer, where
the workspace lives since v3.1.

Mirrors ``tests/web/test_lifecycle_v3_web.py``'s seed-helper style (each test
module owns its own fixtures over the shared ``mkuser``/``docs`` fixtures)."""

from __future__ import annotations

import json

R = "SIN-SRS-R1"


def _payload(page_text: str) -> dict:
    """The viewer's embedded JSON — the queue lives here since v3.1 step 01."""
    marker = '<script type="application/json" id="viewer-data">'
    start = page_text.index(marker) + len(marker)
    return json.loads(page_text[start : page_text.index("</script>", start)])


def _rid(client, rid: str = "SIN-SRS-0001") -> dict:
    data = _payload(client.get(f"/ui/reviews/{R}/document").text)
    return next(x for x in data["rids"] if x["rid"] == rid)


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


def test_closeout_get_redirects_to_the_document(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    r = owner.get(f"/ui/reviews/{R}/closeout", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/document"


def test_rejected_save_re_renders_the_document_with_the_unsaved_text(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)
    edited = docs["baseline"].replace("shall", "must", 1)

    r = owner.post(f"/ui/reviews/{R}/closeout", data={"content": edited, "rids": []})

    assert r.status_code == 422
    assert "at least one accepted RID" in r.text
    assert 'id="doc-edit"' in r.text          # still the document page
    assert "must" in r.text                    # the unsaved edit survived


# --------------------------------------------------------------------------- #
# POST /closeout (save)
# --------------------------------------------------------------------------- #


def test_post_closeout_save_with_ticked_rid_links_version_and_unlocks_mark_implemented(
    mkuser, docs
):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    # nothing linked yet: the card offers no Mark implemented (v3.1 gates it on
    # hasChange, the same condition the server's implement gate checks)
    assert _rid(owner)["hasChange"] is False

    new_content = docs["baseline"] + "\nbounded.\n"
    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": new_content, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # v3.2 point 13: the save closes an implementation session, so it lands on
    # the card it just closed rather than on the bare document.
    assert r.headers["location"] == f"/ui/reviews/{R}/document?focus=SIN-SRS-0001"

    # the RID carries a linked change — and, since v3.2, the save that created
    # it also implemented the finding: closing a session is one gesture, not a
    # save followed by a separate "Mark implemented".
    assert _rid(owner)["hasChange"] is True
    assert _rid(owner)["status"] == "implemented"
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
    rid = _rid(owner)
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
