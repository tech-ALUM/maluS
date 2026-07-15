"""v1.7: an AI co-owner may only DRAFT dispositions (ai_drafted + OPEN); a human
owner confirms. The is_ai guard blocks every committing owner transition."""

from __future__ import annotations

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    """Human primary owner + AI co-owner + one reviewer; one OPEN harvested RID."""
    owner = mkuser("owner", "A. Boffi")
    ai = mkuser("aibot", "AI Bot", is_ai=True)
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    # the human owner makes the AI a co-owner (owner role) via the members GUI
    r = owner.post(
        f"/ui/reviews/{R}/members", data={"username": "aibot", "role": "owner"}, follow_redirects=False
    )
    assert r.status_code == 303, r.text
    # a reviewer submits → OPEN RID SIN-SRS-0001
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    return owner, ai, f


def test_ai_owner_can_draft_a_disposition(mkuser, docs):
    _owner, ai, _f = _seed(mkuser, docs)
    r = ai.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"disposition": "accepted", "reply": "looks right to me"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "open"  # NOT committed — still a proposal
    assert body["ai_drafted"] is True
    assert body["disposition"] == "accepted" and body["reply"] == "looks right to me"


def test_ai_owner_cannot_commit_answer(mkuser, docs):
    _owner, ai, _f = _seed(mkuser, docs)
    r = ai.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "accepted"},
    )
    assert r.status_code == 403


def test_ai_owner_cannot_implement_or_finalize(mkuser, docs):
    _owner, ai, _f = _seed(mkuser, docs)
    assert ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"status": "implemented"}).status_code == 403
    assert ai.post(f"/reviews/{R}/finalize", json={}).status_code == 403


def test_human_owner_confirms_ai_draft_and_keeps_provenance(mkuser, docs):
    owner, ai, _f = _seed(mkuser, docs)
    ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"disposition": "accepted", "reply": "ok"})
    # the human owner confirms via the existing dispose form (commits the answer)
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok", "resolution": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    rid = owner.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()
    assert rid["status"] == "answered"  # committed by the human
    assert rid["ai_drafted"] is True  # provenance retained


def test_human_owner_still_governs_normally(mkuser, docs):
    # regression: a human owner can still commit (the guard is is_ai-specific)
    owner, _ai, _f = _seed(mkuser, docs)
    r = owner.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "rejected", "reply": "n/a"},
    )
    assert r.status_code == 200 and r.json()["status"] == "answered"


# --- GUI: the human owner confirms or discards an AI proposal --------------- #


def test_finding_shows_ai_proposal_for_human_owner(mkuser, docs):
    owner, ai, _f = _seed(mkuser, docs)
    ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"disposition": "accepted", "reply": "ok"})
    page = owner.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert "AI proposal" in page  # a banner marks it as AI-drafted
    assert "Confirm disposition" in page  # the dispose button reads "Confirm"
    assert "/discard-draft" in page  # and a Discard control is offered


def test_ai_owner_sees_no_dispose_form(mkuser, docs):
    _owner, ai, _f = _seed(mkuser, docs)
    ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"disposition": "accepted"})
    page = ai.get(f"/ui/reviews/{R}/rids/SIN-SRS-0001").text
    assert "/dispose" not in page  # an AI co-owner can never commit from the GUI


def test_human_owner_discards_ai_draft(mkuser, docs):
    owner, ai, _f = _seed(mkuser, docs)
    ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"disposition": "accepted", "reply": "ok"})
    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/discard-draft", follow_redirects=False
    )
    assert r.status_code == 303
    rid = owner.get(f"/reviews/{R}/rids/SIN-SRS-0001").json()
    assert rid["status"] == "open" and rid["ai_drafted"] is False and rid["disposition"] is None


def test_discard_forbidden_for_reviewer(mkuser, docs):
    _owner, ai, f = _seed(mkuser, docs)
    ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"disposition": "accepted"})
    assert f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/discard-draft").status_code == 403


def test_dashboard_flags_ai_proposals(mkuser, docs):
    owner, ai, _f = _seed(mkuser, docs)
    ai.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"disposition": "accepted"})
    page = owner.get(f"/ui/reviews/{R}").text
    assert "AI proposals" in page  # dashboard tile counting pending proposals


# --- an AI co-owner may only DRAFT; it never mutates review CONTENT --------- #


def test_ai_owner_cannot_mutate_the_document(mkuser, docs):
    _owner, ai, _f = _seed(mkuser, docs)
    # every content commit is reserved to a human owner (same guard as answer/finalize)
    assert ai.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]}).status_code == 403
    assert ai.post(f"/reviews/{R}/document", json={"content": "hacked baseline"}).status_code == 403
    assert ai.post(f"/reviews/{R}/changes", json={"content": "x", "rids": []}).status_code == 403
    assert ai.post(f"/reviews/{R}/apply-suggs", json={"dry_run": False}).status_code == 403


def test_human_owner_still_mutates_the_document(mkuser, docs):
    # regression: the guard is is_ai-specific — a human owner still edits the document
    owner, _ai, _f = _seed(mkuser, docs)
    r = owner.post(f"/reviews/{R}/document", json={"content": docs["baseline"] + "\nextra\n"})
    assert r.status_code == 200
