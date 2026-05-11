"""
merge use_cache and missing_tables heads

Revision ID: cf1c49fb43ca
Revises: a1b2c3d4e5f6, c6440e6c3d0e
Create Date: 2026-04-30 10:48:40.405244

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "cf1c49fb43ca"
down_revision: str | None = ("a1b2c3d4e5f6", "c6440e6c3d0e")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
