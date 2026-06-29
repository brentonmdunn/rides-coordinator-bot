"""Add wednesday row to message_schedule_pauses.

Revision ID: 625822b2348c
Revises: a1b2c3d4e5f6
Create Date: 2026-06-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "625822b2348c"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO message_schedule_pauses (job_name, is_paused, resume_after_date) "
            "VALUES ('wednesday', 0, NULL) "
            "ON CONFLICT (job_name) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM message_schedule_pauses WHERE job_name = 'wednesday'")
    )
