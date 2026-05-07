"""add use_cache feature flag

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (feature, enabled) VALUES ('use_cache', 1)"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM feature_flags WHERE feature = 'use_cache'")
    )
