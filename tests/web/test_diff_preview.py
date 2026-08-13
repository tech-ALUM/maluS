"""v3.2 step 05 — the editor's live diff endpoint.

It shows baseline → the text as it stands right now, including what is being
typed. That is a *write* surface's view of the document, so it carries the
editor's own authorization: nothing here may be readable by a principal who
could not already read it, and it must not become an open diff service.
"""

from __future__ import annotations

R = "SIN-SRS-P1"

BASELINE = """# Sensor Interface Requirements

The acquisition timeout shall be configurable.

All measurements are written to disk in CSV format.
"""

COPY = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable. "
    "{COMM|type=technical|sev=major: bound the timeout to at most 30 s}",
)

TYPING = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable, bounded to at most 30 s.",
)


def _seed_closeout(mkuser):
    owner = mkuser("p1owner", "P1 Owner")
    reviewer = mkuser("p1rev", "P1 Reviewer")
    outsider = mkuser("p1out", "P1 Outsider")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "P1 Reviewer", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE})
    reviewer.post(f"/reviews/{R}/copies/P1 Reviewer/submit", json={"content": COPY})
    rid = owner.get(f"/reviews/{R}/rids").json()[0]["rid"]
    owner.post(
        f"/ui/reviews/{R}/rids/{rid}/dispose",
        data={"disposition": "accepted", "reply": "Agreed.", "resolution": ""},
        follow_redirects=False,
    )
    reviewer.post(f"/ui/reviews/{R}/rids/{rid}/accept", follow_redirects=False)
    owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False)
    return owner, reviewer, outsider, rid


def test_the_owner_sees_the_text_being_typed_diffed_against_the_baseline(mkuser):
    owner, _rev, _out, _rid = _seed_closeout(mkuser)

    r = owner.post(f"/ui/reviews/{R}/diff-preview", data={"content": TYPING})

    assert r.status_code == 200
    assert "diff-ins" in r.text and "diff-del" in r.text
    assert "bounded to at most 30 s" in r.text
    # unchanged lines are still shown: this is the whole document, not a hunk
    assert "CSV format" in r.text


def test_unchanged_text_says_so_instead_of_rendering_an_empty_diff(mkuser):
    owner, _rev, _out, _rid = _seed_closeout(mkuser)

    r = owner.post(f"/ui/reviews/{R}/diff-preview", data={"content": BASELINE})

    assert r.status_code == 200
    assert "Nothing has changed yet" in r.text


def test_a_reviewer_cannot_use_the_editor_preview(mkuser):
    """The reviewer has the full-diff page; this endpoint belongs to the writer."""
    _owner, reviewer, _out, _rid = _seed_closeout(mkuser)

    r = reviewer.post(f"/ui/reviews/{R}/diff-preview", data={"content": TYPING})

    assert r.status_code == 403


def test_a_non_member_is_refused(mkuser):
    _owner, _rev, outsider, _rid = _seed_closeout(mkuser)

    r = outsider.post(f"/ui/reviews/{R}/diff-preview", data={"content": TYPING})

    assert r.status_code == 403


def test_an_anonymous_caller_is_sent_to_the_login(client):
    r = client.post(f"/ui/reviews/{R}/diff-preview", data={"content": "x"},
                    follow_redirects=False)

    assert r.status_code in (303, 404)   # 404 first if the review is unknown to this app


def test_outside_closeout_the_preview_is_409(mkuser):
    """The editor only exists in closeout, so neither does its diff."""
    owner = mkuser("p2owner", "P2 Owner")
    owner.post("/reviews", json={"review_id": "SIN-SRS-P2", "rid_prefix": "SIN-SRS"})
    owner.post("/reviews/SIN-SRS-P2/freeze", json={"content": BASELINE})

    r = owner.post("/ui/reviews/SIN-SRS-P2/diff-preview", data={"content": TYPING})

    assert r.status_code == 409


def test_an_ai_admin_is_refused(mkuser):
    """is_ai is absolute: an AI principal never writes the document."""
    owner, _rev, _out, _rid = _seed_closeout(mkuser)
    ai_admin = mkuser("p1ai", "P1 AI", is_admin=True, is_ai=True)

    r = ai_admin.post(f"/ui/reviews/{R}/diff-preview", data={"content": TYPING})

    assert r.status_code == 403


def test_the_preview_carries_the_attribution_of_what_is_already_implemented(mkuser):
    owner, _rev, _out, rid = _seed_closeout(mkuser)
    owner.post(f"/ui/reviews/{R}/closeout", data={"content": TYPING, "rids": [rid]},
               follow_redirects=False)

    # now the owner types something further, still unsaved
    typing_more = TYPING.replace("CSV format.", "CSV format, with a documented header.")
    r = owner.post(f"/ui/reviews/{R}/diff-preview", data={"content": typing_more})

    assert r.status_code == 200
    assert rid in r.text                       # the saved change keeps its label
    header_row = next(x for x in r.text.split("<div ") if "documented header" in x)
    assert "diff-rid" not in header_row        # the unsaved one has no cause yet
