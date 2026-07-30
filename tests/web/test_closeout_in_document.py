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
