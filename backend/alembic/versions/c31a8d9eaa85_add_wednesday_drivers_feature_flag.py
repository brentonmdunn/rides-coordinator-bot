"""Add ask_wednesday_drivers_job feature flag.

Revision ID: c31a8d9eaa85
Revises: 9d5ff18c05ad
Create Date: 2026-06-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c31a8d9eaa85"
down_revision: str | None = "9d5ff18c05ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (feature, enabled) "
            "VALUES ('ask_wednesday_drivers_job', 0) "
            "ON CONFLICT (feature) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM feature_flags WHERE feature = 'ask_wednesday_drivers_job'")
    )
