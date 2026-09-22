"""
add phone to locations

Revision ID: b3f7c2a91d4e
Revises: c09138b28076
Create Date: 2026-09-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f7c2a91d4e"
down_revision: str | None = "c09138b28076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable phone column to locations."""
    with op.batch_alter_table("locations") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop the phone column from locations."""
    with op.batch_alter_table("locations") as batch_op:
        batch_op.drop_column("phone")
