"""Store stable Discord identities on ride reaction events.

Revision ID: c8d2e4f6a901
Revises: 43a03ddfa8a6
"""

from alembic import op
import sqlalchemy as sa

revision = "c8d2e4f6a901"
down_revision = "43a03ddfa8a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add IDs and backfill only unique, linked pickup-info username matches."""
    op.add_column("ride_reaction_events", sa.Column("discord_user_id", sa.String(), nullable=True))
    op.create_index("ix_ride_reaction_events_discord_user_id", "ride_reaction_events", ["discord_user_id"])
    op.execute(sa.text("""
        UPDATE ride_reaction_events
        SET discord_user_id = (
            SELECT MAX(locations.discord_user_id) FROM locations
            WHERE LOWER(locations.discord_username) = LOWER(ride_reaction_events.discord_username)
            HAVING COUNT(*) = 1 AND COUNT(locations.discord_user_id) = 1
        )
        WHERE discord_user_id IS NULL
    """))


def downgrade() -> None:
    """Remove reaction identity storage."""
    op.drop_index("ix_ride_reaction_events_discord_user_id", table_name="ride_reaction_events")
    op.drop_column("ride_reaction_events", "discord_user_id")
