"""rtd.yaml validation and generated review minutes (docs/plan/05-lifecycle.md).

``validate`` checks the schema invariants a valid RTD must hold (this is the
check the GUI refers to); ``render_report`` produces ``report.md`` — review
minutes derived entirely from ``rtd.yaml`` (nothing invented), with a status
dashboard, per-reviewer stats, dispositions, and the open/deferred register.
"""

from __future__ import annotations

from pathlib import Path

from .constants import Disposition, Severity, Status
from .harvest import RTD_NAME
from .models import RTD


def validate(rtd: RTD) -> list[str]:
    """Return human-readable invariant violations (empty means valid)."""
    errors: list[str] = []
    ids = {r.rid for r in rtd.rids}
    seen: set[str] = set()
    for r in rtd.rids:
        if r.rid in seen:
            errors.append(f"duplicate RID id {r.rid}")
        seen.add(r.rid)
        if r.status is Status.VERIFIED:
            if not r.verified_by:
                errors.append(f"{r.rid}: verified but verified_by is empty")
            elif r.verified_by == rtd.meta.owner:
                errors.append(f"{r.rid}: verified_by is the owner (closure authority violated)")
        if r.status in (Status.ANSWERED, Status.IMPLEMENTED, Status.VERIFIED) and r.disposition is None:
            errors.append(f"{r.rid}: status {r.status.value} requires a disposition")
        if r.master:
            if r.master not in ids:
                errors.append(f"{r.rid}: master {r.master} does not exist")
            else:
                master = next(x for x in rtd.rids if x.rid == r.master)
                if r.rid not in master.duplicates:
                    errors.append(f"{r.rid}: master {r.master} does not list it as a duplicate")
    return errors


def render_report(rtd: RTD) -> str:
    """Render review minutes as Markdown from ``rtd`` alone."""
    rids, m = rtd.rids, rtd.meta
    n = len(rids)

    def count(pred) -> int:
        return sum(1 for r in rids if pred(r))

    out: list[str] = [f"# Review Minutes — {m.review_id}", ""]
    out += [
        f"- Document: `{m.document}`",
        f"- Baseline: `{m.baseline_sha}`",
        f"- Created: {m.created}",
        f"- Owner: {m.owner}",
        f"- Reviewers: {', '.join(m.reviewers) or '—'}",
        f"- Findings: {n}",
        "",
        "## Status",
        "",
        "| Status | Count |",
        "|---|---|",
    ]
    out += [f"| {s.value} | {count(lambda r, s=s: r.status is s)} |" for s in Status]
    closed = count(lambda r: r.status in (Status.VERIFIED, Status.WITHDRAWN))
    pct = round(100 * closed / n) if n else 0
    out += ["", f"Closed (verified or withdrawn): {closed} / {n} ({pct}%)", ""]

    out += ["## Severity", "", "| Severity | Count |", "|---|---|"]
    out += [f"| {sv.value} | {count(lambda r, sv=sv: r.severity is sv)} |" for sv in Severity]
    out += ["", "## Dispositions", "", "| Disposition | Count |", "|---|---|"]
    out += [f"| {d.value} | {count(lambda r, d=d: r.disposition is d)} |" for d in Disposition]
    out += [f"| (undecided) | {count(lambda r: r.disposition is None)} |", ""]

    out += ["## Per reviewer", "", "| Reviewer | Raised | Verified | Open |", "|---|---|---|---|"]
    for name in m.reviewers:
        raised = count(lambda r, x=name: r.reviewer == x)
        ver = count(lambda r, x=name: r.reviewer == x and r.status is Status.VERIFIED)
        opn = count(lambda r, x=name: r.reviewer == x and r.status is Status.OPEN)
        out.append(f"| {name} | {raised} | {ver} | {opn} |")

    out += ["", "## Open / deferred register", ""]
    register = [r for r in rids if r.status is Status.OPEN or r.disposition is Disposition.DEFERRED]
    if not register:
        out.append("_none_")
    else:
        for r in register:
            disp = r.disposition.value if r.disposition else "—"
            out.append(f"- `{r.rid}` [{r.status.value}] ({disp}) — {r.comment or ''}")

    out += [
        "",
        "## Sources",
        "",
        f"- Generated from `rtd.yaml` ({m.review_id}); baseline `{m.baseline_sha}`.",
    ]
    return "\n".join(out) + "\n"


def report_review(review_dir: Path | str) -> list[str]:
    """Validate the review's rtd.yaml; on success write ``report.md``. Returns errors."""
    review_dir = Path(review_dir)
    rtd = RTD.from_yaml((review_dir / RTD_NAME).read_text(encoding="utf-8"))
    errors = validate(rtd)
    if not errors:
        (review_dir / "report.md").write_text(render_report(rtd), encoding="utf-8")
    return errors
