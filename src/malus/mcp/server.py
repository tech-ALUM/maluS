"""maluS MCP server — review tools for an interactive AI reviewer.

Run with ``malus mcp`` (stdio transport). It authenticates to a running maluS
over HTTP using the AI reviewer's Basic credentials (``MALUS_URL``,
``MALUS_AI_USER``, ``MALUS_AI_PASSWORD``). maluS makes no model calls — Claude
Code runs interactively under the user's own subscription. No verify/close tool
is exposed.
"""

from __future__ import annotations

import os

from malus.mcp import tools


def _http_client():
    import httpx

    base = os.environ.get("MALUS_URL", "http://127.0.0.1:8000")
    user = os.environ.get("MALUS_AI_USER")
    password = os.environ.get("MALUS_AI_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "set MALUS_AI_USER and MALUS_AI_PASSWORD to the AI reviewer's maluS credentials"
        )
    return httpx.Client(base_url=base, auth=(user, password), timeout=30.0)


def build_server(client=None):
    """Build the FastMCP server. ``client`` (an http client) is injectable for
    tests; production uses the env-configured Basic-auth httpx client."""
    from mcp.server.fastmcp import FastMCP

    client = client if client is not None else _http_client()
    server = FastMCP(
        "malus",
        instructions=(
            "maluS formal-review tools. Typical reviewer flow: list_reviews -> "
            "get_baseline -> insert {COMM} blocks into the FULL text -> "
            "submit_reviewer_comments (FINAL: request_reopen to edit again). "
            "Owner-side setup: create_review -> upload_document. You never "
            "verify/close findings.\n\n" + tools.COMMENT_SYNTAX
        ),
    )

    @server.tool()
    def list_reviews() -> list:
        """List the reviews the AI reviewer can see."""
        return tools.list_reviews(client)

    @server.tool()
    def get_baseline(review_id: str) -> str:
        """Return the frozen baseline text of a review's document."""
        return tools.get_baseline(client, review_id)

    @server.tool()
    def list_rids(review_id: str) -> list:
        """List a review's RIDs (findings)."""
        return tools.list_rids(client, review_id)

    @server.tool()
    def get_comment_syntax() -> str:
        """The exact comment-block grammar ({COMM|type=…|sev=…: text}), the
        freeze rule and a worked example — read this BEFORE writing comments."""
        return tools.get_comment_syntax()

    @server.tool()
    def submit_reviewer_comments(review_id: str, reviewer: str, content: str) -> dict:
        """Submit the reviewer's copy: the COMPLETE baseline text with your
        {COMM|type=<typo|editorial|technical|process>|sev=<minor|major|critical>: text}
        blocks inserted inline right after the passages they concern (params
        optional; call get_comment_syntax for the full grammar). INSERTION
        ONLY — changing baseline text is rejected (422). Submitting is FINAL:
        editing again requires request_reopen + the owner's approval."""
        return tools.submit_reviewer_comments(client, review_id, reviewer, content)

    @server.tool()
    def request_reopen(review_id: str, reviewer: str) -> dict:
        """Ask to edit your already-submitted copy again (the owner must
        approve; you'll be able to resubmit once unlocked)."""
        return tools.request_reopen(client, review_id, reviewer)

    @server.tool()
    def create_review(
        review_id: str, title: str = "", reviewers: list | None = None, rid_prefix: str = ""
    ) -> dict:
        """Create a review (the authenticated account becomes its owner) and
        register reviewers. Follow with upload_document for the baseline."""
        return tools.create_review(client, review_id, title, reviewers, rid_prefix)

    @server.tool()
    def upload_document(review_id: str, content: str) -> dict:
        """Freeze the review's baseline Markdown (one-shot, immutable). The
        server refuses this from an AI principal (owner commit) — 403."""
        return tools.upload_document(client, review_id, content)

    @server.tool()
    def propose_triage(review_id: str) -> dict:
        """Propose duplicate clusters (read-only; does not apply them)."""
        return tools.propose_triage(client, review_id)

    @server.tool()
    def submit_disposition(
        review_id: str, rid: str, disposition: str, reply: str = "", resolution: str = ""
    ) -> dict:
        """Draft an owner disposition for a RID (co-owner path). DRAFT ONLY — it
        does not commit: the RID stays open and marked ai_drafted, and a human
        owner must confirm it. disposition is accepted | rejected | deferred."""
        return tools.submit_disposition(client, review_id, rid, disposition, reply, resolution)

    return server


def run() -> None:  # pragma: no cover  (stdio transport; used interactively)
    build_server().run()
