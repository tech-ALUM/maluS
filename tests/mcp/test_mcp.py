"""AI reviewer via MCP (v1 Step 7): a scripted client drives an AI review
end-to-end through the tools against a local API stub; guardrails proven."""

from __future__ import annotations

import asyncio

import pytest

from malus.mcp import build_server, tools

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    mkuser("mod", "M. Mod")
    mkuser("aibot", "AI Bot", is_ai=True)  # the AI reviewer account
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "AI Bot", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner


def test_basic_auth_path_authenticates_the_agent(mkuser, basic_client):
    mkuser("aibot", "AI Bot", is_ai=True)
    ai = basic_client("aibot", "pw")
    me = ai.get("/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "aibot"


def test_ai_review_end_to_end_via_tools(mkuser, basic_client, docs):
    _seed(mkuser, docs)
    ai = basic_client("aibot", "pw")

    assert any(r["review_id"] == R for r in tools.list_reviews(ai))
    assert "Timeouts" in tools.get_baseline(ai, R)

    result = tools.submit_reviewer_comments(ai, R, "AI Bot", docs["ai_copy"])
    assert result["violations"] == []

    rids = tools.list_rids(ai, R)
    assert rids and rids[0]["kind"] == "COMM"
    assert rids[0]["reviewer"] == "AI Bot"  # attributed to the agent identity

    assert "proposals" in tools.propose_triage(ai, R)  # read-only, allowed for the AI


def test_ai_principal_cannot_verify_or_close(mkuser, basic_client, docs):
    _seed(mkuser, docs)
    ai = basic_client("aibot", "pw")
    tools.submit_reviewer_comments(ai, R, "AI Bot", docs["ai_copy"])

    # no verify/close tool is exposed at all ...
    assert not any("verify" in n or "close" in n for n in tools.TOOL_NAMES)
    # ... and the server refuses an AI verify regardless (is_ai guardrail) -> 403
    assert ai.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 403


def test_ai_tampering_rejected_by_parser(mkuser, basic_client, docs):
    _seed(mkuser, docs)
    ai = basic_client("aibot", "pw")
    tampered = docs["baseline"].replace("configurable", "tunable")  # edits baseline text
    r = ai.post(f"/reviews/{R}/copies/AI Bot/submit", json={"content": tampered})
    assert r.status_code == 422  # rejected by the parser, no side channel


def test_mcp_server_builds_with_expected_tools(mkuser, basic_client, docs):
    pytest.importorskip("mcp")
    _seed(mkuser, docs)
    server = build_server(client=basic_client("aibot", "pw"))
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == set(tools.TOOL_NAMES)
    assert not any("verify" in n or "close" in n for n in names)
