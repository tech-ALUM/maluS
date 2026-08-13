"""v3.2 step 03 — the comment card.

Point 7 (one bin), point 9 (sections closed) and the disposition lock are JS,
so what is asserted here is what the server can be held to: the payload the
viewer builds its card from, and the rework request that used to be readable
only as a substring of the owner's own reply field (point 10).
"""

from __future__ import annotations

import json
import re

R = "SIN-SRS-C1"

BASELINE = """# Sensor Interface Requirements

## 2. Timeouts

The acquisition timeout shall be configurable.

## 3. Logging

All measurements are written to disk in CSV format.
"""

COPY = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable. "
    "{COMM|type=technical|sev=major: bound the timeout to at most 30 s}",
)

IMPLEMENTED = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable, bounded to at most 30 s.",
)

REASON = "Say what happens when the bound is exceeded."


def _viewer_data(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" id="viewer-data">(.*?)</script>', html, re.S
    )
    assert match, "viewer-data payload not found"
    return json.loads(match.group(1))


def _rid(data: dict, rid: str) -> dict:
    return next(r for r in data["rids"] if r["rid"] == rid)


def _seed_rework(mkuser):
    """A review in closeout with one accepted finding sent back for rework."""
    owner = mkuser("c1owner", "C1 Owner")
    reviewer = mkuser("c1rev", "C1 Reviewer")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "C1 Reviewer", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE})
    reviewer.post(f"/reviews/{R}/copies/C1 Reviewer/submit", json={"content": COPY})

    rid = owner.get(f"/reviews/{R}/rids").json()[0]["rid"]
    owner.post(
        f"/ui/reviews/{R}/rids/{rid}/dispose",
        data={"disposition": "accepted", "reply": "Agreed.", "resolution": ""},
        follow_redirects=False,
    )
    reviewer.post(f"/ui/reviews/{R}/rids/{rid}/accept", follow_redirects=False)
    owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": IMPLEMENTED, "rids": [rid]},
        follow_redirects=False,
    )
    # the save above already implemented it (v3.2 point 13); no second gesture
    return owner, reviewer, rid


def test_a_rework_request_is_carried_by_its_own_columns(mkuser):
    owner, reviewer, rid = _seed_rework(mkuser)

    reviewer.post(
        f"/ui/reviews/{R}/rids/{rid}/request-changes",
        data={"reason": REASON},
        follow_redirects=False,
    )

    data = _viewer_data(owner.get(f"/ui/reviews/{R}/document").text)
    rework = _rid(data, rid)["rework"]
    assert rework is not None, "the owner's payload must carry the request"
    assert rework["reason"] == REASON
    assert rework["by"] == "C1 Reviewer"
    assert rework["at"]


def test_the_queue_buckets_from_the_column_not_from_the_reply_text(mkuser):
    """The owner writing the marker into their own reply must not fake a
    rework: the bucket reads ``rework_at``, and only the reviewer sets it."""
    owner, reviewer, rid = _seed_rework(mkuser)
    reviewer.post(
        f"/ui/reviews/{R}/rids/{rid}/request-changes",
        data={"reason": REASON},
        follow_redirects=False,
    )

    data = _viewer_data(owner.get(f"/ui/reviews/{R}/document").text)
    assert _rid(data, rid)["queue"] == "rework"

    # the owner re-implements: the request is answered, so it stops showing
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": IMPLEMENTED + "\nBeyond the bound the driver aborts.\n", "rids": [rid]},
        follow_redirects=False,
    )

    data = _viewer_data(owner.get(f"/ui/reviews/{R}/document").text)
    assert _rid(data, rid)["queue"] == "awaiting"
    assert _rid(data, rid)["rework"] is None


def test_a_finding_never_reworked_carries_no_request(mkuser):
    owner, _reviewer, rid = _seed_rework(mkuser)
    data = _viewer_data(owner.get(f"/ui/reviews/{R}/document").text)
    assert _rid(data, rid)["rework"] is None
    assert _rid(data, rid)["queue"] == "awaiting"


def test_the_reply_still_carries_the_note_for_report_and_pdf(mkuser):
    """The columns are the new authority for logic; the human-readable trace in
    ``reply`` is what report.md, the PDF and the timeline read, and it stays."""
    _owner, reviewer, rid = _seed_rework(mkuser)
    reviewer.post(
        f"/ui/reviews/{R}/rids/{rid}/request-changes",
        data={"reason": REASON},
        follow_redirects=False,
    )
    reply = reviewer.get(f"/reviews/{R}/rids/{rid}").json()["reply"]
    assert "[changes requested by C1 Reviewer:" in reply
    assert REASON in reply
