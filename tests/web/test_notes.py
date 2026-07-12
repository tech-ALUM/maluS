"""Per-reviewer private notes on comments (v1.4): stored server-side, scoped to
the current reviewer, never harvested or shared. Keyed by a stable anchor_key."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _review_with_reviewers(mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("frev", "F. Rev")
    g = mkuser("grev", "G. Rev")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "frev", "role": "reviewer"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "grev", "role": "reviewer"})
    return owner, f, g


def test_reviewer_saves_and_reads_a_private_note(mkuser):
    _owner, f, _g = _review_with_reviewers(mkuser)
    assert f.put(
        f"/ui/reviews/{R}/my-notes", data={"anchor_key": "42", "body": "check timing later"}
    ).status_code == 204
    assert f.get(f"/ui/reviews/{R}/my-notes").json() == {"42": "check timing later"}


def test_private_notes_are_per_reviewer(mkuser):
    _owner, f, g = _review_with_reviewers(mkuser)
    f.put(f"/ui/reviews/{R}/my-notes", data={"anchor_key": "42", "body": "mine"})
    assert g.get(f"/ui/reviews/{R}/my-notes").json() == {}  # g never sees f's note
    g.put(f"/ui/reviews/{R}/my-notes", data={"anchor_key": "42", "body": "gs own"})
    assert f.get(f"/ui/reviews/{R}/my-notes").json() == {"42": "mine"}  # unchanged for f


def test_empty_body_clears_a_note(mkuser):
    _owner, f, _g = _review_with_reviewers(mkuser)
    f.put(f"/ui/reviews/{R}/my-notes", data={"anchor_key": "7", "body": "temp"})
    f.put(f"/ui/reviews/{R}/my-notes", data={"anchor_key": "7", "body": ""})
    assert f.get(f"/ui/reviews/{R}/my-notes").json() == {}


def test_my_notes_requires_reviewer_role(mkuser):
    owner, _f, _g = _review_with_reviewers(mkuser)
    assert owner.get(f"/ui/reviews/{R}/my-notes").status_code == 403  # owner is not a reviewer
