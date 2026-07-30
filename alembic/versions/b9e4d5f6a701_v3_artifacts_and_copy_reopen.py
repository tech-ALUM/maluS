"""v3: review_artifacts table + reviewer_copies.reopen_requested_at

Revision ID: b9e4d5f6a701
Revises: a7c31e90d412
Create Date: 2026-07-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # maluS: str columns use sqlmodel.sql.sqltypes.AutoString


# revision identifiers, used by Alembic.
revision: str = 'b9e4d5f6a701'
down_revision: Union[str, Sequence[str], None] = 'a7c31e90d412'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Both objects are created defensively: maluS has two schema authorities —
    Alembic here, and ``malus.db.session.create_all`` which every ``malus
    serve`` / CLI invocation runs as a bootstrap. An app that booted before
    this revision was applied already owns the table and the column without
    any revision stamp, and an unconditional ``create_table`` then fails with
    "table review_artifacts already exists", taking the container down on the
    next deploy (2026-07-30 incident). Skipping what exists lets the two
    authorities converge instead of colliding.
    """
    inspector = sa.inspect(op.get_bind())
    if 'review_artifacts' not in inspector.get_table_names():
        op.create_table(
            'review_artifacts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('review_id', sa.Integer(), nullable=False),
            sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('content', sa.LargeBinary(), nullable=False),
            sa.Column('sha256', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('created', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['review_id'], ['reviews.id']),
            sa.PrimaryKeyConstraint('id'),
        )
    columns = {c['name'] for c in inspector.get_columns('reviewer_copies')}
    if 'reopen_requested_at' not in columns:
        op.add_column(
            'reviewer_copies',
            sa.Column('reopen_requested_at', sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reviewer_copies', 'reopen_requested_at')
    op.drop_table('review_artifacts')
