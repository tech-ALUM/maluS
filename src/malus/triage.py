"""Triage: cluster duplicate findings and apply mechanical suggestions.

Clustering proposes groups of near-identical ``{COMM}`` findings in the same
section; one is chosen as the master and the rest link to it as duplicates
(their status follows the master). Suggestion apply replaces each ``{SUGG}``'s
``old`` text with its ``new`` text in a working copy, flagging (never guessing)
suggestions whose ``old`` text is no longer present. See docs/plan/03-triage.md.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

from .constants import Disposition, Kind, Status
from .harvest import BASELINE_NAME, RTD_NAME
from .models import RTD
from .parser import scan

CLUSTER_THRESHOLD = 0.6  # similarity to propose a duplicate group
AUTO_THRESHOLD = 0.82  # similarity to auto-accept a duplicate link


@dataclass
class DuplicateLink:
    duplicate: str  # RID id
    confidence: float  # similarity to the master's comment, 0..1


@dataclass
class ClusterProposal:
    master: str  # RID id
    links: list[DuplicateLink] = field(default_factory=list)


@dataclass
class SuggResult:
    rid: str
    old: str
    new: str
    applied: bool
    reason: str = ""


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _similarity(a: str | None, b: str | None) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _rid_number(rid: str) -> int:
    tail = rid.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


# --------------------------------------------------------------------------- #
# duplicate clustering
# --------------------------------------------------------------------------- #


def propose_clusters(rtd: RTD, *, threshold: float = CLUSTER_THRESHOLD) -> list[ClusterProposal]:
    """Propose duplicate groups among ``{COMM}`` findings (no mutation)."""
    comms = [r for r in rtd.rids if r.kind is Kind.COMM and r.status is not Status.WITHDRAWN]
    parent = {r.rid: r.rid for r in comms}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(comms):
        for b in comms[i + 1 :]:
            same_section = (a.anchor.section or "") == (b.anchor.section or "")
            if same_section and _similarity(a.comment, b.comment) >= threshold:
                parent[find(a.rid)] = find(b.rid)

    groups: dict[str, list] = {}
    for r in comms:
        groups.setdefault(find(r.rid), []).append(r)

    by_id = {r.rid: r for r in comms}
    proposals: list[ClusterProposal] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda r: (_rid_number(r.rid), r.rid))
        master = members[0]
        links = [
            DuplicateLink(d.rid, round(_similarity(master.comment, d.comment), 3))
            for d in members[1:]
        ]
        links.sort(key=lambda link: link.duplicate)
        proposals.append(ClusterProposal(master.rid, links))
    proposals.sort(key=lambda p: (_rid_number(p.master), p.master))
    return proposals


def apply_clusters(rtd: RTD, proposals: list[ClusterProposal]) -> int:
    """Link the proposed duplicates to their masters; return links applied."""
    by_id = {r.rid: r for r in rtd.rids}
    applied = 0
    for proposal in proposals:
        master = by_id[proposal.master]
        for link in proposal.links:
            dup = by_id[link.duplicate]
            if dup.master == master.rid:
                continue
            dup.master = master.rid
            dup.status = master.status  # duplicate status follows the master
            if dup.rid not in master.duplicates:
                master.duplicates.append(dup.rid)
            applied += 1
    for r in rtd.rids:
        r.duplicates.sort()
    return applied


# --------------------------------------------------------------------------- #
# mechanical suggestion apply
# --------------------------------------------------------------------------- #


def parse_sugg_comment(comment: str) -> tuple[str, str]:
    """Recover ``(old, new)`` from a rendered SUGG comment via the parser."""
    block = scan("{SUGG: " + comment + "}")[0]
    return block.old or "", block.new or ""


def apply_suggs(text: str, rtd: RTD) -> tuple[str, list[SuggResult]]:
    """Apply every non-rejected ``{SUGG}`` to ``text`` (first match), report each."""
    out = text
    results: list[SuggResult] = []
    for r in rtd.rids:
        if r.kind is not Kind.SUGG:
            continue
        old, new = parse_sugg_comment(r.comment or "")
        if r.status is Status.WITHDRAWN or r.disposition is Disposition.REJECTED:
            results.append(SuggResult(r.rid, old, new, False, "rejected or withdrawn"))
            continue
        if old not in out:
            results.append(SuggResult(r.rid, old, new, False, "old text not found"))
            continue
        out = out.replace(old, new, 1)
        results.append(SuggResult(r.rid, old, new, True))
    return out, results


# --------------------------------------------------------------------------- #
# review-level orchestration
# --------------------------------------------------------------------------- #


def triage_review(
    review_dir: Path | str,
    *,
    auto: bool = False,
    threshold: float = CLUSTER_THRESHOLD,
    auto_threshold: float = AUTO_THRESHOLD,
) -> tuple[list[ClusterProposal], int]:
    """Propose duplicate groups; with ``auto`` link high-confidence ones and save."""
    review_dir = Path(review_dir)
    rtd_path = review_dir / RTD_NAME
    rtd = RTD.from_yaml(rtd_path.read_text(encoding="utf-8"))
    proposals = propose_clusters(rtd, threshold=threshold)
    applied = 0
    if auto:
        confident = [
            ClusterProposal(p.master, [l for l in p.links if l.confidence >= auto_threshold])
            for p in proposals
        ]
        applied = apply_clusters(rtd, [p for p in confident if p.links])
        rtd_path.write_text(rtd.to_yaml(), encoding="utf-8")
    return proposals, applied


def apply_suggs_review(
    review_dir: Path | str,
    *,
    dry_run: bool = False,
    out: Path | str | None = None,
) -> tuple[str, list[SuggResult]]:
    """Apply accepted suggestions to a working copy; return the diff and per-SUGG results."""
    review_dir = Path(review_dir)
    baseline = (review_dir / BASELINE_NAME).read_text(encoding="utf-8")
    rtd = RTD.from_yaml((review_dir / RTD_NAME).read_text(encoding="utf-8"))
    new_text, results = apply_suggs(baseline, rtd)
    diff = "".join(
        difflib.unified_diff(
            baseline.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=BASELINE_NAME,
            tofile="working.md",
        )
    )
    if not dry_run:
        target = Path(out) if out else review_dir / "working.md"
        target.write_text(new_text, encoding="utf-8")
    return diff, results
