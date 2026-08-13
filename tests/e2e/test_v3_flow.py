"""v3 end-to-end (docs/plan/v3/06-release.md, Task 1): the full v3.0.0
lifecycle — create+freeze, submit, harvest, disposition, disposition
acceptance, closeout (save/implement/verify), a request-changes round-trip,
finalize, and the finalized downloads — driven over the web routes with
three users (owner, reviewer, admin)."""

from __future__ import annotations

import json
import re

from malus import pdfgen

R = "SIN-SRS-V3"

BASELINE = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

COPY = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: bound the timeout to at most 30 s}

## 3.3 Logging

All measurements are written to disk in CSV format. {COMM|type=editorial|sev=minor: name the CSV columns}
"""

CLOSEOUT_CONTENT = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable, bounded to at most 30 s.",
)

CLOSEOUT_CONTENT_V2 = CLOSEOUT_CONTENT.replace(
    "bounded to at most 30 s.", "bounded to at most 30 seconds (inclusive)."
)


def _viewer_data(html: str) -> dict:
    """Pull the ``#viewer-data`` JSON payload out of the document viewer page."""
    match = re.search(
        r'<script type="application/json" id="viewer-data">(.*?)</script>', html, re.S
    )
    assert match, "viewer-data payload not found in document page"
    return json.loads(match.group(1))


def _rid_by(data: dict, rid: str) -> dict:
    return next(r for r in data["rids"] if r["rid"] == rid)


def test_full_v3_review_closeout_verify_finalize_flow(app, mkuser, docs=None):
    # --- admin provisions the two other accounts ---
    owner = mkuser("v3owner", "V3 Owner")
    reviewer = mkuser("v3reviewer", "V3 Reviewer")

    # --- owner creates the review, adds the reviewer, freezes the baseline ---
    assert owner.post(
        "/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"}
    ).status_code == 201
    assert owner.post(
        f"/reviews/{R}/reviewers", json={"name": "V3 Reviewer", "role": "reviewer"}
    ).status_code == 200
    assert owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE}).status_code == 200
    assert owner.get(f"/reviews/{R}").json()["status"] == "in_review"

    # --- reviewer submits a copy with 2 comments (submit re-harvests) ---
    assert reviewer.post(
        f"/reviews/{R}/copies/V3 Reviewer/submit", json={"content": COPY}
    ).status_code == 200
    rids = owner.get(f"/reviews/{R}/rids").json()
    assert len(rids) == 2
    timeout_rid = next(r["rid"] for r in rids if "timeout" in r["comment"])
    csv_rid = next(r["rid"] for r in rids if "CSV" in r["comment"])

    # --- owner disposes: accept the timeout finding, reject the CSV one ---
    assert owner.post(
        f"/ui/reviews/{R}/rids/{timeout_rid}/dispose",
        data={"disposition": "accepted", "reply": "Agreed, will bound it.", "resolution": ""},
        follow_redirects=False,
    ).status_code == 303
    assert owner.post(
        f"/ui/reviews/{R}/rids/{csv_rid}/dispose",
        data={"disposition": "rejected", "reply": "Out of scope for this release.", "resolution": ""},
        follow_redirects=False,
    ).status_code == 303
    assert owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()["status"] == "answered"
    assert owner.get(f"/reviews/{R}/rids/{csv_rid}").json()["status"] == "answered"

    # --- reviewer accepts both dispositions -> closed (still in_review) ---
    assert reviewer.post(
        f"/ui/reviews/{R}/rids/{timeout_rid}/accept", follow_redirects=False
    ).status_code == 303
    assert reviewer.post(
        f"/ui/reviews/{R}/rids/{csv_rid}/accept", follow_redirects=False
    ).status_code == 303
    assert owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()["status"] == "closed"
    assert owner.get(f"/reviews/{R}/rids/{csv_rid}").json()["status"] == "closed"
    assert owner.get(f"/reviews/{R}").json()["status"] == "in_review"

    # --- owner starts closeout (gate: every finding closed) ---
    assert owner.post(
        f"/ui/reviews/{R}/start-closeout", follow_redirects=False
    ).status_code == 303
    assert owner.get(f"/reviews/{R}").json()["status"] == "closeout"

    # the rejected finding never enters the closeout work queue — it lands
    # in the informational "noChange" bucket, never todo/rework/awaiting/done
    doc_html = owner.get(f"/ui/reviews/{R}/document").text
    data = _viewer_data(doc_html)
    assert _rid_by(data, csv_rid)["queue"] == "noChange"
    assert _rid_by(data, timeout_rid)["queue"] == "todo"

    # --- closeout save linked to the accepted RID only ---
    assert owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": CLOSEOUT_CONTENT, "rids": [timeout_rid]},
        follow_redirects=False,
    ).status_code == 303
    # v3.2 point 13: the save closes an implementation session, so it links the
    # change AND implements the finding — one gesture, one transaction.
    assert owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()["status"] == "implemented"
    assert timeout_rid in owner.get(f"/reviews/{R}/traceability").json()["referenced"]
    assert csv_rid not in owner.get(f"/reviews/{R}/traceability").json()["referenced"]

    # the standalone route survives for pre-v3.2 data and is idempotent
    assert owner.post(
        f"/ui/reviews/{R}/rids/{timeout_rid}/implement", follow_redirects=False
    ).status_code == 303
    assert owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()["status"] == "implemented"

    # --- reviewer requests changes (back to closed, reason recorded) ---
    assert reviewer.post(
        f"/ui/reviews/{R}/rids/{timeout_rid}/request-changes",
        data={"reason": "Please spell out the unit explicitly."},
        follow_redirects=False,
    ).status_code == 303
    reworked = owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()
    assert reworked["status"] == "closed"
    assert "Please spell out the unit explicitly." in reworked["reply"]

    # the reworked finding now shows up in the "rework" bucket, not "todo"
    doc_html = owner.get(f"/ui/reviews/{R}/document").text
    data = _viewer_data(doc_html)
    assert _rid_by(data, timeout_rid)["queue"] == "rework"

    # --- owner re-saves the edit and re-marks implemented ---
    assert owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": CLOSEOUT_CONTENT_V2, "rids": [timeout_rid]},
        follow_redirects=False,
    ).status_code == 303
    assert owner.post(
        f"/ui/reviews/{R}/rids/{timeout_rid}/implement", follow_redirects=False
    ).status_code == 303
    assert owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()["status"] == "implemented"

    # --- reviewer verifies ---
    assert reviewer.post(
        f"/ui/reviews/{R}/rids/{timeout_rid}/verify", follow_redirects=False
    ).status_code == 303
    assert owner.get(f"/reviews/{R}/rids/{timeout_rid}").json()["status"] == "verified"

    # --- owner finalizes ---
    assert owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False).status_code == 303
    assert owner.get(f"/reviews/{R}").json()["status"] == "finalized"

    # --- downloads ---
    final_md = owner.get(f"/ui/reviews/{R}/download/final.md")
    assert final_md.status_code == 200
    assert final_md.text == CLOSEOUT_CONTENT_V2

    report_md = owner.get(f"/ui/reviews/{R}/download/report.md")
    assert report_md.status_code == 200

    pdf = owner.get(f"/ui/reviews/{R}/download/review.pdf")
    assert pdf.status_code == (200 if pdfgen.PDF_AVAILABLE else 404)

    # every RID reached a terminal state: the accepted one verified, the
    # rejected one closed (v3: rejected/deferred findings never go past 'closed')
    final_status = {r["rid"]: r["status"] for r in owner.get(f"/reviews/{R}/rids").json()}
    assert final_status[timeout_rid] == "verified"
    assert final_status[csv_rid] == "closed"
