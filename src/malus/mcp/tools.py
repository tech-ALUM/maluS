"""MCP tool implementations — drive the maluS HTTP API as a reviewer identity.

These are the review tools an interactive AI agent (Claude Code) invokes. Each
calls the Step-3 API with the caller's credentials; maluS makes **no** server-side
model calls, so the free/interactive path incurs no model billing.

There is deliberately **no** verify / close / disposition tool: AI principals may
never advance a finding (also enforced server-side by the ``is_ai`` guardrail).
AI-submitted content enters only through the same validated endpoints a human
uses — invalid comment blocks are rejected by the parser.

``client`` is any object with ``get``/``post`` returning an httpx-style response
(an ``httpx.Client`` in production; a FastAPI ``TestClient`` in tests).
"""

from __future__ import annotations

TOOL_NAMES = [
    "list_reviews",
    "get_baseline",
    "list_rids",
    "submit_reviewer_comments",
    "propose_triage",
]


def list_reviews(client) -> list:
    r = client.get("/reviews")
    r.raise_for_status()
    return r.json()


def get_baseline(client, review_id: str) -> str:
    r = client.get(f"/reviews/{review_id}/baseline")
    r.raise_for_status()
    return r.json()["content"]


def list_rids(client, review_id: str) -> list:
    r = client.get(f"/reviews/{review_id}/rids")
    r.raise_for_status()
    return r.json()


def submit_reviewer_comments(client, review_id: str, reviewer: str, content: str) -> dict:
    """Submit the AI reviewer's copy (comment blocks only). The server validates
    with the parser, saves the copy, and re-harvests; returns the RIDs +
    violations."""
    r = client.post(f"/reviews/{review_id}/copies/{reviewer}/submit", json={"content": content})
    r.raise_for_status()
    return r.json()


def propose_triage(client, review_id: str) -> dict:
    r = client.post(f"/reviews/{review_id}/triage", json={"auto": False})
    r.raise_for_status()
    return r.json()
