"""add stonesbot feature flag

Revision ID: 8b2d3f0c5e21
Revises: 7a1c2e9b4d10
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b2d3f0c5e21"
down_revision: Union[str, None] = "7a1c2e9b4d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (feature, enabled) "
            "SELECT 'stonesbot', COALESCE((SELECT enabled FROM feature_flags WHERE feature = 'ridebot'), 0) "
            "WHERE NOT EXISTS (SELECT 1 FROM feature_flags WHERE feature = 'stonesbot')"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM feature_flags WHERE feature = 'stonesbot'"))
