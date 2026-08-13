"""the reviewer's rework request becomes three columns on rids

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-13 18:40:00.000000

Until v3.2 a "request changes" left exactly one trace the machine could read:
the string ``[changes requested by <reviewer>: <reason>]`` appended to
``rids.reply``. The closeout queue decided its *rework* bucket by testing that
substring, and the owner met the reviewer's demand mixed into the same field
they write their own answers in.

This revision gives it columns. The note keeps being appended to ``reply`` —
``report.md``, the PDF and the timeline read it, and rewriting those belongs to
another change — but the *logic* now reads ``rework_at``.

Idempotent per the project convention (``CLAUDE.md``, revision
``b9e4d5f6a701``): every column is inspected before it is added, so a database
that already has them is left alone. The backfill is a set-based Core statement
built from the same literal marker the domain writes, never the ORM.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The marker written by malus.lifecycle.request_changes_rid. Kept as a module
# constant so the backfill and its tests cannot drift from each other.
MARKER = "[changes requested by "


def _rids() -> sa.Table:
    return sa.table(
        "rids",
        sa.column("id", sa.Integer),
        sa.column("status", sa.String),
        sa.column("reply", sa.String),
        sa.column("rework_reason", sa.String),
        sa.column("rework_at", sa.DateTime),
    )


def backfill_statement() -> sa.sql.Update:
    """Mark every finding whose reply carries the rework marker.

    Only ``closed`` rows are touched: that is the only status the rework bucket
    ever consults, and a finding that moved on has a marker in its history but
    no pending request. ``rework_reason`` is left NULL and the reply keeps the
    full text — parsing a free-text field to recover a reason would invent data
    where the original is right there, and the reader falls back to it.
    ``rework_by_id`` is likewise left NULL: the reviewer's name in the marker is
    a display name, and mapping it back to a user id is a guess.
    """
    rids = _rids()
    return (
        rids.update()
        .where(rids.c.status == "closed")
        .where(rids.c.reply.is_not(None))
        .where(rids.c.reply.contains(MARKER))
        .where(rids.c.rework_at.is_(None))
        .values(rework_at=sa.func.current_timestamp())
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("rids")}
    missing = {"rework_reason", "rework_by_id", "rework_at"} - columns

    if missing:
        # Batch mode, because one of the three carries a foreign key and SQLite
        # has no ALTER for constraints — Alembic's copy-and-move is the
        # documented way, and on PostgreSQL it degrades to plain ALTERs. All
        # three go in one batch so the table is rewritten once, not three times.
        with op.batch_alter_table("rids") as batch_op:
            if "rework_reason" in missing:
                batch_op.add_column(sa.Column("rework_reason", sa.String(), nullable=True))
            if "rework_by_id" in missing:
                batch_op.add_column(
                    sa.Column(
                        "rework_by_id",
                        sa.Integer(),
                        sa.ForeignKey("users.id", name="fk_rids_rework_by_id_users"),
                        nullable=True,
                    )
                )
            if "rework_at" in missing:
                batch_op.add_column(sa.Column("rework_at", sa.DateTime(), nullable=True))

    op.execute(backfill_statement())


def downgrade() -> None:
    """Drop the three columns. The rework request survives in ``reply`` and in
    the audit log, so nothing is lost that was not already recorded twice.

    Batch mode again, and for a sharper reason than the upgrade's: a plain
    ``DROP COLUMN`` on SQLite leaves the foreign key definition behind and the
    table stops opening at all — *unknown column "rework_by_id" in foreign key
    definition*. The copy-and-move rebuilds the table without it.
    """
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("rids")}
    present = [n for n in ("rework_at", "rework_by_id", "rework_reason") if n in columns]
    if not present:
        return
    with op.batch_alter_table("rids") as batch_op:
        for name in present:
            batch_op.drop_column(name)
