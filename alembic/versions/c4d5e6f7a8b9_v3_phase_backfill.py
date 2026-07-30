"""v3 phase backfill: draft|active -> in_review for frozen reviews

Revision ID: c4d5e6f7a8b9
Revises: b9e4d5f6a701
Create Date: 2026-07-30 16:00:00.000000

This is the DATA half of the v3 lifecycle migration. It used to live in Python
as ``malus.db.session.migrate_review_phases``, re-run on every process start
and invisible to Alembic — one of the two schema authorities whose drift took
the server down on 2026-07-30 (v3.1 ``docs/plan/v3.1/05-one-schema-authority.md``).

It is a separate revision rather than an edit to ``b9e4d5f6a701`` because that
revision is already applied in production: a backfill folded into it would
never run there.

Built from SQLAlchemy Core constructs, not literal SQL, so the boolean test
renders correctly on both supported dialects (``IS 1`` on SQLite, ``IS true``
on PostgreSQL). It only ever promotes a status — no row is deleted, no column
is dropped, nothing is rewritten.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b9e4d5f6a701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def backfill_statement() -> sa.sql.Update:
    """The backfill as a Core statement (also compiled by the tests, which
    assert it is portable across SQLite and PostgreSQL).

    Pre-v3 rows are stuck at ``draft`` (there was no phase column) or at the
    removed v2 value ``active``. A review whose baseline is already frozen
    belongs at ``in_review``; one without a baseline is a genuine draft and is
    left alone; ``closeout``/``finalized`` are never touched.
    """
    reviews = sa.table(
        "reviews", sa.column("id", sa.Integer), sa.column("status", sa.String)
    )
    documents = sa.table(
        "documents", sa.column("id", sa.Integer), sa.column("review_id", sa.Integer)
    )
    versions = sa.table(
        "document_versions",
        sa.column("document_id", sa.Integer),
        sa.column("is_baseline", sa.Boolean),
    )
    frozen = (
        sa.select(documents.c.review_id)
        .select_from(documents.join(versions, versions.c.document_id == documents.c.id))
        .where(versions.c.is_baseline.is_(True))
    )
    return (
        reviews.update()
        .where(reviews.c.status.in_(("draft", "active")))
        .where(reviews.c.id.in_(frozen))
        .values(status="in_review")
    )


def upgrade() -> None:
    """Promote frozen pre-v3 reviews to ``in_review``. Idempotent: a second run
    matches nothing, because ``freeze_baseline`` is the only writer of
    ``in_review`` and no service ever writes ``draft`` back."""
    op.execute(backfill_statement())


def downgrade() -> None:
    """Deliberately a no-op. This revision carries no schema change, and the
    pre-migration status of a promoted review (``draft`` vs the removed v2
    ``active``) is not recoverable — inventing one would be data loss. Reviews
    stay at ``in_review``, which is a valid v3 phase."""
