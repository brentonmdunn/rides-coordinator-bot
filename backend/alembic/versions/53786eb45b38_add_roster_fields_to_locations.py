"""
add roster fields to locations

Revision ID: 53786eb45b38
Revises: 8b2d3f0c5e21
Create Date: 2026-09-11 11:52:41.156041

"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "53786eb45b38"
down_revision: str | None = "8b2d3f0c5e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

# Hardcoded as frozen literals so this migration's behavior never changes even if the
# enums it mirrors do. Don't import shared.core.enums here.
_CLASS_YEARS: tuple[str, ...] = ("1st", "2nd", "3rd", "4th", "5th")
_CAMPUS_LIVING_LOCATIONS: tuple[str, ...] = (
    "Seventh",
    "ERC",
    "Marshall",
    "Sixth",
    "Muir",
    "Warren",
    "Rita",
    "Eighth",
    "Pangea",
    "Pepper Canyon East",
    "Pepper Canyon West",
    "Revelle",
)


def upgrade() -> None:
    """Add roster columns, drop `driver`, and normalize existing data."""
    with op.batch_alter_table("locations") as batch_op:
        batch_op.add_column(sa.Column("discord_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            "ix_locations_discord_user_id", ["discord_user_id"], unique=True
        )
        batch_op.drop_column("driver")

    connection = op.get_bind()

    year_by_lower = {value.lower(): value for value in _CLASS_YEARS}
    location_by_lower = {value.lower(): value for value in _CAMPUS_LIVING_LOCATIONS}

    rows = connection.execute(
        sa.text("SELECT id, year, location, discord_username FROM locations")
    ).fetchall()

    for row in rows:
        row_id, year, location, discord_username = row

        normalized_year = year
        if year is not None:
            match = year_by_lower.get(year.strip().lower())
            if match is not None:
                normalized_year = match
            else:
                logger.warning(
                    "locations.id=%s has unmatched year %r; leaving as-is", row_id, year
                )

        normalized_location = location
        if location is not None:
            match = location_by_lower.get(location.strip().lower())
            if match is not None:
                normalized_location = match
            else:
                logger.warning(
                    "locations.id=%s has unmatched location %r; leaving as-is",
                    row_id,
                    location,
                )

        normalized_username = discord_username
        if discord_username is not None:
            normalized_username = discord_username.strip().lstrip("@").lower()

        connection.execute(
            sa.text(
                "UPDATE locations SET year = :year, location = :location, "
                "discord_username = :discord_username WHERE id = :id"
            ),
            {
                "year": normalized_year,
                "location": normalized_location,
                "discord_username": normalized_username,
                "id": row_id,
            },
        )

    op.execute(
        sa.text("DELETE FROM feature_flags WHERE feature = 'rides_locations_sync_job'")
    )


def downgrade() -> None:
    """Drop the roster columns and add `driver` back."""
    with op.batch_alter_table("locations") as batch_op:
        batch_op.add_column(sa.Column("driver", sa.String(), nullable=True))
        batch_op.drop_index("ix_locations_discord_user_id")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("discord_user_id")
