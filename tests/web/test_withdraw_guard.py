"""v3 withdraw guard: a vanished comment block may withdraw only an OPEN finding.

Field bug: a reviewer deleting an answered comment's block from their copy and
saving silently drove the RID answered -> withdrawn (an edge the transition
graph forbids), erasing the owner's disposition. The save must be refused
before anything is persisted.
"""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed_answered(mkuser, docs):
    """Review with one RID disposed accepted; returns (owner, reviewer) clients."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "agreed"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return owner, f


def test_save_that_drops_an_answered_block_is_refused(mkuser, docs):
    _owner, f = _seed_answered(mkuser, docs)

    # the copy without the comment block = the pristine baseline
    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["baseline"], "action": "save"},
    )
    assert r.status_code == 422
    assert "SIN-SRS-0001" in r.text and "reopen" in r.text

    # nothing was persisted: the RID keeps its disposition, the copy its block
    view = f.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert '"status": "answered"' in view
    assert '"disposition": "accepted"' in view
    assert "bound the timeout" in view  # myCopy still contains the block


def test_save_that_drops_an_open_block_still_withdraws(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")

    r = f.post(
        f"/ui/reviews/{R}/edit-copy",
        data={"content": docs["baseline"], "action": "save"},
        follow_redirects=False,
    )
    assert r.status_code == 303  # legal: open -> withdrawn (or purged if pristine)
