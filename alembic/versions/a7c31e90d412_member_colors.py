"""member colors (v2.1): users.color + review_members.color

Revision ID: a7c31e90d412
Revises: f1a2b3c4d5e6
Create Date: 2026-07-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # maluS: str columns use sqlmodel.sql.sqltypes.AutoString


# revision identifiers, used by Alembic.
revision: str = 'a7c31e90d412'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: nullable #rrggbb color on users (global default,
    admin-set) and review_members (per-review override, owner/admin-set)."""
    op.add_column('users', sa.Column('color', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column(
        'review_members', sa.Column('color', sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('review_members', 'color')
    op.drop_column('users', 'color')
