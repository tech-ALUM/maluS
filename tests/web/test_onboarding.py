"""Reviewer onboarding & hand-off (v1.2 Step 2): a shareable review link, a
prominent reviewer landing CTA, and a "to comment" cue in the review list."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    """A frozen review owned by 'owner' with 'fmiccoli' seated as a reviewer."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/ui/reviews/{R}/members", data={"username": "fmiccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner, f


def test_reviewer_sees_landing_cta_but_owner_does_not(mkuser, docs):
    owner, f = _seed(mkuser, docs)
    # v3.2 point 5: the coral banner and its sentence are gone; the reviewer's
    # way into the document is a single button, and only the reviewer sees it.
    reviewer_page = f.get(f"/ui/reviews/{R}").text
    assert "go to document editor" in reviewer_page.lower()
    assert "cta-banner" not in reviewer_page
    assert "you're a <b>reviewer</b> on this document" not in reviewer_page.lower()
    assert "go to document editor" not in owner.get(f"/ui/reviews/{R}").text.lower()


def test_owner_sees_a_copy_link_control(mkuser, docs):
    owner, f = _seed(mkuser, docs)
    assert 'id="copy-link"' in owner.get(f"/ui/reviews/{R}").text  # a shareable-link control


def test_review_list_flags_awaiting_my_comment_and_clears_after_submit(mkuser, docs):
    owner, f = _seed(mkuser, docs)
    assert "to comment" in f.get("/ui/reviews").text.lower()  # reviewer hasn't commented yet
    assert "to comment" not in owner.get("/ui/reviews").text.lower()  # owner is not a reviewer

    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"]})  # submit the copy
    assert "to comment" not in f.get("/ui/reviews").text.lower()  # cue clears once submitted
