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


# --------------------------------------------------------------------------- #
# v1.6: Save (draft) vs Submit in the reviewer editor
# --------------------------------------------------------------------------- #


def _submitted_at(app):
    from sqlmodel import Session, select

    from malus.db.models import ReviewerCopy

    with Session(app.state.engine) as s:
        return s.exec(select(ReviewerCopy)).one().submitted_at


def test_save_draft_persists_harvests_and_stays_in_editor(mkuser, docs, app):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "save"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/edit-copy" in r.headers["location"]  # stays in the editor
    assert _submitted_at(app) is None  # draft, not submitted
    rids = f.get(f"/reviews/{R}/rids").json()
    assert any(x["kind"] == "COMM" for x in rids)  # Save harvested → visible in the table


def test_submit_marks_submitted_and_redirects_to_dashboard(mkuser, docs, app):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "submit"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/ui/reviews/{R}")  # back to the dashboard
    assert _submitted_at(app) is not None  # submitted


def test_save_draft_still_enforces_freeze_rule(mkuser, docs):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    tampered = docs["baseline"].replace("configurable", "tunable")
    r = f.post(f"/ui/reviews/{R}/edit-copy", data={"content": tampered, "action": "save"})
    assert r.status_code == 422 and "Rejected" in r.text


def test_editor_has_save_and_submit_buttons(mkuser, docs):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    page = f.get(f"/ui/reviews/{R}/edit-copy").text
    assert 'name="action" value="save"' in page
    assert 'name="action" value="submit"' in page


def test_editor_form_opts_out_of_hx_boost(mkuser, docs):
    # hx-boost (htmx 2.x) drops the submit button's `action` value, so a boosted
    # form would send neither save nor submit and fall back to the default —
    # "Save draft" would wrongly submit. The form must submit natively so the
    # clicked button's value reaches the server (verified live in the browser).
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    page = f.get(f"/ui/reviews/{R}/edit-copy").text
    assert 'id="rev-form"' in page and 'hx-boost="false"' in page


def test_editor_shows_saved_flash_and_draft_state(mkuser, docs):
    _owner, f, _mod = _seed_frozen(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "save"})
    page = f.get(f"/ui/reviews/{R}/edit-copy?saved=1").text
    assert "Saved" in page  # the "Saved ✓" flash
    assert "Draft" in page  # the copy-state line reflects the un-submitted draft
