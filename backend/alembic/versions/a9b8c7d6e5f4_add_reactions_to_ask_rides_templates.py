"""Add reactions column to ask_rides_message_templates.

Revision ID: a9b8c7d6e5f4
Revises: 44f6b5bdaeef
Create Date: 2026-07-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = '44f6b5bdaeef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable JSON-encoded reactions column (NULL = use default emojis)."""
    op.add_column(
        'ask_rides_message_templates',
        sa.Column('reactions', sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Drop the reactions column."""
    op.drop_column('ask_rides_message_templates', 'reactions')
