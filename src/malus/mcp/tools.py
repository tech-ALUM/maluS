"""MCP tool implementations — drive the maluS HTTP API as a reviewer identity.

These are the review tools an interactive AI agent (Claude Code) invokes. Each
calls the Step-3 API with the caller's credentials; maluS makes **no** server-side
model calls, so the free/interactive path incurs no model billing.

There is deliberately **no** verify / close tool, and the disposition tool only
**drafts** (never commits): AI principals may never advance a finding — the
``is_ai`` guardrail refuses answer/implement/finalize server-side, and a human
owner must confirm any AI-drafted disposition (v1.7). AI-submitted content enters
only through the same validated endpoints a human uses — invalid comment blocks
are rejected by the parser.

``client`` is any object with ``get``/``post`` returning an httpx-style response
(an ``httpx.Client`` in production; a FastAPI ``TestClient`` in tests).
"""

from __future__ import annotations

TOOL_NAMES = [
    "list_reviews",
    "get_baseline",
    "list_rids",
    "get_comment_syntax",
    "submit_reviewer_comments",
    "request_reopen",
    "create_review",
    "upload_document",
    "propose_triage",
    "submit_disposition",
]

# The normative cheat-sheet (docs/spec/comment-syntax.md, distilled) — served by
# get_comment_syntax and embedded in the server instructions so an AI reviewer
# never needs a trial comment to learn the grammar.
COMMENT_SYNTAX = """\
maluS COMMENT SYNTAX — insert blocks INLINE into your copy of the document,
each immediately AFTER the text it refers to:

    {COMM|type=<t>|sev=<s>: your comment text}

- type: typo | editorial | technical | process   (optional, default editorial)
- sev:  minor | major | critical                 (optional, default minor)
- Parameters are optional and order-free; NO whitespace between "{COMM" and ":".
- The block ends at the first unescaped "}"; write a literal "}" as "\\}".
  Blocks may span multiple lines.
- FREEZE RULE (hard): never change, delete, move or reformat the baseline text.
  The ONLY legal edit is inserting comment blocks; the server diffs your copy
  against the frozen baseline and rejects anything else (422).
- Do NOT use the legacy {SUGG: "old" -> "new"} form — v3 reviews use comments only.

Example. Baseline sentence:
    The timeout shall be configurable.
Your copy:
    The timeout shall be configurable. {COMM|type=technical|sev=major: bound the timeout to at most 30 s}

Workflow: get_baseline -> insert your {COMM} blocks into the FULL text ->
submit_reviewer_comments with the complete annotated copy. Submitting is FINAL:
to edit again call request_reopen and wait for the owner's approval.
"""


def get_comment_syntax() -> str:
    """The comment-block grammar and freeze rule (no server call needed)."""
    return COMMENT_SYNTAX


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


def request_reopen(client, review_id: str, reviewer: str) -> dict:
    """Ask to edit an already-submitted copy again (v3: Submit is final). The
    owner — a human — approves; poll list_reviews/get_baseline later and
    resubmit once unlocked."""
    r = client.post(f"/reviews/{review_id}/copies/{reviewer}/request-reopen")
    r.raise_for_status()
    return {"status": "reopen requested", "reviewer": reviewer}


def create_review(
    client,
    review_id: str,
    title: str = "",
    reviewers: list | None = None,
    rid_prefix: str = "",
) -> dict:
    """Create a review (the caller becomes its owner) and register reviewers.
    Upload the document with upload_document next."""
    payload: dict = {"review_id": review_id}
    if title:
        payload["title"] = title
    if rid_prefix:
        payload["rid_prefix"] = rid_prefix
    r = client.post("/reviews", json=payload)
    r.raise_for_status()
    out = r.json()
    for name in reviewers or []:
        rr = client.post(f"/reviews/{review_id}/reviewers", json={"name": name, "role": "reviewer"})
        rr.raise_for_status()
    return out


def upload_document(client, review_id: str, content: str) -> dict:
    """Freeze the review's baseline document (Markdown). One-shot: the baseline
    is immutable afterwards. NOTE: freezing commits an owner decision — the
    server refuses it from an AI principal (403); use human credentials."""
    r = client.post(f"/reviews/{review_id}/freeze", json={"content": content})
    r.raise_for_status()
    return r.json()


def propose_triage(client, review_id: str) -> dict:
    r = client.post(f"/reviews/{review_id}/triage", json={"auto": False})
    r.raise_for_status()
    return r.json()


def submit_disposition(
    client, review_id: str, rid: str, disposition: str, reply: str = "", resolution: str = ""
) -> dict:
    """Draft an owner disposition for a RID (AI co-owner path, v1.7). DRAFT ONLY:
    it PATCHes the disposition fields WITHOUT a status transition, so the RID stays
    OPEN and is marked ``ai_drafted`` — a human owner must confirm it. The server
    refuses any committing transition from an AI principal (403)."""
    payload: dict = {"disposition": disposition}
    if reply:
        payload["reply"] = reply
    if resolution:
        payload["resolution"] = resolution
    r = client.patch(f"/reviews/{review_id}/rids/{rid}", json=payload)
    r.raise_for_status()
    return r.json()
