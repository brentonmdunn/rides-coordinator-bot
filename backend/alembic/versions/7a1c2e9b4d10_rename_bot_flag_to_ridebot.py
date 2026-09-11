"""rename bot flag to ridebot

Revision ID: 7a1c2e9b4d10
Revises: a9b8c7d6e5f4
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a1c2e9b4d10"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM feature_flags WHERE feature = 'ridebot' "
            "AND EXISTS (SELECT 1 FROM feature_flags WHERE feature = 'bot')"
        )
    )
    op.execute(
        sa.text("UPDATE feature_flags SET feature = 'ridebot' WHERE feature = 'bot'")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM feature_flags WHERE feature = 'bot' "
            "AND EXISTS (SELECT 1 FROM feature_flags WHERE feature = 'ridebot')"
        )
    )
    op.execute(
        sa.text("UPDATE feature_flags SET feature = 'bot' WHERE feature = 'ridebot'")
    )
