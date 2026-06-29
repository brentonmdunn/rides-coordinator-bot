"""Add global_settings table and seed fellowship_season default.

Revision ID: 9d5ff18c05ad
Revises: 625822b2348c
Create Date: 2026-06-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d5ff18c05ad"
down_revision: str | None = "625822b2348c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "global_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        sa.text(
            "INSERT INTO global_settings (key, value) VALUES ('fellowship_season', 'friday') "
            "ON CONFLICT (key) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_table("global_settings")
