"""maluS MCP server: review tools for an interactive (free) AI reviewer."""

from malus.mcp import tools
from malus.mcp.engine import engine_enabled

__all__ = ["tools", "engine_enabled", "build_server"]


def build_server(client=None):
    from malus.mcp.server import build_server as _build

    return _build(client)
