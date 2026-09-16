"""add weekly_events_announcements table and flag

Revision ID: c4e9a71d3b80
Revises: e3f7a1c9b2d4
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e9a71d3b80"
down_revision: str | None = "e3f7a1c9b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weekly_events_announcements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("posted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_weekly_events_announcements_id"),
        "weekly_events_announcements",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_weekly_events_announcements_message_id"),
        "weekly_events_announcements",
        ["message_id"],
        unique=True,
    )
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (feature, enabled) "
            "VALUES ('weekly_events_announcement_job', 0)"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM feature_flags WHERE feature = 'weekly_events_announcement_job'")
    )
    op.drop_index(
        op.f("ix_weekly_events_announcements_message_id"),
        table_name="weekly_events_announcements",
    )
    op.drop_index(
        op.f("ix_weekly_events_announcements_id"), table_name="weekly_events_announcements"
    )
    op.drop_table("weekly_events_announcements")
