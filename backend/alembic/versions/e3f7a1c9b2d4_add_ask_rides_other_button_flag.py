"""add ask_rides_other_button feature flag

Revision ID: e3f7a1c9b2d4
Revises: 53786eb45b38
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f7a1c9b2d4"
down_revision: Union[str, None] = "53786eb45b38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (feature, enabled) "
            "SELECT 'ask_rides_other_button', 0 "
            "WHERE NOT EXISTS (SELECT 1 FROM feature_flags WHERE feature = 'ask_rides_other_button')"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM feature_flags WHERE feature = 'ask_rides_other_button'"))
