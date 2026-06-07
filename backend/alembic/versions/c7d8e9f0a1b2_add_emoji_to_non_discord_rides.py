"""
Add emoji column to non_discord_rides.

Revision ID: c7d8e9f0a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-06-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b2c3d4e5f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable emoji column to non_discord_rides."""
    op.add_column("non_discord_rides", sa.Column("emoji", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop emoji column from non_discord_rides."""
    op.drop_column("non_discord_rides", "emoji")
