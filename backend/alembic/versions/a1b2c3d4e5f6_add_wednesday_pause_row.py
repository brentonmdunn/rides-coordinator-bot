"""Add wednesday row to message_schedule_pauses.

Revision ID: a1b2c3d4e5f6
Revises: c7d8e9f0a1b2
Create Date: 2026-06-28

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO message_schedule_pauses (job_name, is_paused, resume_after_date) "
        "VALUES ('wednesday', 0, NULL)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM message_schedule_pauses WHERE job_name = 'wednesday'")
