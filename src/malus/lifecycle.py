"""Reviewer-side verification and commit↔RID traceability (docs/plan/05-lifecycle.md).

Traceability links each accepted RID to the commit(s) that implement it: a RID
is *referenced* when its id appears in a commit message between the frozen
baseline SHA and HEAD. Verification is reviewer-side — the owner identity can
never issue a verdict — and reopening sends a RID back to ``open`` with a
mandatory reason appended to its thread.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .constants import Disposition, Role, Status
from .harvest import BASELINE_NAME, RTD_NAME
from .models import RID, RTD, TransitionError, transition
from .report import render_report, validate


@dataclass
class TraceabilityReport:
    referenced: dict[str, list[str]] = field(default_factory=dict)
    accepted_unreferenced: list[str] = field(default_factory=list)
    referenced_not_accepted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.accepted_unreferenced and not self.referenced_not_accepted


def commits_since(repo: Path | str, sha: str) -> list[tuple[str, str]]:
    """Return ``[(commit_sha, message)]`` for ``sha..HEAD`` in ``repo``."""
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--pretty=format:%H%x1f%B%x1e", f"{sha}..HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"git log {sha}..HEAD failed: {result.stderr.strip()}")
    commits: list[tuple[str, str]] = []
    for record in result.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        commit_sha, _, body = record.partition("\x1f")
        commits.append((commit_sha.strip(), body))
    return commits


def check_traceability(rtd: RTD, repo: Path | str) -> TraceabilityReport:
    """Cross-check accepted RIDs against commit references (baseline SHA → HEAD)."""
    commits = commits_since(repo, rtd.meta.baseline_sha)
    rid_ids = [r.rid for r in rtd.rids]
    referenced: dict[str, list[str]] = {}
    for commit_sha, body in commits:
        for rid in rid_ids:
            if rid in body:
                referenced.setdefault(rid, []).append(commit_sha)
    accepted = {r.rid for r in rtd.rids if r.disposition is Disposition.ACCEPTED}
    return TraceabilityReport(
        referenced=referenced,
        accepted_unreferenced=sorted(a for a in accepted if a not in referenced),
        referenced_not_accepted=sorted(r for r in referenced if r not in accepted),
    )


def _find(rtd: RTD, rid_id: str) -> RID:
    for rid in rtd.rids:
        if rid.rid == rid_id:
            return rid
    raise ValueError(f"no such RID: {rid_id}")


def pending_for_reviewer(rtd: RTD, reviewer: str) -> list[RID]:
    """That reviewer's RIDs awaiting their verdict (answered or implemented)."""
    return [
        r
        for r in rtd.rids
        if r.reviewer == reviewer and r.status in (Status.ANSWERED, Status.IMPLEMENTED)
    ]


def verify_rid(
    rtd: RTD,
    rid_id: str,
    *,
    reviewer: str,
    moderator: bool = False,
    on: _dt.date | None = None,
) -> RID:
    """Verify a RID as a reviewer (or moderator on their behalf)."""
    if not reviewer:
        raise ValueError("a reviewer name is required to verify")
    if reviewer == rtd.meta.owner:
        raise TransitionError("the owner identity may never issue a verdict")
    rid = _find(rtd, rid_id)
    role = Role.MODERATOR if moderator else Role.REVIEWER
    transition(rid, Status.VERIFIED, actor_role=role, actor_name=reviewer, on=on)
    return rid


def reopen_rid(
    rtd: RTD,
    rid_id: str,
    *,
    reviewer: str,
    reason: str,
    moderator: bool = False,
) -> RID:
    """Send a RID back to ``open`` with a mandatory reason appended to its thread."""
    if not reviewer:
        raise ValueError("a reviewer name is required to reopen")
    if not reason or not reason.strip():
        raise ValueError("reopening a RID requires a reason")
    rid = _find(rtd, rid_id)
    if reviewer == rtd.meta.owner:
        raise TransitionError("the owner identity may never reopen a RID")
    if not moderator and rid.reviewer != reviewer:
        raise TransitionError(f"only the RID's own reviewer ({rid.reviewer!r}) may reopen it")
    if rid.status not in (Status.ANSWERED, Status.IMPLEMENTED, Status.VERIFIED):
        raise TransitionError(f"cannot reopen a RID in status {rid.status.value!r}")
    note = f"[reopened by {reviewer}: {reason.strip()}]"
    rid.reply = f"{rid.reply}\n{note}" if rid.reply else note
    rid.status = Status.OPEN
    rid.verified_by = None
    rid.verified_on = None
    return rid


_CARRYOVER_FIELDS = ("rid", "reviewer", "kind", "type", "severity", "comment", "anchor")


def finalize_review(review_dir: Path | str) -> list[str]:
    """Finalize a review: refuse unless every RID is verified/withdrawn and valid.

    On success, writes ``final.md`` (the finalized document, from the working
    copy), ``report.md`` (minutes), ``carryover.yaml`` (deferred findings for the
    next cycle), and a ``FINALIZED`` marker. Returns blocking errors (empty = done).
    """
    review_dir = Path(review_dir)
    rtd = RTD.from_yaml((review_dir / RTD_NAME).read_text(encoding="utf-8"))

    errors: list[str] = []
    open_rids = [
        r.rid for r in rtd.rids if r.status not in (Status.VERIFIED, Status.WITHDRAWN)
    ]
    if open_rids:
        errors.append("findings not yet verified/withdrawn: " + ", ".join(open_rids))
    errors += validate(rtd)
    if errors:
        return errors

    working = review_dir / "working.md"
    source = working if working.exists() else review_dir / BASELINE_NAME
    (review_dir / "final.md").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (review_dir / "report.md").write_text(render_report(rtd), encoding="utf-8")

    deferred = [r for r in rtd.rids if r.disposition is Disposition.DEFERRED]
    carryover = {
        "source_review": rtd.meta.review_id,
        "baseline_sha": rtd.meta.baseline_sha,
        "deferred": [{k: r.to_dict()[k] for k in _CARRYOVER_FIELDS} for r in deferred],
    }
    (review_dir / "carryover.yaml").write_text(
        yaml.safe_dump(carryover, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (review_dir / "FINALIZED").write_text(
        f"Finalized {rtd.meta.review_id}: {len(rtd.rids)} findings, "
        f"{len(deferred)} deferred to the next cycle.\n",
        encoding="utf-8",
    )
    return []
