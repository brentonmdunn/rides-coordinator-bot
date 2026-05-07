"""
merge modmail and main heads

Revision ID: b7d962687c65
Revises: a9f3e2b1c8d7, d8e2f1a3b5c7
Create Date: 2026-05-06 21:50:55.071964

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b7d962687c65"
down_revision: str | None = ("a9f3e2b1c8d7", "d8e2f1a3b5c7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
