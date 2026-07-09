"""Comment-block parser for reviewer copies (docs/spec/comment-syntax.md).

``scan`` locates every ``{COMM …}`` / ``{SUGG …}`` block in a text and parses
it strictly; a recognised opener that is malformed raises :class:`ParseError`
with a precise ``line``/``col``. Text that is not a block opener is ignored,
so the parser can run over a whole reviewer copy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import DEFAULT_SEVERITY, DEFAULT_TYPE, CommentType, Kind, Severity

_WS = " \t\r\n"


class ParseError(ValueError):
    """A malformed comment block, with 1-based ``line``/``col`` position."""

    def __init__(self, message: str, line: int, col: int, pos: int) -> None:
        self.message = message
        self.line = line
        self.col = col
        self.pos = pos
        super().__init__(f"{line}:{col}: {message}")


@dataclass
class ParsedBlock:
    """One parsed comment block and its span in the source text."""

    kind: Kind
    start: int
    end: int
    line: int
    col: int
    comment_type: CommentType | None = None
    severity: Severity | None = None
    text: str | None = None
    old: str | None = None
    new: str | None = None


def _line_col(text: str, pos: int) -> tuple[int, int]:
    prefix = text[:pos]
    line = prefix.count("\n") + 1
    col = pos - prefix.rfind("\n")  # rfind == -1 when on the first line
    return line, col


def _err(text: str, pos: int, message: str) -> ParseError:
    line, col = _line_col(text, pos)
    return ParseError(message, line, col, pos)


def _skip_ws(text: str, j: int) -> int:
    n = len(text)
    while j < n and text[j] in _WS:
        j += 1
    return j


def scan(text: str) -> list[ParsedBlock]:
    """Return every comment block in ``text`` in document order."""
    blocks: list[ParsedBlock] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "{" and i + 5 < n:
            if text.startswith("{COMM", i) and text[i + 5] in "|:":
                block = _parse_comm(text, i)
                blocks.append(block)
                i = block.end
                continue
            if text.startswith("{SUGG", i) and text[i + 5] == ":":
                block = _parse_sugg(text, i)
                blocks.append(block)
                i = block.end
                continue
        i += 1
    return blocks


def _parse_comm(text: str, i: int) -> ParsedBlock:
    n = len(text)
    line, col = _line_col(text, i)
    j = i + 5  # just past "{COMM"

    comment_type: CommentType | None = None
    severity: Severity | None = None
    seen: set[str] = set()

    while j < n and text[j] == "|":
        j += 1
        k = j
        while k < n and text[k] not in "|:":
            k += 1
        if k >= n:
            raise _err(text, j, "unterminated comment header")
        token = text[j:k]
        if "=" not in token or any(c in token for c in _WS):
            raise _err(text, j, f"malformed parameter {token!r}")
        key, _, value = token.partition("=")
        if key == "type":
            if "type" in seen:
                raise _err(text, j, "duplicate 'type' parameter")
            try:
                comment_type = CommentType(value)
            except ValueError:
                raise _err(text, j, f"invalid type {value!r}") from None
            seen.add("type")
        elif key == "sev":
            if "sev" in seen:
                raise _err(text, j, "duplicate 'sev' parameter")
            try:
                severity = Severity(value)
            except ValueError:
                raise _err(text, j, f"invalid sev {value!r}") from None
            seen.add("sev")
        else:
            raise _err(text, j, f"unknown parameter {key!r}")
        j = k

    if j >= n or text[j] != ":":
        raise _err(text, j if j < n else i, "expected ':' in comment header")
    j += 1

    body: list[str] = []
    while j < n:
        c = text[j]
        if c == "\\" and j + 1 < n and text[j + 1] == "}":
            body.append("}")
            j += 2
            continue
        if c == "}":
            content = "".join(body).strip()
            if not content:
                raise _err(text, i, "empty comment text")
            return ParsedBlock(
                kind=Kind.COMM,
                start=i,
                end=j + 1,
                line=line,
                col=col,
                comment_type=comment_type if comment_type is not None else DEFAULT_TYPE,
                severity=severity if severity is not None else DEFAULT_SEVERITY,
                text=content,
            )
        body.append(c)
        j += 1
    raise _err(text, i, "unterminated comment block")


def _read_qstring(text: str, j: int, blk_start: int) -> tuple[str, int]:
    n = len(text)
    j = _skip_ws(text, j)
    if j >= n or text[j] != '"':
        raise _err(text, j if j < n else blk_start, "expected opening '\"'")
    j += 1
    chars: list[str] = []
    while j < n:
        c = text[j]
        if c == "\\" and j + 1 < n and text[j + 1] in '"}':
            chars.append(text[j + 1])
            j += 2
            continue
        if c == '"':
            return "".join(chars), j + 1
        chars.append(c)
        j += 1
    raise _err(text, blk_start, "unterminated suggestion string")


def _parse_sugg(text: str, i: int) -> ParsedBlock:
    n = len(text)
    line, col = _line_col(text, i)
    j = i + 6  # just past "{SUGG:"

    old, j = _read_qstring(text, j, i)
    j = _skip_ws(text, j)
    if not text.startswith("->", j):
        raise _err(text, j, "expected '->' in suggestion")
    j += 2
    new, j = _read_qstring(text, j, i)
    j = _skip_ws(text, j)
    if j >= n or text[j] != "}":
        raise _err(text, j if j < n else i, "expected '}' to close suggestion")
    if old == "":
        raise _err(text, i, "suggestion 'old' text must be non-empty")
    return ParsedBlock(
        kind=Kind.SUGG, start=i, end=j + 1, line=line, col=col, old=old, new=new
    )
