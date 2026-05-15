"""
Add ride_reaction_events table.

Revision ID: b2c3d4e5f6a1
Revises: a9f3e2b1c8d7
Create Date: 2026-05-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: str | None = "a9f3e2b1c8d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ride_reaction_events table."""
    op.create_table(
        "ride_reaction_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("discord_username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("emoji", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ride_date", sa.Date(), nullable=True),
        sa.Column("ride_type", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ride_reaction_events_message_id"),
        "ride_reaction_events",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ride_reaction_events_occurred_at"),
        "ride_reaction_events",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop ride_reaction_events table."""
    op.drop_index(op.f("ix_ride_reaction_events_occurred_at"), table_name="ride_reaction_events")
    op.drop_index(op.f("ix_ride_reaction_events_message_id"), table_name="ride_reaction_events")
    op.drop_table("ride_reaction_events")
