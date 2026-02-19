"""Add message_schedule_pauses table.

Revision ID: f1a2b3c4d5e6
Revises: 11c485f67e95
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = '11c485f67e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create message_schedule_pauses table."""
    op.create_table(
        'message_schedule_pauses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_name', sa.String(), nullable=False),
        sa.Column('is_paused', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('resume_after_date', sa.Date(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_name'),
    )
    op.create_index(op.f('ix_message_schedule_pauses_id'), 'message_schedule_pauses', ['id'], unique=False)

    # Seed default rows for all 3 job types
    op.execute(
        "INSERT INTO message_schedule_pauses (job_name, is_paused, resume_after_date) "
        "VALUES ('friday', 0, NULL), ('sunday', 0, NULL), ('sunday_class', 0, NULL)"
    )


def downgrade() -> None:
    """Drop message_schedule_pauses table."""
    op.drop_index(op.f('ix_message_schedule_pauses_id'), table_name='message_schedule_pauses')
    op.drop_table('message_schedule_pauses')
