"""v3.2 step 04 — one implementation session, one transaction.

The owner opens a finding, the editor unlocks for it, they change the document
and close it. That one gesture used to be two calls that could half-succeed:
a version saved and linked, the finding still sitting in *To implement*.
"""

from __future__ import annotations

import json
import re

R = "SIN-SRS-I1"

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
).replace(
    "All measurements are written to disk in CSV format.",
    "All measurements are written to disk in CSV format. "
    "{COMM|type=technical|sev=major: bound the timeout, it is unbounded here too}",
)

EDITED = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable, bounded to at most 30 s.",
)


def _viewer_data(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="viewer-data">(.*?)</script>', html, re.S)
    assert m
    return json.loads(m.group(1))


def _rid(data: dict, rid: str) -> dict:
    return next(r for r in data["rids"] if r["rid"] == rid)


def _seed(mkuser):
    """Closeout, two accepted findings — the second stands in for a duplicate
    the same edit resolves."""
    owner = mkuser("i1owner", "I1 Owner")
    reviewer = mkuser("i1rev", "I1 Reviewer")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "I1 Reviewer", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE})
    reviewer.post(f"/reviews/{R}/copies/I1 Reviewer/submit", json={"content": COPY})

    rids = [r["rid"] for r in owner.get(f"/reviews/{R}/rids").json()]
    for rid in rids:
        owner.post(
            f"/ui/reviews/{R}/rids/{rid}/dispose",
            data={"disposition": "accepted", "reply": "Agreed.", "resolution": ""},
            follow_redirects=False,
        )
        reviewer.post(f"/ui/reviews/{R}/rids/{rid}/accept", follow_redirects=False)
    owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    return owner, reviewer, rids


def test_closing_a_session_saves_links_and_implements_in_one_go(mkuser):
    owner, _reviewer, rids = _seed(mkuser)

    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": EDITED, "rids": [rids[0]], "resolution": "Bounded to 30 s."},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"?focus={rids[0]}")  # lands on the card just closed

    row = owner.get(f"/reviews/{R}/rids/{rids[0]}").json()
    assert row["status"] == "implemented"          # no second gesture needed
    assert row["resolution"] == "Bounded to 30 s."
    assert rids[0] in owner.get(f"/reviews/{R}/traceability").json()["referenced"]

    data = _viewer_data(owner.get(f"/ui/reviews/{R}/document").text)
    assert _rid(data, rids[0])["queue"] == "awaiting"
    assert _rid(data, rids[1])["queue"] == "todo"   # untouched by this session


def test_duplicates_attached_at_close_are_implemented_too(mkuser):
    owner, _reviewer, rids = _seed(mkuser)

    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": EDITED, "rids": rids},     # session RID first, duplicate after
        follow_redirects=False,
    )

    statuses = {r["rid"]: r["status"] for r in owner.get(f"/reviews/{R}/rids").json()}
    assert statuses[rids[0]] == "implemented"
    assert statuses[rids[1]] == "implemented"
    referenced = owner.get(f"/reviews/{R}/traceability").json()["referenced"]
    assert rids[0] in referenced and rids[1] in referenced


def test_a_refused_finding_leaves_no_version_behind(mkuser):
    """The whole session is one transaction: if any finding fails its guard,
    the document must not have moved either."""
    owner, reviewer, rids = _seed(mkuser)
    before = owner.get(f"/ui/reviews/{R}/document").text
    ordinal_before = _viewer_data(before)["latestOrdinal"]

    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": EDITED, "rids": [rids[0], "SIN-SRS-9999"]},
        follow_redirects=False,
    )
    assert r.status_code == 422

    assert _viewer_data(owner.get(f"/ui/reviews/{R}/document").text)["latestOrdinal"] == ordinal_before
    assert owner.get(f"/reviews/{R}/rids/{rids[0]}").json()["status"] == "closed"
    assert rids[0] not in owner.get(f"/reviews/{R}/traceability").json()["referenced"]


def test_unchanged_text_is_still_refused(mkuser):
    owner, _reviewer, rids = _seed(mkuser)
    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": BASELINE, "rids": [rids[0]]},
        follow_redirects=False,
    )
    assert r.status_code == 422
    assert owner.get(f"/reviews/{R}/rids/{rids[0]}").json()["status"] == "closed"


def test_a_session_with_no_finding_is_refused(mkuser):
    owner, _reviewer, _rids = _seed(mkuser)
    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": EDITED, "rids": []},
        follow_redirects=False,
    )
    assert r.status_code == 422


def test_the_owner_still_cannot_reach_verified(mkuser):
    """Folding implement into the save must not widen what the owner may do."""
    owner, _reviewer, rids = _seed(mkuser)
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": EDITED, "rids": [rids[0]]},
        follow_redirects=False,
    )
    r = owner.post(f"/ui/reviews/{R}/rids/{rids[0]}/verify", follow_redirects=False)
    assert r.status_code in (403, 409)
    assert owner.get(f"/reviews/{R}/rids/{rids[0]}").json()["status"] == "implemented"
