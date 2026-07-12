"""Editor + reviewer/owner workflow tests (v1 Step 6): comment & submit,
freeze-rule rejection at both layers, and owner implement -> version -> RID link."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_frozen(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner, f, mod


def test_reviewer_editor_page_renders(mkuser, docs):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    page = f.get(f"/ui/reviews/{R}/edit-copy")
    assert page.status_code == 200
    # v1.4: rendered A4 sheet + hidden content field (no visible textarea)
    assert "review copy" in page.text.lower()
    assert 'id="sheet"' in page.text and 'id="content-src"' in page.text


def test_reviewer_submits_valid_copy_and_it_harvests(mkuser, docs):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    r = f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"]}, follow_redirects=False)
    assert r.status_code == 303
    rids = f.get(f"/reviews/{R}/rids").json()
    assert any(x["kind"] == "COMM" for x in rids)  # submit triggered a harvest


def test_reviewer_tampering_is_rejected_server_side(mkuser, docs):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    tampered = docs["baseline"].replace("configurable", "tunable")  # edits baseline text
    r = f.post(f"/ui/reviews/{R}/edit-copy", data={"content": tampered})
    assert r.status_code == 422 and "Rejected" in r.text
    assert f.get(f"/reviews/{R}/rids").json() == []  # nothing was harvested


def test_owner_cannot_open_reviewer_editor(mkuser, docs):
    owner, _f, _mod = _seed_frozen(mkuser, docs)
    assert owner.get(f"/ui/reviews/{R}/edit-copy").status_code == 403


def test_owner_implement_creates_version_and_links_rid(mkuser, docs):
    owner, f, _mod = _seed_frozen(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"]})  # harvests SIN-SRS-0001
    owner.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "accepted", "reply": "ok"},
    )

    page = owner.get(f"/ui/reviews/{R}/implement")
    assert page.status_code == 200 and "SIN-SRS-0001" in page.text

    r = owner.post(
        f"/ui/reviews/{R}/implement",
        data={"content": docs["baseline"] + "\nbounded.\n", "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # the accepted RID is now implemented with a linked change (traceability)
    assert owner.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()["status"] == "implemented"
    assert "SIN-SRS-0001" in owner.get(f"/reviews/{R}/traceability").json()["referenced"]

    # and its reviewer can verify it
    assert f.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 200
