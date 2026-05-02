"""Add self-auth tables: Discord identity fields on user_accounts and auth_sessions.

Revision ID: a9f3e2b1c8d7
Revises: cf1c49fb43ca
Create Date: 2026-05-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9f3e2b1c8d7"
down_revision: str | None = "cf1c49fb43ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Discord identity columns to user_accounts and create auth_sessions."""
    # Make email nullable and add Discord linkage + invite metadata columns.
    # SQLite requires batch mode to alter existing columns.
    with op.batch_alter_table("user_accounts") as batch_op:
        batch_op.alter_column("email", nullable=True)
        batch_op.add_column(sa.Column("discord_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("discord_username", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("invited_by", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("invited_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_user_accounts_discord_user_id", ["discord_user_id"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id_hash", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("csrf_token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_session_id_hash", "auth_sessions", ["session_id_hash"], unique=True)
    op.create_index("ix_auth_sessions_email", "auth_sessions", ["email"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    """Remove auth_sessions and Discord identity columns from user_accounts."""
    op.drop_table("auth_sessions")

    with op.batch_alter_table("user_accounts") as batch_op:
        batch_op.drop_index("ix_user_accounts_discord_user_id")
        batch_op.drop_column("invited_at")
        batch_op.drop_column("invited_by")
        batch_op.drop_column("discord_username")
        batch_op.drop_column("discord_user_id")
        batch_op.alter_column("email", nullable=False)
