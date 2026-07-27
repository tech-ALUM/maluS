"""Unified document viewer (v2 step 4): one /document page for every role,
capabilities gated per role, all harvested comments in the payload, and the
old edit-copy page replaced by a redirect (its POST contract unchanged)."""

from __future__ import annotations

import json

R = "SIN-SRS-R1"


def _payload(page_text: str) -> dict:
    marker = '<script type="application/json" id="viewer-data">'
    start = page_text.index(marker) + len(marker)
    end = page_text.index("</script>", start)
    return json.loads(page_text[start:end])


def _seed(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    ai = mkuser("bot", "AI Bot", is_ai=True)
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    for name, role in [("F. Miccoli", "reviewer"), ("M. Mod", "moderator"), ("AI Bot", "reviewer")]:
        owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": role})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "save"})
    return owner, f, mod, ai


def test_document_page_per_role_capabilities(mkuser, docs):
    owner, f, mod, ai = _seed(mkuser, docs)

    d_owner = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    assert d_owner["canDispose"] is True and d_owner["isReviewer"] is False
    assert d_owner["myCopy"] is None

    d_f = _payload(f.get(f"/ui/reviews/{R}/document").text)
    assert d_f["isReviewer"] is True and d_f["canDispose"] is False
    assert d_f["myCopy"] and "{COMM" in d_f["myCopy"]

    d_mod = _payload(mod.get(f"/ui/reviews/{R}/document").text)
    assert d_mod["canDispose"] is False
    assert all(r["canVerify"] for r in d_mod["rids"])  # moderator verifies on behalf

    d_ai = _payload(ai.get(f"/ui/reviews/{R}/document").text)
    assert d_ai["canDispose"] is False
    assert all(not r["canVerify"] for r in d_ai["rids"])  # AI never closes


def test_document_payload_has_all_comments_with_offsets(mkuser, docs):
    owner, _f, _mod, _ai = _seed(mkuser, docs)
    d = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    # reviewer seats only — the moderator holds no copy and authors no comments
    assert d["reviewers"] == ["F. Miccoli", "AI Bot"]
    assert len(d["rids"]) == 1
    rid = d["rids"][0]
    assert rid["reviewer"] == "F. Miccoli" and rid["kind"] == "COMM"
    assert isinstance(rid["offset"], int) and rid["offset"] > 0
    assert d["baseline"] == docs["baseline"]


def test_document_requires_membership(admin, mkuser, docs):
    _seed(mkuser, docs)
    outsider = mkuser("out", "Out Sider")
    assert outsider.get(f"/ui/reviews/{R}/document").status_code == 403
    # a global admin is a superuser over every review (v1.10)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    assert admin.get(f"/ui/reviews/{R}/document").status_code == 200


def test_edit_copy_redirects_to_document(mkuser, docs):
    _owner, f, _mod, _ai = _seed(mkuser, docs)
    r = f.get(f"/ui/reviews/{R}/edit-copy", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/ui/reviews/{R}/document")


def test_post_contract_unchanged_and_422_renders_viewer(mkuser, docs):
    _owner, f, _mod, _ai = _seed(mkuser, docs)
    # valid save → 303 back to the document viewer
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "save"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and "/document" in r.headers["location"]
    # freeze violation → 422, re-rendering the viewer with the typed content
    tampered = docs["baseline"].replace("configurable", "tunable")
    r = f.post(f"/ui/reviews/{R}/edit-copy", data={"content": tampered, "action": "save"})
    assert r.status_code == 422 and "Rejected" in r.text
    assert 'id="viewer-data"' in r.text  # the viewer page, not a bare error
    assert _payload(r.text)["myCopy"] == tampered  # typed content not lost


# ---------------------------------------------------------------- focus mode


def test_finding_url_redirects_to_focus(mkuser, docs):
    owner, _f, _mod, _ai = _seed(mkuser, docs)
    r = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/ui/reviews/{R}/document?focus=SIN-SRS-0001")


def test_focus_payload_and_unknown_focus_404(mkuser, docs):
    owner, _f, _mod, _ai = _seed(mkuser, docs)
    d = _payload(owner.get(f"/ui/reviews/{R}/document?focus=SIN-SRS-0001").text)
    assert d["focus"] == "SIN-SRS-0001"
    assert owner.get(f"/ui/reviews/{R}/document?focus=SIN-SRS-9999").status_code == 404


def test_actions_redirect_back_to_focus(mkuser, docs):
    owner, f, _mod, _ai = _seed(mkuser, docs)
    # rejected → answered, from which the reviewer may verify directly
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "rejected", "reply": "out of scope", "resolution": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"].endswith("?focus=SIN-SRS-0001")
    r = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/verify", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("?focus=SIN-SRS-0001")
