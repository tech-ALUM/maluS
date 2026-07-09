"""Guards for the single-file GUI: self-contained and constants in sync."""

import re
from pathlib import Path

from malus.gui_constants import render_block

RTD_HTML = Path(__file__).parent.parent / "gui" / "rtd.html"


def test_gui_is_self_contained() -> None:
    text = RTD_HTML.read_text(encoding="utf-8")
    # zero network / no external resources (works from file://)
    assert "http://" not in text
    assert "https://" not in text
    assert "//cdn" not in text
    assert not re.search(r"<script[^>]+\bsrc=", text)
    assert not re.search(r"<link[^>]+\bhref=", text)
    assert "@import" not in text


def test_generated_constants_in_sync_with_python() -> None:
    text = RTD_HTML.read_text(encoding="utf-8")
    assert render_block() in text  # regenerate via: python -m malus.gui_constants gui/rtd.html
