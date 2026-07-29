"""Per-RID change diffs in the viewer payload (v3 step 03 task 2): once a
review reaches closeout/finalized, an accepted RID's post-baseline saves
surface as rendered diffs in the unified viewer's ``#viewer-data`` payload
(``rids[i].changes``); everyone else (in_review phase, non-accepted RIDs)
gets an empty list. Mirrors ``tests/web/test_document_viewer.py``'s payload
helper and ``tests/web/test_closeout_page.py``'s seed-helper style."""

from __future__ import annotations

import json

R = "SIN-SRS-R1"


def _payload(page_text: str) -> dict:
    marker = '<script type="application/json" id="viewer-data">'
    start = page_text.index(marker) + len(marker)
    end = page_text.index("</script>", start)
    return json.loads(page_text[start:end])


def _seed(mkuser, docs):
    """Owner + reviewer; a baseline containing the word 'quick', two COMM
    findings — SIN-SRS-0001 accepted, SIN-SRS-0002 rejected — both disposed
    and accepted by the reviewer (in_review, findings closed)."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    baseline = docs["baseline"].rstrip("\n") + "\n\nThe scan completes quick.\n"
    copy = (
        docs["copy_f"].rstrip("\n")
        + "\n\nThe scan completes quick. {COMM|type=editorial: word choice}\n"
    )
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": baseline})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": copy})
    owner.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok", "resolution": ""},
    )
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0002/dispose",
        data={"disposition": "rejected", "reply": "no", "resolution": ""},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0002/accept")
    return owner, f, baseline


def test_in_review_every_rid_has_no_changes(mkuser, docs):
    owner, _f, _baseline = _seed(mkuser, docs)
    # still in_review: both findings are closed but the review hasn't entered closeout
    d = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    assert len(d["rids"]) == 2
    assert all(r["changes"] == [] for r in d["rids"])


def test_closeout_accepted_rid_gets_diff_after_linked_save_rejected_stays_empty(mkuser, docs):
    owner, f, baseline = _seed(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/start-closeout")

    new_content = baseline.replace("quick", "slow")
    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": new_content, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )
    assert r.status_code == 303

    d = _payload(f.get(f"/ui/reviews/{R}/document").text)
    rid1 = next(x for x in d["rids"] if x["rid"] == "SIN-SRS-0001")
    rid2 = next(x for x in d["rids"] if x["rid"] == "SIN-SRS-0002")
    assert rid2["changes"] == []  # rejected — never gets a diff, even in closeout

    assert len(rid1["changes"]) == 1
    change = rid1["changes"][0]
    assert change["ordinal"] == 2
    assert "<ins>slow</ins>" in change["diffHtml"]
    assert isinstance(change["created"], str) and change["created"]
    assert change["note"] is None
