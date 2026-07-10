"""Server-rendered GUI (Jinja + progressive HTMX) over the service layer."""

from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

from malus.web.router import web  # noqa: E402  (after the paths so the router can import them)

__all__ = ["STATIC_DIR", "TEMPLATES_DIR", "web"]
