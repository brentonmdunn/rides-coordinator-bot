"""
Complete event synchronization, requests, driver offers, and assignments.

Revision ID: f2a3b4c5d607
Revises: d1e2f3a4b506
"""

import sqlalchemy as sa

from alembic import op

revision = "f2a3b4c5d607"
down_revision = "d1e2f3a4b506"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add durable workflow state without deleting legacy requests or audit records."""
    for column in (
        sa.Column("kind", sa.String(), nullable=False, server_default="rider"),
        sa.Column("state_changed_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("sync_error", sa.String(), nullable=True),
    ):
        op.add_column("ride_announcements", column)
    op.create_table(
        "ride_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("ride_events.id"), nullable=False),
        sa.Column("identity_key", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("discord_user_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("pickup", sa.Boolean(), nullable=False),
        sa.Column("return_preference", sa.String(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "identity_key"),
    )
    op.create_index("ix_ride_requests_event_id", "ride_requests", ["event_id"])
    op.create_table(
        "ride_driver_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("ride_events.id"), nullable=False),
        sa.Column("discord_user_id", sa.String(), nullable=False),
        sa.Column("discord_username", sa.String(), nullable=False),
        sa.Column("availability", sa.String(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("directions", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("return_preference", sa.String(), nullable=False, server_default="either"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "discord_user_id"),
    )
    op.create_index("ix_ride_driver_offers_event_id", "ride_driver_offers", ["event_id"])
    op.create_table(
        "ride_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("ride_events.id"), nullable=False),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("ride_requests.id"), nullable=False),
        sa.Column(
            "driver_offer_id", sa.Integer(), sa.ForeignKey("ride_driver_offers.id"), nullable=False
        ),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "request_id", "direction"),
    )
    op.create_index("ix_ride_assignments_event_id", "ride_assignments", ["event_id"])
    # Preserve pre-rollout signup state even when Discord is temporarily unreachable.
    # Mark the reconstructed preference for review until a complete snapshot refreshes it.
    op.execute(
        sa.text("""
        INSERT INTO ride_requests
            (event_id, identity_key, source, discord_user_id, name, active, pickup,
             return_preference, needs_review, updated_at)
        SELECT a.event_id, 'discord:' || s.discord_user_id, 'discord', s.discord_user_id,
               MAX(s.display_name), MAX(s.active), 1, 'unknown', 1, MAX(s.updated_at)
        FROM ride_signups s JOIN ride_announcements a ON a.message_id = s.message_id
        GROUP BY a.event_id, s.discord_user_id
    """)
    )


def downgrade() -> None:
    """Remove the workflow additions, retaining the earlier event/signup tables."""
    for table in ("ride_assignments", "ride_driver_offers", "ride_requests"):
        op.drop_index(f"ix_{table}_event_id", table_name=table)
        op.drop_table(table)
    with op.batch_alter_table("ride_announcements") as batch:
        for column in ("sync_error", "last_checked_at", "deleted_at", "state_changed_at", "kind"):
            batch.drop_column(column)
