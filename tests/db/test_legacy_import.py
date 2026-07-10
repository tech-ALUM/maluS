"""The v0 fixture reviews run through the DB (v1 Step 2 DoD): import a v0
review directory, then drive the whole pipeline over the database."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from malus import services as svc
from malus.constants import Disposition
from malus.legacy import import_review_dir
from malus.repo import ReviewerCopyRepo, RidRepo, VersionRepo, content_hash

SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-review"


def test_import_seeds_review_baseline_and_copies(session: Session):
    review = import_review_dir(session, SAMPLE)
    session.commit()

    assert review.review_id_str == "SIN-SRS-R1"
    assert review.owner.display_name == "A. Boffi"
    base = VersionRepo(session).baseline(review)
    assert base.content_hash == content_hash((SAMPLE / "baseline.md").read_text())
    assert len(ReviewerCopyRepo(session).list(review)) == 3  # F. Miccoli, R. Bianchi, G. Verdi


def test_pipeline_over_imported_v0_review(session: Session):
    review = import_review_dir(session, SAMPLE)
    session.commit()

    result = svc.harvest(session, review)
    session.commit()
    # G. Verdi edited baseline text (CSV -> JSON): a freeze-rule violation
    assert [v.reviewer for v in result.violations] == ["G. Verdi"]
    rids = RidRepo(session).list(review)
    assert sorted(r.kind for r in rids) == ["COMM", "COMM", "SUGG"]  # SUGG deduped across F+R

    # re-harvest is idempotent (stable ids, no churn)
    before = [r.rid_str for r in rids]
    svc.harvest(session, review)
    session.commit()
    assert [r.rid_str for r in RidRepo(session).list(review)] == before

    # minutes render
    errors, md = svc.report(session, review)
    assert errors == [] and "SIN-SRS-R1" in md

    # close out: owner rejects each, its reviewer verifies, then finalize
    for r in RidRepo(session).list(review):
        svc.answer(session, review, r.rid_str, disposition=Disposition.REJECTED, reply="n/a")
    session.commit()
    for r in RidRepo(session).list(review):
        svc.verify(session, review, r.rid_str, reviewer=r.reviewer.display_name)
    session.commit()
    assert svc.finalize(session, review) == []
