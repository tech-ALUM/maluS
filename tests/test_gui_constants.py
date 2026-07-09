"""Tests for the generated GUI transition-constants block."""

import json

from malus.gui_constants import BEGIN, END, render_block


def _data(block: str) -> dict:
    body = block.split("const MALUS = ", 1)[1].rsplit(";", 1)[0]
    return json.loads(body)


def test_block_has_markers() -> None:
    block = render_block()
    assert block.startswith(BEGIN)
    assert block.rstrip().endswith(END)


def test_transitions_match_constants() -> None:
    transitions = _data(render_block())["TRANSITIONS"]
    assert transitions["open"] == ["answered", "withdrawn"]
    assert transitions["answered"] == ["implemented", "verified"]
    assert transitions["implemented"] == ["verified"]
    assert transitions["verified"] == []
    assert transitions["withdrawn"] == []


def test_enums_present() -> None:
    data = _data(render_block())
    assert data["STATUSES"] == ["open", "answered", "implemented", "verified", "withdrawn"]
    assert data["TYPES"] == ["typo", "editorial", "technical", "process"]
    assert data["SEVERITIES"] == ["minor", "major", "critical"]
    assert data["DISPOSITIONS"] == ["accepted", "rejected", "deferred"]
    assert data["KINDS"] == ["COMM", "SUGG"]
    assert data["ROLES"] == ["owner", "reviewer", "moderator"]
    assert data["TERMINAL"] == ["verified", "withdrawn"]


def test_render_is_deterministic() -> None:
    assert render_block() == render_block()
