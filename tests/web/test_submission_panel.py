"""v1.6 dashboard reviewer submission panel (soft indicator): shows each
reviewer as not-started / draft / submitted, an N/M count, and an
all-submitted notice that blocks nothing."""

from __future__ import annotations

R = "SIN-SRS-R1"

COPY_R = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=editorial|sev=minor: reword this}

## 3.3 Logging

All measurements are written to disk in CSV format.
"""


def _seed_three_reviewers(mkuser, docs):
    """Owner + three reviewers (F, R, T) on a frozen review; none has commented."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    r = mkuser("rbianchi", "R. Bianchi")
    t = mkuser("tpanseri", "T. Panseri")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    for name in ("F. Miccoli", "R. Bianchi", "T. Panseri"):
        owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner, f, r, t


def test_panel_shows_each_reviewer_state_and_count(mkuser, docs):
    owner, f, r, _t = _seed_three_reviewers(mkuser, docs)
    # F submits; R saves a draft; T never touches it.
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    r.post(f"/ui/reviews/{R}/edit-copy", data={"content": COPY_R, "action": "save"})

    page = owner.get(f"/ui/reviews/{R}").text
    assert "1/3" in page  # only F is submitted (slim badge, v2.2)
    # all three reviewers appear with a state pill
    assert "submitted" in page and "draft" in page and "not started" in page
    # soft indicator: still waiting, nothing is blocked
    assert "waiting for 2" in page
    assert "all submitted" not in page


def test_panel_all_submitted_notice(mkuser, docs):
    owner, f, r, t = _seed_three_reviewers(mkuser, docs)
    for c in (f, r, t):
        c.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    page = owner.get(f"/ui/reviews/{R}").text
    assert "3/3" in page
    assert "all submitted ✓" in page
    assert "waiting for" not in page


def test_panel_soft_gate_does_not_block_disposition(mkuser, docs):
    # OTHER reviewers still pending never block a dispose; the disposed
    # comment's own copy must be submitted though (v3: no dispose on drafts)
    owner, f, _r, _t = _seed_three_reviewers(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok", "resolution": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303  # disposition went through despite pending reviewers
