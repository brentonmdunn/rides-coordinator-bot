"""
Remove unused schema for deferred ride coordination features.

Revision ID: a3b4c5d6e708
Revises: f2a3b4c5d607
"""

import sqlalchemy as sa

from alembic import op

revision = "a3b4c5d6e708"
down_revision = "f2a3b4c5d607"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove unused feature tables, refusing to discard any existing feature data."""
    connection = op.get_bind()
    for table in ("ride_assignments", "ride_driver_offers"):
        if connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}")):
            raise RuntimeError(
                f"{table} contains data; preserve it explicitly before removing deferred features"
            )
    for table in ("ride_assignments", "ride_driver_offers"):
        op.drop_index(f"ix_{table}_event_id", table_name=table)
        op.drop_table(table)


def downgrade() -> None:
    """Restore the earlier empty feature tables without changing rider state."""
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
