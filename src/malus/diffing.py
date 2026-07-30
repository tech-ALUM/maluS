"""Server-side diff rendering for the v3 closeout verification (stdlib only).

`html_diff` renders old→new as blocks of context lines plus changed lines with
word-level <ins>/<del> refinement. Two modes: **compact** (the default, ±N lines
of context around each hunk, the rest elided behind a marker) and **whole
document** (`context=None`, every line, nothing elided — v3.1 step 03). All text
is HTML-escaped before any markup is added, so the result is safe to inject into
the viewer (which additionally runs DOMPurify — defense in depth).
"""

from __future__ import annotations

import difflib
import html
import re

_WORDS = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)


def _split_words(line: str) -> list[str]:
    return _WORDS.findall(line)


def _refine(old_line: str, new_line: str) -> tuple[str, str]:
    """Word-level <del>/<ins> markup for one replaced line pair."""
    old_w, new_w = _split_words(old_line), _split_words(new_line)
    sm = difflib.SequenceMatcher(a=old_w, b=new_w, autojunk=False)
    del_out, ins_out = [], []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        a_txt = html.escape("".join(old_w[a1:a2]))
        b_txt = html.escape("".join(new_w[b1:b2]))
        if op == "equal":
            del_out.append(a_txt)
            ins_out.append(b_txt)
        else:
            if a_txt:
                del_out.append(f"<del>{a_txt}</del>")
            if b_txt:
                ins_out.append(f"<ins>{b_txt}</ins>")
    return "".join(del_out), "".join(ins_out)


def _gutter(old_no: int | None, new_no: int | None, line_numbers: bool) -> str:
    """The two line-number spans of one row — "" when numbering is off.

    A deleted row has no new-side number and an inserted row has no old-side
    number: that span is emitted **empty** so both gutter columns keep their
    width and the rows stay aligned. The values are ``int``s, never document
    text, so nothing here can carry markup.
    """
    if not line_numbers:
        return ""
    o = "" if old_no is None else str(old_no)
    n = "" if new_no is None else str(new_no)
    return (
        f'<span class="diff-ln diff-ln-old">{o}</span>'
        f'<span class="diff-ln diff-ln-new">{n}</span>'
    )


def html_diff(
    old: str,
    new: str,
    *,
    context: int | None = 3,
    line_numbers: bool = False,
) -> str:
    """Line-grouped, word-refined diff as safe HTML (empty string if equal).

    ``context`` is the number of unchanged lines kept around each hunk;
    ``None`` renders the **whole document** with no elision marker. With
    ``line_numbers`` every row is prefixed by two gutter spans, old then new
    (v3.1 step 03 — the ``?view=full`` page and the downloadable diff
    artifact). Defaults reproduce the v3 output byte for byte.
    """
    if old == new:
        return ""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    # one group = the whole document when context is None, so the loop body
    # below is shared by both modes
    groups = [sm.get_opcodes()] if context is None else sm.get_grouped_opcodes(context)
    parts: list[str] = ['<div class="diff">']
    for group in groups:
        parts.append('<div class="diff-hunk">')
        for op, a1, a2, b1, b2 in group:
            if op == "equal":
                for k, line in enumerate(old_lines[a1:a2]):
                    g = _gutter(a1 + k + 1, b1 + k + 1, line_numbers)
                    parts.append(f'<div class="diff-ctx">{g}{html.escape(line)}</div>')
            elif op == "replace" and (a2 - a1) == (b2 - b1):
                for k, (o, n) in enumerate(zip(old_lines[a1:a2], new_lines[b1:b2])):
                    d, i = _refine(o, n)
                    gd = _gutter(a1 + k + 1, None, line_numbers)
                    gi = _gutter(None, b1 + k + 1, line_numbers)
                    parts.append(f'<div class="diff-del">{gd}{d}</div>')
                    parts.append(f'<div class="diff-ins">{gi}{i}</div>')
            else:
                for k, line in enumerate(old_lines[a1:a2]):
                    g = _gutter(a1 + k + 1, None, line_numbers)
                    parts.append(f'<div class="diff-del">{g}<del>{html.escape(line)}</del></div>')
                for k, line in enumerate(new_lines[b1:b2]):
                    g = _gutter(None, b1 + k + 1, line_numbers)
                    parts.append(f'<div class="diff-ins">{g}<ins>{html.escape(line)}</ins></div>')
        parts.append("</div>")
        if context is not None:                  # nothing is elided in full mode
            parts.append('<div class="diff-skip">⋯</div>')
    if parts[-1] == '<div class="diff-skip">⋯</div>':
        parts.pop()                              # no trailing elision marker
    parts.append("</div>")
    return "".join(parts)
