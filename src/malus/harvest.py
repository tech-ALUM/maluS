"""Freeze validation, anchoring, and RTD assembly (the reusable harvest core).

The freeze rule (D1) is validated by stripping every parsed comment block from
a reviewer copy and requiring the residue to differ from the baseline only in
whitespace. Anchors are computed in the baseline coordinate space, and RID ids
are assigned in document order and reconciled across re-harvests by content.

This module is storage-agnostic: it operates on strings and :class:`RTD`
objects. The DB-backed orchestration lives in ``malus.services`` (v1);
``malus.legacy`` imports v0 file-based reviews.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .constants import CommentType, Kind, Severity, Status
from .models import RID, RTD, Anchor, Meta
from .parser import ParseError, ParsedBlock, scan

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*$")


class FreezeViolation(Exception):
    """A reviewer copy changed baseline text (not a pure comment insertion)."""

    def __init__(self, message: str, line: int | None = None) -> None:
        self.message = message
        self.line = line
        super().__init__(message)


@dataclass
class Violation:
    """A per-copy harvest failure (freeze rule broken or a malformed block)."""

    reviewer: str
    message: str
    line: int | None = None


@dataclass
class HarvestResult:
    rtd: RTD
    violations: list[Violation] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# freeze validation
# --------------------------------------------------------------------------- #


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    out: list[str] = []
    prev = 0
    for start, end in sorted(spans):
        out.append(text[prev:start])
        prev = end
    out.append(text[prev:])
    return "".join(out)


def _align_ws(baseline: str, residue: str) -> list[int]:
    """Align residue to baseline tolerating only whitespace differences — O(n).

    Returns ``r2b`` (length ``len(residue) + 1``) mapping each residue offset
    to its baseline offset, with ``r2b[len(residue)] == len(baseline)``.
    Raises :class:`FreezeViolation` at the first non-whitespace mismatch
    (a residue is valid iff it equals the baseline after removing every
    whitespace character — the freeze rule D1). Replaces the two char-level
    difflib passes of v1 (v2 step 1).
    """
    nb, nr = len(baseline), len(residue)
    r2b = [0] * (nr + 1)
    i = j = 0

    def _violate() -> None:
        line = baseline[:i].count("\n") + 1
        raise FreezeViolation(f"non-comment change at baseline line {line}", line)

    while j < nr:
        ch = residue[j]
        if i < nb and baseline[i] == ch:
            r2b[j] = i
            i += 1
            j += 1
        elif ch.isspace():
            r2b[j] = i if i < nb else nb
            j += 1
        elif i < nb and baseline[i].isspace():
            i += 1
        else:
            _violate()
    while i < nb:  # leftover baseline must be pure whitespace
        if not baseline[i].isspace():
            _violate()
        i += 1
    r2b[nr] = nb
    return r2b


def validate_insertion_only(baseline: str, copy: str) -> list[ParsedBlock]:
    """Return the copy's comment blocks, or raise if it edits baseline text.

    Raises :class:`FreezeViolation` for a non-comment change and
    :class:`malus.parser.ParseError` for a malformed block.
    """
    blocks = scan(copy)
    residue = _remove_spans(copy, [(b.start, b.end) for b in blocks])
    _align_ws(baseline, residue)
    return blocks


# --------------------------------------------------------------------------- #
# anchoring
# --------------------------------------------------------------------------- #


def _build_r2b(baseline: str, residue: str) -> list[int]:
    """Map each residue offset to its baseline offset (residue ⊇ baseline + ws)."""
    return _align_ws(baseline, residue)


def _anchor(baseline: str, offset: int) -> Anchor:
    before = baseline[:offset]
    line_hint = before.count("\n") + 1
    section: str | None = None
    for line in before.split("\n"):
        match = _HEADING.match(line)
        if match:
            section = match.group(1)
    quote = " ".join(before[-120:].split()) or None
    return Anchor(section=section, quote=quote, line_hint=line_hint, offset=offset)


# --------------------------------------------------------------------------- #
# rtd.yaml assembly
# --------------------------------------------------------------------------- #


def _rid_prefix(meta: Meta) -> str:
    if meta.rid_prefix:
        return meta.rid_prefix
    head, sep, _tail = meta.review_id.rpartition("-")
    return head if sep and head else meta.review_id


def _rid_number(rid_id: str, prefix: str) -> int | None:
    lead = f"{prefix}-"
    if rid_id.startswith(lead) and rid_id[len(lead) :].isdigit():
        return int(rid_id[len(lead) :])
    return None


def _esc_operand(s: str) -> str:
    """Escape a SUGG operand so ``{SUGG: <rendered>}`` re-parses to the original."""
    return s.replace("}", "\\}").replace('"', '\\"')


def _render_sugg(old: str, new: str) -> str:
    return f'"{_esc_operand(old)}" -> "{_esc_operand(new)}"'


def _identity(
    kind: Kind,
    comment_type: CommentType | None,
    severity: Severity | None,
    comment: str,
    reviewer: str,
) -> tuple:
    content = (
        kind.value,
        comment_type.value if comment_type else "",
        severity.value if severity else "",
        comment,
    )
    # {COMM} identity is per-reviewer; identical {SUGG}s dedup across reviewers.
    return (reviewer if kind is Kind.COMM else "", content)


def build_rtd(
    baseline: str,
    meta: Meta,
    copies: dict[str, str],
    existing: RTD | None = None,
) -> HarvestResult:
    """Assemble an ``RTD`` from reviewer copies, reconciling with ``existing``."""
    prefix = _rid_prefix(meta)
    violations: list[Violation] = []
    findings: list[dict] = []

    for reviewer in sorted(copies):
        copy_text = copies[reviewer]
        try:
            blocks = validate_insertion_only(baseline, copy_text)
        except (ParseError, FreezeViolation) as exc:
            violations.append(
                Violation(reviewer, str(exc), getattr(exc, "line", None))
            )
            continue
        residue = _remove_spans(copy_text, [(b.start, b.end) for b in blocks])
        r2b = _build_r2b(baseline, residue)
        removed = 0
        for block in blocks:
            residue_off = block.start - removed
            removed += block.end - block.start
            anchor = _anchor(baseline, r2b[residue_off])
            if block.kind is Kind.COMM:
                comment, ctype, sev = block.text, block.comment_type, block.severity
            else:
                comment, ctype, sev = _render_sugg(block.old, block.new), None, None
            findings.append(
                {
                    "reviewer": reviewer,
                    "kind": block.kind,
                    "type": ctype,
                    "severity": sev,
                    "comment": comment,
                    "anchor": anchor,
                    "base_off": r2b[residue_off],
                    "copy_off": block.start,
                }
            )

    findings.sort(key=lambda f: (f["base_off"], f["reviewer"], f["copy_off"]))

    deduped: list[dict] = []
    seen_sugg: set[str] = set()
    for finding in findings:
        if finding["kind"] is Kind.SUGG:
            if finding["comment"] in seen_sugg:
                continue
            seen_sugg.add(finding["comment"])
        deduped.append(finding)

    existing_rids = list(existing.rids) if existing else []
    by_identity = {
        _identity(r.kind, r.type, r.severity, r.comment or "", r.reviewer): r
        for r in existing_rids
    }
    output: dict[str, RID] = {r.rid: r for r in existing_rids}
    seen_ids: set[str] = set()
    new_findings: list[dict] = []

    for finding in deduped:
        ident = _identity(
            finding["kind"],
            finding["type"],
            finding["severity"],
            finding["comment"],
            finding["reviewer"],
        )
        match = by_identity.get(ident)
        if match is not None:
            match.anchor = finding["anchor"]
            if match.status is Status.WITHDRAWN:
                match.status = Status.OPEN  # finding reappeared
            seen_ids.add(match.rid)
        else:
            new_findings.append(finding)

    next_num = max((_rid_number(rid_id, prefix) or 0 for rid_id in output), default=0)
    for finding in new_findings:
        next_num += 1
        rid_id = f"{prefix}-{next_num:04d}"
        output[rid_id] = RID(
            rid=rid_id,
            reviewer=finding["reviewer"],
            created=meta.created,
            kind=finding["kind"],
            anchor=finding["anchor"],
            type=finding["type"],
            severity=finding["severity"],
            status=Status.OPEN,
            comment=finding["comment"],
        )
        seen_ids.add(rid_id)

    for rid in existing_rids:
        if rid.rid not in seen_ids and rid.status is not Status.WITHDRAWN:
            rid.status = Status.WITHDRAWN

    ordered = sorted(
        output.values(), key=lambda r: (_rid_number(r.rid, prefix) or 0, r.rid)
    )
    return HarvestResult(rtd=RTD(meta=meta, rids=ordered), violations=violations)
