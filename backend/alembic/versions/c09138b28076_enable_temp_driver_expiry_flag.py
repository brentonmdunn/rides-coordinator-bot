"""
enable temp driver expiry flag

Seed temp_driver_expiry_job as enabled. Grants aren't gated by this flag, so if it
started disabled (the default for newly seeded flags) temporary drivers would keep the
role past expiry until someone remembered to flip it. Local dev still disables every
*_job flag at startup.

Revision ID: c09138b28076
Revises: 239c8630731f
Create Date: 2026-09-18 23:36:46.930912

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c09138b28076"
down_revision: str | None = "239c8630731f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (feature, enabled) "
            "SELECT 'temp_driver_expiry_job', 1 "
            "WHERE NOT EXISTS (SELECT 1 FROM feature_flags WHERE feature = 'temp_driver_expiry_job')"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DELETE FROM feature_flags WHERE feature = 'temp_driver_expiry_job'"))
