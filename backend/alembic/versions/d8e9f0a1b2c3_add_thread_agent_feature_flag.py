"""add thread_agent feature flag

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("INSERT INTO feature_flags (feature, enabled) VALUES ('thread_agent', 0)")
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM feature_flags WHERE feature = 'thread_agent'"))
