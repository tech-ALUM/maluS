"""Import a v0 file-based review directory into the database.

This is the only surviving file-reading path (ADR 0001 removed git as
store/transport). It reads a ``<review>/`` laid out by the v0 CLI —
``baseline.md``, ``rtd.yaml`` (meta, possibly with rids), ``reviewers/<name>.md``
— and seeds an equivalent review in the DB via the service layer. No git.
"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from malus.db.models import Review
from malus.models import RTD
from malus.services.core import add_reviewer_copy, create_review, freeze_baseline
from malus.services.sync import sync_rtd_to_review

BASELINE_NAME = "baseline.md"
RTD_NAME = "rtd.yaml"
REVIEWERS_DIR = "reviewers"


def import_review_dir(session: Session, review_dir: Path | str) -> Review:
    """Seed a DB review from a v0 review directory; returns the new Review."""
    review_dir = Path(review_dir)
    rtd = RTD.from_yaml((review_dir / RTD_NAME).read_text(encoding="utf-8"))
    meta = rtd.meta

    review = create_review(
        session,
        review_id=meta.review_id,
        document_name=meta.document,
        owner=meta.owner or "unknown",
        reviewers=meta.reviewers,
        rid_prefix=meta.rid_prefix,
        created=meta.created,
    )
    freeze_baseline(session, review, (review_dir / BASELINE_NAME).read_text(encoding="utf-8"))

    reviewers_dir = review_dir / REVIEWERS_DIR
    if reviewers_dir.is_dir():
        for path in sorted(reviewers_dir.glob("*.md")):
            add_reviewer_copy(session, review, path.stem, path.read_text(encoding="utf-8"))

    if rtd.rids:  # a v0 rtd.yaml may already carry harvested/dispositioned RIDs
        sync_rtd_to_review(session, review, rtd)

    return review
