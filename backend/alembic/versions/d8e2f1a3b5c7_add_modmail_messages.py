"""add modmail_messages table

Revision ID: d8e2f1a3b5c7
Revises: c9f7a2b4e011
Create Date: 2026-04-26 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e2f1a3b5c7"
down_revision: str | None = "c9f7a2b4e011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "modmail_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "sender_type",
            sa.Enum("user", "admin", "bot", name="modmailsendertype"),
            nullable=False,
        ),
        sa.Column("sender_id", sa.String(), nullable=False),
        sa.Column("sender_name", sa.String(), nullable=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("attachments_json", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_modmail_messages_user_id"),
        "modmail_messages",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_modmail_messages_created_at"),
        "modmail_messages",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_modmail_messages_created_at"), table_name="modmail_messages")
    op.drop_index(op.f("ix_modmail_messages_user_id"), table_name="modmail_messages")
    op.drop_table("modmail_messages")
