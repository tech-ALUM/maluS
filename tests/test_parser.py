"""Tests for the comment-block parser (docs/spec/comment-syntax.md)."""

import pytest

from malus.constants import CommentType, Kind, Severity
from malus.parser import ParseError, scan


def _one(text: str):
    blocks = scan(text)
    assert len(blocks) == 1
    return blocks[0]


# --- {COMM} ---


def test_comm_applies_defaults() -> None:
    b = _one("{COMM: this reads awkwardly}")
    assert b.kind is Kind.COMM
    assert b.comment_type is CommentType.EDITORIAL
    assert b.severity is Severity.MINOR
    assert b.text == "this reads awkwardly"


def test_comm_params_are_order_free() -> None:
    a = _one("{COMM|type=technical|sev=major: x}")
    b = _one("{COMM|sev=major|type=technical: x}")
    assert (a.comment_type, a.severity) == (CommentType.TECHNICAL, Severity.MAJOR)
    assert (b.comment_type, b.severity) == (CommentType.TECHNICAL, Severity.MAJOR)


def test_comm_partial_params_keep_other_default() -> None:
    b = _one("{COMM|type=typo: recieve}")
    assert b.comment_type is CommentType.TYPO
    assert b.severity is Severity.MINOR


def test_comm_process_type_is_accepted() -> None:
    b = _one("{COMM|type=process|sev=critical: missing traceability matrix}")
    assert b.comment_type is CommentType.PROCESS
    assert b.severity is Severity.CRITICAL


def test_comm_multiline_text_is_trimmed() -> None:
    b = _one("{COMM:  line one\nline two  }")
    assert b.text == "line one\nline two"


def test_comm_escaped_closing_brace() -> None:
    b = _one("{COMM: set X to \\} then stop}")
    assert b.text == "set X to } then stop"


# --- {SUGG} ---


def test_sugg_basic() -> None:
    b = _one('{SUGG: "colour" -> "color"}')
    assert b.kind is Kind.SUGG
    assert b.old == "colour"
    assert b.new == "color"
    assert b.comment_type is None and b.severity is None


def test_sugg_deletion_allows_empty_new() -> None:
    b = _one('{SUGG: "redundant clause" -> ""}')
    assert b.old == "redundant clause"
    assert b.new == ""


def test_sugg_escaped_quote_in_operand() -> None:
    b = _one('{SUGG: "a \\"quoted\\" word" -> "a word"}')
    assert b.old == 'a "quoted" word'
    assert b.new == "a word"


# --- scan over prose ---


def test_scan_finds_blocks_and_ignores_non_openers() -> None:
    text = 'intro {COMM: a} middle {SUGG: "x" -> "y"} tail {COMMENT} end'
    blocks = scan(text)
    assert [b.kind for b in blocks] == [Kind.COMM, Kind.SUGG]


def test_scan_records_positions() -> None:
    text = "line1\nline2 {COMM: here}\n"
    b = _one(text)
    assert b.line == 2
    assert text[b.start : b.end] == "{COMM: here}"


# --- malformed → ParseError with position ---


def test_unknown_type_value_raises() -> None:
    with pytest.raises(ParseError):
        scan("{COMM|type=bogus: x}")


def test_unknown_parameter_raises() -> None:
    with pytest.raises(ParseError):
        scan("{COMM|foo=bar: x}")


def test_duplicate_parameter_raises() -> None:
    with pytest.raises(ParseError):
        scan("{COMM|type=typo|type=technical: x}")


def test_unterminated_block_raises() -> None:
    with pytest.raises(ParseError):
        scan("{COMM: no closing brace")


def test_empty_comm_text_raises() -> None:
    with pytest.raises(ParseError):
        scan("{COMM:   }")


def test_sugg_empty_old_raises() -> None:
    with pytest.raises(ParseError):
        scan('{SUGG: "" -> "x"}')


def test_parse_error_reports_line() -> None:
    text = "ok line\nok line\n{COMM|type=nope: x}"
    with pytest.raises(ParseError) as exc:
        scan(text)
    assert exc.value.line == 3
