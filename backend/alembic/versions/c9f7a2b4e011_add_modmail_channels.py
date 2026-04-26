"""Add modmail_channels table.

Revision ID: c9f7a2b4e011
Revises: f1a2b3c4d5e6
Create Date: 2026-04-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f7a2b4e011"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create modmail_channels table."""
    op.create_table(
        "modmail_channels",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("channel_id"),
    )
    op.create_index(
        op.f("ix_modmail_channels_channel_id"),
        "modmail_channels",
        ["channel_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop modmail_channels table."""
    op.drop_index(
        op.f("ix_modmail_channels_channel_id"), table_name="modmail_channels",
    )
    op.drop_table("modmail_channels")
