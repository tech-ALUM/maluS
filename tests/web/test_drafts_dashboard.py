"""v3: draft comments (from unsubmitted copies) are visually separated in the
dashboard and cannot be disposed until the reviewer submits their copy."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_draft(mkuser, docs):
    """One reviewer comment saved as a DRAFT (copy not submitted)."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["copy_f"], "action": "save"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return owner, f


def test_draft_rid_marked_and_counted_in_dashboard(mkuser, docs):
    owner, _f = _seed_draft(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}").text
    assert "st-draft" in page and "row-draft" in page
    assert "1 draft" in page


def test_draft_flag_in_viewer_payload(mkuser, docs):
    owner, _f = _seed_draft(mkuser, docs)
    view = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"draft": true' in view


def test_dispose_refused_on_a_draft_comment(mkuser, docs):
    owner, f = _seed_draft(mkuser, docs)
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok"},
    )
    assert r.status_code == 409

    # once the reviewer submits, the same dispose goes through
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = owner.get(f"/ui/reviews/{R}").text
    assert "st-draft" not in page  # no longer a draft


def test_draft_facet_filters_rows(mkuser, docs):
    owner, _f = _seed_draft(mkuser, docs)
    assert "SIN-SRS-0001" in owner.get(f"/ui/reviews/{R}?f=draft:eq:yes").text
    assert "SIN-SRS-0001" not in owner.get(f"/ui/reviews/{R}?f=draft:eq:no").text
