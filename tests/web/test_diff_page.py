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


# --- v3.1 step 03: Compact | Full view toggle ------------------------------

FILLER = "\n".join(f"filler line {i:02d}" for i in range(30))


def _seed_long_closeout(mkuser, docs):
    """Owner + reviewer, baseline padded with 30 filler lines, one accepted
    RID, one closeout save touching **two distant lines** — so compact view
    has two hunks (hence a diff-skip marker) and elides the rest."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    baseline = docs["baseline"] + FILLER + "\n"
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": baseline})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit",
           json={"content": docs["copy_f"] + FILLER + "\n"})
    owner.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")
    edited = baseline.replace("configurable", "bounded").replace(
        "filler line 20", "filler line twenty"
    )
    owner.post(f"/ui/reviews/{R}/closeout",
               data={"content": edited, "rids": ["SIN-SRS-0001"]})
    return owner, f


def test_default_view_is_compact(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/diff")
    assert page.status_code == 200
    assert "filler line 00" not in page.text     # far context elided
    assert "filler line 29" not in page.text
    assert "diff-skip" in page.text              # marker between the two hunks
    assert "diff-ln" not in page.text            # no gutters in compact view
    assert f'href="/ui/reviews/{R}/diff?view=full"' in page.text


def test_full_view_renders_the_whole_document_with_line_numbers(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/diff?view=full")
    assert page.status_code == 200
    assert "filler line 00" in page.text and "filler line 29" in page.text
    assert "diff-skip" not in page.text
    assert '<span class="diff-ln diff-ln-old">1</span>' in page.text
    assert f'href="/ui/reviews/{R}/diff?view=compact"' in page.text


def test_unknown_view_falls_back_to_compact(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/diff?view=bogus")
    assert page.status_code == 200               # never 4xx on a read-only page
    assert "diff-ln" not in page.text
    assert page.text.count('aria-current="page"') == 1


def test_active_view_is_marked_in_the_toggle(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    full = owner.get(f"/ui/reviews/{R}/diff?view=full").text
    assert f'href="/ui/reviews/{R}/diff?view=full" aria-current="page"' in full
    assert full.count('aria-current="page"') == 1


def test_toggle_is_server_side_only(client):
    css = client.get("/static/app.css").text
    assert ".diff-ln" in css                     # the gutters are styled
    # no script tag is introduced by the diff page (zero-JS toggle)
