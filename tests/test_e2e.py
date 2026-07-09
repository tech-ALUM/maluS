"""End-to-end: the full maluS pipeline on the synthetic SRS demo, in a git repo.

init -> freeze -> copies -> harvest -> triage --auto -> apply-suggs ->
disposition (headless rtd.yaml edits) -> implement (RID-referenced commit) ->
verify (with one reopen then re-verify) -> finalize.
"""

import datetime as dt
import shutil
import subprocess
from pathlib import Path

from malus.constants import Disposition, Role, Status
from malus.harvest import freeze_review, harvest_review, init_review, make_copies
from malus.lifecycle import check_traceability, finalize_review, reopen_rid, verify_rid
from malus.models import RTD, transition
from malus.triage import apply_suggs_review, triage_review

DEMO = Path(__file__).parent.parent / "examples" / "srs-demo"
REVIEWERS = ["A. Rossi", "B. Bianchi", "C. Verdi"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _load(review: Path) -> RTD:
    return RTD.from_yaml((review / "rtd.yaml").read_text(encoding="utf-8"))


def _save(review: Path, rtd: RTD) -> None:
    (review / "rtd.yaml").write_text(rtd.to_yaml(), encoding="utf-8")


def test_end_to_end_srs_demo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")

    # 1. init a review from the synthetic SRS
    review = init_review(
        "SIN-SRS-R1",
        DEMO / "srs.md",
        reviews_root=repo / "reviews",
        owner="A. Boffi",
        reviewers=REVIEWERS,
        created=dt.date(2026, 7, 3),
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: init SIN-SRS-R1 review")

    # 2. freeze — records the baseline commit SHA
    freeze_review(review)

    # 3. copies (blank per-reviewer copies), then drop in the scripted scenario
    make_copies(review)
    for name in REVIEWERS:
        shutil.copyfile(DEMO / "reviewers" / f"{name}.md", review / "reviewers" / f"{name}.md")

    # 4. harvest — C. Verdi edited baseline text → freeze violation; the rest harvest
    result = harvest_review(review)
    assert any(v.reviewer == "C. Verdi" for v in result.violations)
    assert [r.rid for r in result.rtd.rids] == [
        "SIN-SRS-0001",
        "SIN-SRS-0002",
        "SIN-SRS-0003",
        "SIN-SRS-0004",
    ]

    # 5. triage --auto — the two timeout findings cluster (0001 master, 0002 duplicate)
    triage_review(review, auto=True)
    by = {r.rid: r for r in _load(review).rids}
    assert by["SIN-SRS-0002"].master == "SIN-SRS-0001"
    assert "SIN-SRS-0002" in by["SIN-SRS-0001"].duplicates

    # 6. apply-suggs — both mechanical suggestions apply to a working copy
    _diff, sugg = apply_suggs_review(review)
    assert sum(r.applied for r in sugg) == 2
    working = (review / "working.md").read_text(encoding="utf-8")
    assert "the device" in working and "115,200" in working

    # 7. disposition — headless owner edits (as the GUI would write)
    rtd = _load(review)
    by = {r.rid: r for r in rtd.rids}
    for rid in ("SIN-SRS-0001", "SIN-SRS-0003", "SIN-SRS-0004"):
        by[rid].disposition = Disposition.ACCEPTED
        by[rid].reply = "agreed"
        by[rid].status = Status.ANSWERED
    # the duplicate is withdrawn by its own reviewer
    transition(by["SIN-SRS-0002"], Status.WITHDRAWN, actor_role=Role.REVIEWER, actor_name="B. Bianchi")
    _save(review, rtd)

    # 8. implement — one commit referencing the accepted RIDs
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "fix(srs): bound timeout and apply suggestions — SIN-SRS-0001 SIN-SRS-0003 SIN-SRS-0004",
    )
    report = check_traceability(_load(review), repo)
    assert report.ok  # every accepted RID is now referenced

    rtd = _load(review)
    by = {r.rid: r for r in rtd.rids}
    for rid in ("SIN-SRS-0001", "SIN-SRS-0003", "SIN-SRS-0004"):
        by[rid].status = Status.IMPLEMENTED  # owner marks implemented after the commit

    # 9. verify — reviewer closes; one reopen then re-verify
    verify_rid(rtd, "SIN-SRS-0001", reviewer="A. Rossi", on=dt.date(2026, 7, 9))
    assert by["SIN-SRS-0001"].status is Status.VERIFIED
    reopen_rid(rtd, "SIN-SRS-0001", reviewer="A. Rossi", reason="bound value still unclear")
    assert by["SIN-SRS-0001"].status is Status.OPEN
    assert by["SIN-SRS-0001"].verified_by is None
    # owner re-answers and re-implements (already referenced); reviewer verifies again
    by["SIN-SRS-0001"].status = Status.ANSWERED
    by["SIN-SRS-0001"].status = Status.IMPLEMENTED
    verify_rid(rtd, "SIN-SRS-0001", reviewer="A. Rossi", on=dt.date(2026, 7, 9))
    verify_rid(rtd, "SIN-SRS-0003", reviewer="A. Rossi", on=dt.date(2026, 7, 9))
    verify_rid(rtd, "SIN-SRS-0004", reviewer="B. Bianchi", on=dt.date(2026, 7, 9))
    _save(review, rtd)

    # every finding is now verified or withdrawn
    final = _load(review)
    assert all(r.status in (Status.VERIFIED, Status.WITHDRAWN) for r in final.rids)

    # 10. finalize — produces the outputs and refuses nothing
    errors = finalize_review(review)
    assert errors == []
    for name in ("final.md", "report.md", "carryover.yaml", "FINALIZED"):
        assert (review / name).exists()
