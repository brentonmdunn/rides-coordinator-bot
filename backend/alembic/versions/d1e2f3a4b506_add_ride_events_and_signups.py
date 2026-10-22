"""Add database-owned ride events, announcement mappings, and current signups.

Revision ID: d1e2f3a4b506
Revises: c8d2e4f6a901
"""

import sqlalchemy as sa

from alembic import op

revision = "d1e2f3a4b506"
down_revision = "c8d2e4f6a901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tables without reinterpreting historical message text or dates."""
    op.create_table(
        "ride_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "message_type", "event_date"),
    )
    op.create_table(
        "ride_announcements",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("signup_emojis", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_reconciled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["ride_events.id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index("ix_ride_announcements_event_id", "ride_announcements", ["event_id"])
    op.create_table(
        "ride_signups",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("discord_user_id", sa.String(), nullable=False),
        sa.Column("emoji", sa.String(), nullable=False),
        sa.Column("discord_username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["ride_announcements.message_id"]),
        sa.PrimaryKeyConstraint("message_id", "discord_user_id", "emoji"),
    )


def downgrade() -> None:
    """Remove signup storage without modifying the legacy reaction audit log."""
    op.drop_table("ride_signups")
    op.drop_index("ix_ride_announcements_event_id", table_name="ride_announcements")
    op.drop_table("ride_announcements")
    op.drop_table("ride_events")
