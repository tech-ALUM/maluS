"""Closeout payload in the unified viewer (v3.1 step 01 task 1): the work
queue the standalone workspace used to build now rides in ``#viewer-data``.
Seed helpers mirror ``tests/web/test_closeout_page.py``."""

from __future__ import annotations

import json

R = "SIN-SRS-R1"


def _payload(page_text: str) -> dict:
    marker = '<script type="application/json" id="viewer-data">'
    start = page_text.index(marker) + len(marker)
    end = page_text.index("</script>", start)
    return json.loads(page_text[start:end])


def _seed_closeout(mkuser, docs):
    """Owner + reviewer; one accepted RID, review flipped into closeout."""
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
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")
    return owner, f


def test_owner_gets_the_work_queue_in_the_viewer_payload(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)

    data = _payload(owner.get(f"/ui/reviews/{R}/document").text)

    assert data["canEditDoc"] is True
    assert data["latest"] == docs["baseline"]
    rid = next(r for r in data["rids"] if r["rid"] == "SIN-SRS-0001")
    assert rid["queue"] == "todo"
    assert rid["hasChange"] is False


def test_reviewer_sees_the_queue_but_may_not_edit(mkuser, docs):
    _owner, f = _seed_closeout(mkuser, docs)

    data = _payload(f.get(f"/ui/reviews/{R}/document").text)

    assert data["canEditDoc"] is False
    rid = next(r for r in data["rids"] if r["rid"] == "SIN-SRS-0001")
    assert rid["queue"] == "todo"


def test_closeout_form_posts_to_the_closeout_endpoint(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)

    html = owner.get(f"/ui/reviews/{R}/document").text

    assert f'action="/ui/reviews/{R}/closeout"' in html
    assert 'id="doc-edit"' in html
    assert 'id="doc-mode-edit"' in html          # the Render|Edit toggle
    assert 'id="content-src"' not in html        # the reviewer textarea is absent


def test_reviewer_in_closeout_gets_no_editor_and_no_popover(mkuser, docs):
    _owner, f = _seed_closeout(mkuser, docs)

    html = f.get(f"/ui/reviews/{R}/document").text

    assert 'id="doc-edit"' not in html
    assert 'id="cmt-pop"' not in html            # commenting is over in closeout


def test_unsubmitted_reviewer_cannot_comment_in_closeout(mkuser, docs):
    """The v3 defect the phase gate closes: a reviewer whose copy is still a
    draft could open the selection popover in closeout (the server refused the
    save, but the affordance existed). ``mySubmitted`` alone does not cover it —
    the closeout gate must be the phase."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    t = mkuser("tpanseri", "T. Panseri")  # never submits: copy stays a draft
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "T. Panseri", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    assert owner.post(f"/ui/reviews/{R}/start-closeout").status_code in (200, 303)

    html = t.get(f"/ui/reviews/{R}/document").text

    assert _payload(html)["mySubmitted"] is False  # the draft state is real
    assert 'id="cmt-pop"' not in html              # …and still no popover
    assert 'value="submit"' not in html            # nor the Save/Submit bar


def test_saving_from_the_document_links_the_ticked_rid(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)
    edited = docs["baseline"].replace("shall", "must", 1)

    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": edited, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )

    assert r.status_code == 303
    data = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    rid = next(x for x in data["rids"] if x["rid"] == "SIN-SRS-0001")
    assert rid["hasChange"] is True
    assert data["latest"] == edited


def test_mark_implemented_returns_to_the_document_focused(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": docs["baseline"].replace("shall", "must", 1), "rids": ["SIN-SRS-0001"]},
    )

    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement",
        data={"resolution": "reworded"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/document?focus=SIN-SRS-0001"


def test_in_review_carries_no_queue(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{R}/harvest")

    data = _payload(owner.get(f"/ui/reviews/{R}/document").text)

    assert data["canEditDoc"] is False
    assert all(r["queue"] is None for r in data["rids"])
