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
    server = FastMCP("malus")

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
    def submit_reviewer_comments(review_id: str, reviewer: str, content: str) -> dict:
        """Submit the AI reviewer's copy — comment blocks only. Validated by the
        parser and harvested server-side; tampering with baseline text is rejected."""
        return tools.submit_reviewer_comments(client, review_id, reviewer, content)

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
