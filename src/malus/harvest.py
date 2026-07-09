"""Freeze validation, anchoring, and rtd.yaml assembly (docs/plan/02-harvest.md).

The freeze rule (D1) is validated by stripping every parsed comment block from
a reviewer copy and requiring the residue to differ from the baseline only in
whitespace. Anchors are computed in the baseline coordinate space, and RID ids
are assigned in document order and reconciled across re-harvests by content.
"""

from __future__ import annotations

import datetime as _dt
import difflib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .constants import CommentType, Kind, Severity, Status
from .models import RID, RTD, Anchor, Meta
from .parser import ParseError, ParsedBlock, scan

BASELINE_NAME = "baseline.md"
RTD_NAME = "rtd.yaml"
REVIEWERS_DIR = "reviewers"

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


def validate_insertion_only(baseline: str, copy: str) -> list[ParsedBlock]:
    """Return the copy's comment blocks, or raise if it edits baseline text.

    Raises :class:`FreezeViolation` for a non-comment change and
    :class:`malus.parser.ParseError` for a malformed block.
    """
    blocks = scan(copy)
    residue = _remove_spans(copy, [(b.start, b.end) for b in blocks])
    matcher = difflib.SequenceMatcher(a=baseline, b=residue, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if baseline[i1:i2].strip() or residue[j1:j2].strip():
            line = baseline[:i1].count("\n") + 1
            raise FreezeViolation(f"non-comment change at baseline line {line}", line)
    return blocks


# --------------------------------------------------------------------------- #
# anchoring
# --------------------------------------------------------------------------- #


def _build_r2b(baseline: str, residue: str) -> list[int]:
    """Map each residue offset to its baseline offset (residue ⊇ baseline + ws)."""
    r2b = [0] * (len(residue) + 1)
    matcher = difflib.SequenceMatcher(a=baseline, b=residue, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for off in range(j1, j2):
                r2b[off] = i1 + (off - j1)
        else:
            for off in range(j1, j2):
                r2b[off] = i1
    r2b[len(residue)] = len(baseline)
    return r2b


def _anchor(baseline: str, offset: int) -> Anchor:
    before = baseline[:offset]
    line_hint = before.count("\n") + 1
    section: str | None = None
    for line in before.split("\n"):
        match = _HEADING.match(line)
        if match:
            section = match.group(1)
    quote = " ".join(before[-120:].split()) or None
    return Anchor(section=section, quote=quote, line_hint=line_hint)


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


def _render_sugg(old: str, new: str) -> str:
    return f'"{old}" -> "{new}"'


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


# --------------------------------------------------------------------------- #
# file-based review instance (reviewer copies are files, per the D1 deviation)
# --------------------------------------------------------------------------- #


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _baseline_sha(baseline_path: Path) -> str:
    """Return the git blob SHA of the baseline (deterministic, no commit needed)."""
    result = subprocess.run(
        ["git", "hash-object", str(baseline_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def init_review(
    review_id: str,
    document: Path | str,
    *,
    reviews_root: Path | str = "reviews",
    owner: str | None = None,
    reviewers: list[str] | None = None,
    created: _dt.date | None = None,
) -> Path:
    """Create a new review instance from a source Markdown document.

    Lays out ``<reviews_root>/<review_id>/`` with ``baseline.md`` (copied from
    ``document``), an empty ``reviewers/`` directory, and an ``rtd.yaml`` whose
    meta is seeded (``baseline_sha`` stays empty until ``freeze`` records it).
    Refuses to overwrite an existing review.
    """
    source = Path(document)
    review_dir = Path(reviews_root) / review_id
    rtd_path = review_dir / RTD_NAME
    if rtd_path.exists():
        raise FileExistsError(f"review already exists: {rtd_path}")
    if not source.is_file():
        raise FileNotFoundError(f"document not found: {source}")
    (review_dir / REVIEWERS_DIR).mkdir(parents=True, exist_ok=True)
    (review_dir / BASELINE_NAME).write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    rtd = RTD(
        meta=Meta(
            review_id=review_id,
            document=BASELINE_NAME,
            baseline_sha="",
            created=created or _dt.date.today(),
            owner=owner or "",
            reviewers=list(reviewers or []),
        )
    )
    rtd_path.write_text(rtd.to_yaml(), encoding="utf-8")
    return review_dir


def freeze_review(
    review_dir: Path | str,
    *,
    review_id: str | None = None,
    owner: str | None = None,
    reviewers: list[str] | None = None,
) -> str:
    """Record the baseline SHA into the review meta, creating rtd.yaml if absent."""
    review_dir = Path(review_dir)
    sha = _baseline_sha(review_dir / BASELINE_NAME)
    rtd_path = review_dir / RTD_NAME
    if rtd_path.exists():
        rtd = RTD.from_yaml(_read(rtd_path))
        rtd.meta.baseline_sha = sha
        if review_id:
            rtd.meta.review_id = review_id
        if owner:
            rtd.meta.owner = owner
        if reviewers is not None:
            rtd.meta.reviewers = list(reviewers)
    else:
        rtd = RTD(
            meta=Meta(
                review_id=review_id or review_dir.resolve().name,
                document=BASELINE_NAME,
                baseline_sha=sha,
                created=_dt.date.today(),
                owner=owner or "",
                reviewers=list(reviewers or []),
            )
        )
    rtd_path.write_text(rtd.to_yaml(), encoding="utf-8")
    return sha


def make_copies(review_dir: Path | str) -> list[Path]:
    """Create a per-reviewer baseline copy for each meta reviewer lacking one."""
    review_dir = Path(review_dir)
    rtd = RTD.from_yaml(_read(review_dir / RTD_NAME))
    baseline = _read(review_dir / BASELINE_NAME)
    reviewers_dir = review_dir / REVIEWERS_DIR
    reviewers_dir.mkdir(exist_ok=True)
    created: list[Path] = []
    for name in rtd.meta.reviewers:
        path = reviewers_dir / f"{name}.md"
        if not path.exists():
            path.write_text(baseline, encoding="utf-8")
            created.append(path)
    return created


def harvest_review(review_dir: Path | str) -> HarvestResult:
    """Harvest all reviewer copies in a review directory and rewrite rtd.yaml."""
    review_dir = Path(review_dir)
    rtd_path = review_dir / RTD_NAME
    if not rtd_path.exists():
        raise FileNotFoundError(
            f"{rtd_path} not found; run 'malus freeze' to create the review meta first"
        )
    baseline = _read(review_dir / BASELINE_NAME)
    existing = RTD.from_yaml(_read(rtd_path))
    copies: dict[str, str] = {}
    reviewers_dir = review_dir / REVIEWERS_DIR
    if reviewers_dir.is_dir():
        for path in sorted(reviewers_dir.glob("*.md")):
            copies[path.stem] = _read(path)
    result = build_rtd(baseline, existing.meta, copies, existing=existing)
    rtd_path.write_text(result.rtd.to_yaml(), encoding="utf-8")
    return result
