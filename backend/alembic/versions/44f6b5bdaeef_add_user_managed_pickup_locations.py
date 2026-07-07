"""
add user managed pickup locations

Revision ID: 44f6b5bdaeef
Revises: 94e82225a623
Create Date: 2026-07-06 23:49:24.851673

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44f6b5bdaeef"
down_revision: str | None = "94e82225a623"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PICKUP_ADJUSTMENT_KEY = "ride_grouping_pickup_adjustment"

# Frozen seed data — copied from the hardcoded constants this migration replaces
# (bot/utils/constants.py MAP_LOCATIONS, bot/utils/locations.py LOCATIONS_MATRIX,
# bot/services/group_rides_service.py living_to_pickup). Deliberately literal so
# the migration never depends on live application code.
SEED_LOCATIONS = [
    # (id, name, latitude, longitude, minutes_from_start, minutes_to_end)
    (1, "Sixth loop", 32.881096, -117.242020, None, None),
    (2, "Seventh mail room", 32.888203, -117.242347, None, 20),
    (3, "Marshall uppers", 32.883187, -117.241281, None, None),
    (4, "ERC across from bamboo", 32.885294, -117.242357, None, None),
    (5, "Muir tennis courts", 32.878133, -117.243361, None, None),
    (6, "Eighth basketball courts", 32.873411, -117.242997, 10, None),
    (7, "Innovation", 32.879118, -117.231663, 10, 20),
    (8, "Rita", 32.873065, -117.235532, 10, None),
    (9, "Warren Equality Ln", 32.883587, -117.233687, None, None),
    (10, "Warren Justice Ln", 32.883156, -117.232222, None, None),
    (11, "Geisel Loop", 32.881598, -117.238614, None, None),
    (12, "Pepper Canyon Loop", 32.878366, -117.234230, 10, 20),
]

SEED_EDGES = [
    # (location_a_id, location_b_id, minutes) — deduplicated symmetric pairs
    (1, 3, 1),  # Sixth loop <-> Marshall uppers
    (1, 5, 1),  # Sixth loop <-> Muir tennis courts
    (2, 4, 1),  # Seventh mail room <-> ERC across from bamboo
    (2, 9, 4),  # Seventh mail room <-> Warren Equality Ln
    (2, 11, 5),  # Seventh mail room <-> Geisel Loop
    (3, 4, 1),  # Marshall uppers <-> ERC across from bamboo
    (5, 6, 2),  # Muir tennis courts <-> Eighth basketball courts
    (6, 8, 4),  # Eighth basketball courts <-> Rita
    (6, 12, 5),  # Eighth basketball courts <-> Pepper Canyon Loop
    (7, 8, 7),  # Innovation <-> Rita
    (7, 9, 1),  # Innovation <-> Warren Equality Ln
    (8, 9, 8),  # Rita <-> Warren Equality Ln
    (9, 11, 3),  # Warren Equality Ln <-> Geisel Loop
    (9, 12, 6),  # Warren Equality Ln <-> Pepper Canyon Loop
]

SEED_LIVING_MAPPINGS = [
    # (living_location, pickup_location_id) — CampusLivingLocations values.
    # Pangea has no mapping today (was absent from living_to_pickup); omitted.
    ("Sixth", 1),
    ("Seventh", 2),
    ("Marshall", 3),
    ("ERC", 4),
    ("Muir", 5),
    ("Eighth", 6),
    ("Revelle", 6),
    ("Pepper Canyon East", 7),
    ("Pepper Canyon West", 7),
    ("Rita", 8),
    ("Warren", 9),
]


def upgrade() -> None:
    """Upgrade schema."""
    locations_table = op.create_table(
        "pickup_locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("minutes_from_start", sa.Integer(), nullable=True),
        sa.Column("minutes_to_end", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_seeded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_pickup_locations_id"), "pickup_locations", ["id"], unique=False)

    edges_table = op.create_table(
        "pickup_location_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("location_a_id", sa.Integer(), nullable=False),
        sa.Column("location_b_id", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("minutes > 0"),
        sa.ForeignKeyConstraint(["location_a_id"], ["pickup_locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_b_id"], ["pickup_locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_a_id", "location_b_id"),
    )
    op.create_index(
        op.f("ix_pickup_location_edges_id"), "pickup_location_edges", ["id"], unique=False
    )

    mappings_table = op.create_table(
        "living_location_pickups",
        sa.Column("living_location", sa.String(), nullable=False),
        sa.Column("pickup_location_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["pickup_location_id"], ["pickup_locations.id"]),
        sa.PrimaryKeyConstraint("living_location"),
    )

    op.bulk_insert(
        locations_table,
        [
            {
                "id": loc_id,
                "name": name,
                "latitude": lat,
                "longitude": lng,
                "minutes_from_start": from_start,
                "minutes_to_end": to_end,
                "is_active": True,
                "is_seeded": True,
            }
            for loc_id, name, lat, lng, from_start, to_end in SEED_LOCATIONS
        ],
    )
    op.bulk_insert(
        edges_table,
        [
            {"location_a_id": a, "location_b_id": b, "minutes": minutes}
            for a, b, minutes in SEED_EDGES
        ],
    )
    op.bulk_insert(
        mappings_table,
        [
            {"living_location": living, "pickup_location_id": pickup_id}
            for living, pickup_id in SEED_LIVING_MAPPINGS
        ],
    )

    op.execute(
        sa.text(
            "INSERT INTO global_settings (key, value) "
            f"SELECT '{PICKUP_ADJUSTMENT_KEY}', '1' "
            f"WHERE NOT EXISTS (SELECT 1 FROM global_settings WHERE key = '{PICKUP_ADJUSTMENT_KEY}')"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text(f"DELETE FROM global_settings WHERE key = '{PICKUP_ADJUSTMENT_KEY}'"))
    op.drop_table("living_location_pickups")
    op.drop_index(op.f("ix_pickup_location_edges_id"), table_name="pickup_location_edges")
    op.drop_table("pickup_location_edges")
    op.drop_index(op.f("ix_pickup_locations_id"), table_name="pickup_locations")
    op.drop_table("pickup_locations")
