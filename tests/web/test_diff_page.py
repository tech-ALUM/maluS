"""Full-diff page (v3 step 03 task 4): ``GET /ui/reviews/{id}/diff`` — the
whole document, baseline vs latest version, rendered with the same
``malus.diffing.html_diff`` word-level renderer as the per-RID Changes
section (task 3). Any review member or a global admin may open it — same
authz as ``document_page`` (``tests/web/test_document_viewer.py``). Mirrors
``tests/web/test_closeout_page.py``'s seed-helper style."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_answered(mkuser, docs):
    """Owner + reviewer; freeze, harvest one COMM RID (SIN-SRS-0001), owner
    accepts it (still in_review)."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
    )
    return owner, f


def _to_closeout(owner, f):
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")


def test_member_get_diff_after_linked_save_shows_ins(mkuser, docs):
    owner, f = _seed_answered(mkuser, docs)
    _to_closeout(owner, f)
    new_content = docs["baseline"].replace("configurable", "bounded")
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": new_content, "rids": ["SIN-SRS-0001"]},
    )

    page = owner.get(f"/ui/reviews/{R}/diff")
    assert page.status_code == 200
    assert "<ins>" in page.text
    assert "Full diff" in page.text
    assert "baseline v1" in page.text and "v2" in page.text

    # a plain reviewer member gets the same page, not just the owner
    r_page = f.get(f"/ui/reviews/{R}/diff")
    assert r_page.status_code == 200
    assert "<ins>" in r_page.text


def test_non_member_get_diff_is_403(mkuser, docs):
    owner, f = _seed_answered(mkuser, docs)
    _to_closeout(owner, f)

    outsider = mkuser("out", "Out Sider")
    assert outsider.get(f"/ui/reviews/{R}/diff").status_code == 403


def test_admin_is_never_blocked(admin, mkuser, docs):
    owner, f = _seed_answered(mkuser, docs)
    _to_closeout(owner, f)

    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    assert admin.get(f"/ui/reviews/{R}/diff").status_code == 200


def test_identical_baseline_and_latest_shows_no_changes_yet(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})

    page = owner.get(f"/ui/reviews/{R}/diff")
    assert page.status_code == 200
    assert "No changes yet." in page.text
    assert "<ins>" not in page.text and "<del>" not in page.text


def test_get_diff_before_baseline_frozen_is_409(mkuser):
    owner = mkuser("owner", "A. Boffi")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})

    assert owner.get(f"/ui/reviews/{R}/diff").status_code == 409


def test_served_document_viewer_js_contains_cp_changes_renderer(client):
    # cheap smoke that the task-3 Changes-section renderer shipped (task 3
    # brief's own approach) — the diff page shares its CSS with this renderer.
    js = client.get("/static/document-viewer.js").text
    assert "cp-changes" in js
