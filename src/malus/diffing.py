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
from dataclasses import dataclass, field

_WORDS = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)


# --------------------------------------------------------------------------- #
# v3.2 point 13: which finding caused which hunk
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Attribution:
    """Where each line of the final document came from.

    ``inserted[i]`` are the findings that last wrote line *i* of the final text
    — empty when the line survives from the baseline untouched. ``deleted[j]``
    are the findings whose version removed baseline line *j*; a deletion leaves
    no line behind to carry a label, so it is recorded separately.

    Both are tuples of RID strings: one implementation session may legitimately
    resolve a cluster of duplicates (v3.2 step 04).
    """

    inserted: tuple[tuple[str, ...], ...] = ()
    deleted: dict[int, tuple[str, ...]] = field(default_factory=dict)

    def for_new_line(self, index: int) -> tuple[str, ...]:
        return self.inserted[index] if 0 <= index < len(self.inserted) else ()

    def for_old_line(self, index: int) -> tuple[str, ...]:
        return self.deleted.get(index, ())


def line_provenance(chain: list[tuple[str, list[str]]]) -> Attribution:
    """Carry line provenance through a chain of document versions.

    ``chain`` is ``[(baseline, []), (content, rids), …]`` in order. Each step's
    ``rids`` are the findings that version was saved against — which, since
    v3.2 step 04, is exactly the implementation session that produced it. That
    is what makes this sound: a version with one cause can label its lines.

    ``equal`` opcodes propagate both provenance and the baseline line each line
    descends from; ``insert`` and ``replace`` overwrite provenance with the
    current step's findings, and record the baseline lines that step removed.
    A line whose provenance cannot be established stays empty — the renderer
    shows no badge rather than a guess.
    """
    if not chain:
        return Attribution()
    baseline = chain[0][0].splitlines()
    prov: list[tuple[str, ...]] = [() for _ in baseline]
    origin: list[int | None] = list(range(len(baseline)))
    deleted: dict[int, tuple[str, ...]] = {}
    current = baseline

    for content, rids in chain[1:]:
        step = tuple(rids)
        nxt = content.splitlines()
        sm = difflib.SequenceMatcher(a=current, b=nxt, autojunk=False)
        new_prov: list[tuple[str, ...]] = []
        new_origin: list[int | None] = []
        for op, a1, a2, b1, b2 in sm.get_opcodes():
            if op == "equal":
                new_prov.extend(prov[a1:a2])
                new_origin.extend(origin[a1:a2])
                continue
            for i in range(a1, a2):          # lines this step removed
                if origin[i] is not None:
                    deleted[origin[i]] = step
            for _ in range(b1, b2):          # lines this step wrote
                new_prov.append(step)
                new_origin.append(None)
        prov, origin, current = new_prov, new_origin, nxt

    return Attribution(inserted=tuple(prov), deleted=deleted)


def _badge(rids: tuple[str, ...], rid_base: str | None = None) -> str:
    """The RID label on a changed row — empty when provenance is unknown.

    With ``rid_base`` each RID becomes a link to its comment; without it the
    label is inert text. The self-contained ``diff.html`` download passes
    nothing, because a link into the application would dangle the moment that
    file is e-mailed or archived.
    """
    if not rids:
        return ""
    if rid_base is None:
        text = html.escape(" ".join(rids))
        return f'<span class="diff-rid" title="{text}">{text}</span>'
    links = "".join(
        f'<a class="diff-rid" href="{html.escape(rid_base + rid, quote=True)}"'
        f' title="{html.escape(rid)}">{html.escape(rid)}</a>'
        for rid in rids
    )
    return links


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
    attribution: Attribution | None = None,
    rid_base: str | None = None,
) -> str:
    """Line-grouped, word-refined diff as safe HTML (empty string if equal).

    ``context`` is the number of unchanged lines kept around each hunk;
    ``None`` renders the **whole document** with no elision marker. With
    ``line_numbers`` every row is prefixed by two gutter spans, old then new
    (v3.1 step 03 — the ``?view=full`` page and the downloadable diff
    artifact). With ``attribution`` every changed row carries the finding that
    caused it (v3.2 point 13); a row whose provenance is unknown carries
    nothing, and with ``rid_base`` each badge links to its comment. Defaults
    reproduce the v3 output byte for byte — the per-finding ``Changes`` section
    and the v3.1 downloads depend on that.
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
                    bd = _badge(attribution.for_old_line(a1 + k), rid_base) if attribution else ""
                    bi = _badge(attribution.for_new_line(b1 + k), rid_base) if attribution else ""
                    parts.append(f'<div class="diff-del">{gd}{bd}{d}</div>')
                    parts.append(f'<div class="diff-ins">{gi}{bi}{i}</div>')
            else:
                for k, line in enumerate(old_lines[a1:a2]):
                    g = _gutter(a1 + k + 1, None, line_numbers)
                    b = _badge(attribution.for_old_line(a1 + k), rid_base) if attribution else ""
                    parts.append(f'<div class="diff-del">{g}{b}<del>{html.escape(line)}</del></div>')
                for k, line in enumerate(new_lines[b1:b2]):
                    g = _gutter(None, b1 + k + 1, line_numbers)
                    b = _badge(attribution.for_new_line(b1 + k), rid_base) if attribution else ""
                    parts.append(f'<div class="diff-ins">{g}{b}<ins>{html.escape(line)}</ins></div>')
        parts.append("</div>")
        if context is not None:                  # nothing is elided in full mode
            parts.append('<div class="diff-skip">⋯</div>')
    if parts[-1] == '<div class="diff-skip">⋯</div>':
        parts.pop()                              # no trailing elision marker
    parts.append("</div>")
    return "".join(parts)
