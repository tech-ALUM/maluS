"""Member colors (v2.1): admin-set global default (users.color) + per-review
override (review_members.color). Resolution: override → global → null
(deterministic palette fallback in the client)."""

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
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "save"})
    return owner, f


def test_admin_sets_global_color_and_it_resolves(admin, mkuser, docs):
    owner, _f = _seed(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    r = admin.post("/ui/admin/users/fmiccoli/color", data={"color": "#12ab34"}, follow_redirects=False)
    assert r.status_code == 303
    d = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    assert d["colors"]["F. Miccoli"] == "#12ab34"


def test_review_override_supersedes_global_and_resets(admin, mkuser, docs):
    owner, _f = _seed(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    admin.post("/ui/admin/users/fmiccoli/color", data={"color": "#12ab34"})

    r = owner.post(
        f"/ui/reviews/{R}/members/fmiccoli/color", data={"color": "#ff0000"}, follow_redirects=False
    )
    assert r.status_code == 303
    d = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    assert d["colors"]["F. Miccoli"] == "#ff0000"  # override wins

    owner.post(f"/ui/reviews/{R}/members/fmiccoli/color", data={"color": ""})  # reset
    d = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    assert d["colors"]["F. Miccoli"] == "#12ab34"  # back to the global default


def test_no_color_set_resolves_to_null_palette_fallback(mkuser, docs):
    owner, _f = _seed(mkuser, docs)
    d = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    assert d["colors"]["F. Miccoli"] is None


def test_color_authz_and_validation(admin, mkuser, docs):
    owner, f = _seed(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    # global color is admin-only
    assert owner.post("/ui/admin/users/fmiccoli/color", data={"color": "#12ab34"}).status_code == 403
    # review override is owner/admin-only
    assert f.post(f"/ui/reviews/{R}/members/fmiccoli/color", data={"color": "#ff0000"}).status_code == 403
    # bad hex → 422
    assert admin.post("/ui/admin/users/fmiccoli/color", data={"color": "red"}).status_code == 422
    assert owner.post(f"/ui/reviews/{R}/members/fmiccoli/color", data={"color": "#12"}).status_code == 422
