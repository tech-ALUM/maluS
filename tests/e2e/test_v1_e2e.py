"""v1 end-to-end (Step 9): a full multi-user review with a human AND an AI
reviewer, driven over the API + GUI + MCP, finalized — with no git anywhere.
Plus a v0 legacy import into the DB."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from malus.legacy import import_review_dir
from malus.mcp import tools

R = "SIN-SRS-R1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_full_multi_user_review_to_finalize(app, mkuser, basic_client, docs):
    # --- admin provisions accounts; owner sets up the review ---
    owner = mkuser("owner", "A. Boffi")
    human = mkuser("fmiccoli", "F. Miccoli")
    mkuser("aibot", "AI Bot", is_ai=True)
    mod = mkuser("mod", "M. Mod")
    ai = basic_client("aibot", "pw")  # the AI agent authenticates with Basic (MCP path)

    assert owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"}).status_code == 201
    for name, role in [("F. Miccoli", "reviewer"), ("AI Bot", "reviewer"), ("M. Mod", "moderator")]:
        assert owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": role}).status_code == 200
    assert owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]}).status_code == 200

    # --- reviewers comment & submit (human via API submit; AI via MCP tools) ---
    assert human.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]}).status_code == 200
    ai_result = tools.submit_reviewer_comments(ai, R, "AI Bot", docs["ai_copy"])
    assert ai_result["violations"] == []

    rids = owner.get(f"/reviews/{R}/rids").json()
    by_reviewer = {r["reviewer"]: r["rid"] for r in rids}
    assert set(by_reviewer) == {"F. Miccoli", "AI Bot"}  # both reviewers' findings harvested
    human_rid, ai_rid = by_reviewer["F. Miccoli"], by_reviewer["AI Bot"]

    # --- moderator triages (no-op cluster here) ---
    assert mod.post(f"/reviews/{R}/triage", json={"auto": True}).status_code == 200

    # --- owner disposes: accept the human finding (GUI), reject the AI finding (API) ---
    assert owner.post(
        f"/ui/reviews/{R}/rids/{human_rid}/dispose",
        data={"disposition": "accepted", "reply": "Agreed.", "resolution": ""},
        follow_redirects=False,
    ).status_code == 303
    assert owner.patch(
        f"/reviews/{R}/rids/{ai_rid}", json={"status": "answered", "disposition": "rejected", "reply": "no"}
    ).status_code == 200

    # --- owner implements the accepted finding via the editor (GUI) -> version + RID link ---
    assert owner.post(
        f"/ui/reviews/{R}/implement",
        data={"content": docs["baseline"] + "\nThe timeout is bounded to 30s.\n", "rids": [human_rid]},
        follow_redirects=False,
    ).status_code == 303
    assert owner.get(f"/reviews/{R}/rids/{human_rid}").json()["status"] == "implemented"
    assert human_rid in owner.get(f"/reviews/{R}/traceability").json()["referenced"]

    # --- verification: the human verifies their own (GUI); the moderator verifies the
    #     AI's finding on the AI's behalf (an AI can never verify) ---
    assert human.post(f"/ui/reviews/{R}/rids/{human_rid}/verify", follow_redirects=False).status_code == 303
    assert ai.post(f"/reviews/{R}/rids/{ai_rid}/verify").status_code == 403  # AI cannot close
    assert mod.post(f"/reviews/{R}/rids/{ai_rid}/verify").status_code == 200  # moderator on behalf

    # --- report + finalize ---
    report = owner.get(f"/reviews/{R}/report").json()
    assert report["errors"] == [] and "Review Minutes" in report["report"]
    fin = owner.post(f"/reviews/{R}/finalize", json={})
    assert fin.status_code == 200 and fin.json()["finalized"] is True and fin.json()["status"] == "finalized"

    # every RID is closed and the audit log recorded distinct actors
    assert all(r["status"] in ("verified", "withdrawn") for r in owner.get(f"/reviews/{R}/rids").json())
    from malus.db.models import AuditLog

    with Session(app.state.engine) as session:
        actions = {a.action for a in session.exec(select(AuditLog)).all()}
        assert {"create_review", "freeze", "harvest", "answer", "implement", "verify", "finalize"} <= actions


def test_v0_review_directory_imports_and_is_usable(app, admin):
    """A legacy v0 review directory loads into the DB and is served over the API."""
    with Session(app.state.engine) as session:
        review = import_review_dir(session, FIXTURES / "sample-review")
        session.commit()
        rid_str = review.review_id_str
    got = admin.get(f"/reviews/{rid_str}")
    assert got.status_code == 200 and got.json()["review_id"] == rid_str
