"""v3.2 step 05 — the attribution reaches the readers, and only them.

The full-diff page and the self-contained diff download label each hunk with
the finding that caused it. The finalized document must not: `final.md` and the
PDF are the deliverable, not review scaffolding.
"""

from __future__ import annotations

R = "SIN-SRS-A1"

BASELINE = """# Sensor Interface Requirements

The acquisition timeout shall be configurable.

All measurements are written to disk in CSV format.

Calibration coefficients live beside the measurement data.
"""

COPY = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable. "
    "{COMM|type=technical|sev=major: bound the timeout to at most 30 s}",
).replace(
    "All measurements are written to disk in CSV format.",
    "All measurements are written to disk in CSV format. "
    "{COMM|type=editorial|sev=minor: name the CSV columns}",
)


def _seed_two_implemented(mkuser):
    """Closeout with two findings, each implemented by its own session — so the
    two edits have two distinct causes to attribute."""
    owner = mkuser("a1owner", "A1 Owner")
    reviewer = mkuser("a1rev", "A1 Reviewer")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "A1 Reviewer", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE})
    reviewer.post(f"/reviews/{R}/copies/A1 Reviewer/submit", json={"content": COPY})

    rids = owner.get(f"/reviews/{R}/rids").json()
    timeout = next(r["rid"] for r in rids if "timeout" in r["comment"])
    csv = next(r["rid"] for r in rids if "CSV" in r["comment"])
    for rid in (timeout, csv):
        owner.post(
            f"/ui/reviews/{R}/rids/{rid}/dispose",
            data={"disposition": "accepted", "reply": "Agreed.", "resolution": ""},
            follow_redirects=False,
        )
        reviewer.post(f"/ui/reviews/{R}/rids/{rid}/accept", follow_redirects=False)
    owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)

    v1 = BASELINE.replace(
        "The acquisition timeout shall be configurable.",
        "The acquisition timeout shall be configurable, bounded to at most 30 s.",
    )
    owner.post(f"/ui/reviews/{R}/closeout", data={"content": v1, "rids": [timeout]},
               follow_redirects=False)
    v2 = v1.replace(
        "All measurements are written to disk in CSV format.",
        "All measurements are written to disk as CSV with a documented column header.",
    )
    owner.post(f"/ui/reviews/{R}/closeout", data={"content": v2, "rids": [csv]},
               follow_redirects=False)
    return owner, reviewer, timeout, csv, v2


def test_the_full_diff_page_names_the_finding_behind_each_change(mkuser):
    owner, _reviewer, timeout, csv, _final = _seed_two_implemented(mkuser)

    page = owner.get(f"/ui/reviews/{R}/diff?view=full").text

    assert 'class="diff-rid"' in page
    # each edit is labelled with its own cause, not with both
    timeout_row = next(r for r in page.split("<div ") if "30 s" in r and "diff-ins" in r)
    assert timeout in timeout_row and csv not in timeout_row
    csv_row = next(r for r in page.split("<div ") if "column header" in r and "diff-ins" in r)
    assert csv in csv_row and timeout not in csv_row


def test_an_untouched_line_carries_no_badge(mkuser):
    owner, _reviewer, _timeout, _csv, _final = _seed_two_implemented(mkuser)

    page = owner.get(f"/ui/reviews/{R}/diff?view=full").text

    calib = next(r for r in page.split("<div ") if "Calibration" in r)
    assert "diff-rid" not in calib


def test_a_reviewer_sees_the_attribution_too(mkuser):
    """Point 13's whole purpose: the reviewer reading the full diff can tell
    which of their comments produced which change."""
    _owner, reviewer, timeout, _csv, _final = _seed_two_implemented(mkuser)

    page = reviewer.get(f"/ui/reviews/{R}/diff?view=full")

    assert page.status_code == 200
    assert timeout in page.text and 'class="diff-rid"' in page.text


def test_the_finalized_document_carries_no_attribution(mkuser):
    """final.md is the deliverable. Review scaffolding must not leak into it."""
    owner, reviewer, timeout, csv, final_text = _seed_two_implemented(mkuser)
    for rid in (timeout, csv):
        reviewer.post(f"/ui/reviews/{R}/rids/{rid}/verify", follow_redirects=False)
    owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False)

    final_md = owner.get(f"/ui/reviews/{R}/download/final.md")

    assert final_md.status_code == 200
    assert final_md.text == final_text
    assert "diff-rid" not in final_md.text
    assert timeout not in final_md.text and csv not in final_md.text


def test_the_downloadable_diff_is_attributed_and_still_self_contained(mkuser):
    owner, reviewer, timeout, csv, _final = _seed_two_implemented(mkuser)
    for rid in (timeout, csv):
        reviewer.post(f"/ui/reviews/{R}/rids/{rid}/verify", follow_redirects=False)
    owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False)

    art = owner.get(f"/ui/reviews/{R}/download/diff.html")

    assert art.status_code == 200
    assert 'class="diff-rid"' in art.text and timeout in art.text
    assert ".diff-rid {" in art.text          # its style travels with it
    assert "/static/" not in art.text          # still no external reference
    assert "<script" not in art.text


def test_the_per_finding_changes_section_is_unchanged(mkuser):
    """The card's own diff is a single version step and reads the same renderer;
    attribution is opt-in and must not have leaked into it."""
    owner, _reviewer, timeout, _csv, _final = _seed_two_implemented(mkuser)

    viewer = owner.get(f"/ui/reviews/{R}/document?focus={timeout}").text
    payload_start = viewer.index('id="viewer-data"')
    payload = viewer[payload_start : viewer.index("</script>", payload_start)]

    assert "diff-rid" not in payload
