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
    """Upgrade schema."""
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
    op.add_column(
        'reviewer_copies',
        sa.Column('reopen_requested_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reviewer_copies', 'reopen_requested_at')
    op.drop_table('review_artifacts')
