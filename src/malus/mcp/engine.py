"""Optional, off-by-default **paid** server-side AI engine.

The default maluS AI path is free: an interactive Claude Code session connected
to the MCP server (``malus.mcp.server``) makes zero server-side model calls, so
it incurs no model billing. This module is the opt-in *paid* path for unattended
runs, enabled only when ``MALUS_AI_ENGINE=anthropic``; it is billed at Anthropic
API rates (programmatic Claude Code usage was separated from the interactive
subscription pool on 2026-06-15).
"""

from __future__ import annotations

import os


def engine_enabled() -> bool:
    return os.environ.get("MALUS_AI_ENGINE", "").strip().lower() == "anthropic"


def run_headless(*_args, **_kwargs):
    if not engine_enabled():
        raise RuntimeError(
            "the server-side AI engine is disabled. Set MALUS_AI_ENGINE=anthropic to enable "
            "it (PAID — billed at Anthropic API rates). The default free path is the "
            "interactive MCP server (malus mcp)."
        )
    raise NotImplementedError(
        "the paid server-side engine is a documented opt-in and is not implemented in v1; "
        "use the free interactive MCP path (see docs/usage/ai-reviewer.md)"
    )
