"""v3 startup backfill: pre-v3 rows stuck at ``draft``/``active`` (the removed
v2 value) with a frozen baseline are migrated to ``in_review`` once, at
startup. Idempotent; never touches ``closeout``/``finalized`` rows or drafts
without a baseline (``docs/plan/`` Step 1).

Mirrors ``tests/db/conftest.py``'s engine/session fixtures — the migration
runs directly against the DB session, no HTTP, no filesystem.
"""

from __future__ import annotations

from malus import services as svc
from malus.db.session import migrate_review_phases
from malus.repo import ReviewRepo


def test_backfill_draft_with_baseline_becomes_in_review(engine, session):
    review = svc.create_review(session, review_id="R-1", document_name="d.md", owner="own")
    svc.freeze_baseline(session, review, "# doc", by=None)
    ReviewRepo(session).set_status(review, "draft")  # simulate a pre-v3 row
    migrate_review_phases(session)
    assert review.status == "in_review"


def test_backfill_leaves_unfrozen_draft(engine, session):
    review = svc.create_review(session, review_id="R-2", document_name="d.md", owner="own")
    migrate_review_phases(session)
    assert review.status == "draft"


def test_backfill_active_with_baseline_becomes_in_review(engine, session):
    """A row stuck at the removed v2 status ``active`` (rather than ``draft``)
    with a frozen baseline is also backfilled — ``migrate_review_phases``
    treats ``draft``/``active`` the same, since both predate the v3 phase
    column."""
    review = svc.create_review(session, review_id="R-3", document_name="d.md", owner="own")
    svc.freeze_baseline(session, review, "# doc", by=None)
    ReviewRepo(session).set_status(review, "active")  # simulate a pre-v3 v2 row
    migrate_review_phases(session)
    assert review.status == "in_review"


def test_backfill_is_idempotent(engine, session):
    review = svc.create_review(session, review_id="R-4", document_name="d.md", owner="own")
    svc.freeze_baseline(session, review, "# doc", by=None)
    ReviewRepo(session).set_status(review, "draft")
    migrate_review_phases(session)
    migrate_review_phases(session)
    assert review.status == "in_review"


def test_backfill_leaves_closeout_and_finalized_untouched(engine, session):
    closeout_review = svc.create_review(
        session, review_id="R-5", document_name="d.md", owner="own"
    )
    svc.freeze_baseline(session, closeout_review, "# doc", by=None)
    ReviewRepo(session).set_status(closeout_review, "closeout")

    finalized_review = svc.create_review(
        session, review_id="R-6", document_name="d.md", owner="own"
    )
    svc.freeze_baseline(session, finalized_review, "# doc", by=None)
    ReviewRepo(session).set_status(finalized_review, "finalized")

    migrate_review_phases(session)

    assert closeout_review.status == "closeout"
    assert finalized_review.status == "finalized"
