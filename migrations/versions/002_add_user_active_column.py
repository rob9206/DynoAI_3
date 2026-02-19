"""Add active column to users table

Revision ID: 002_user_active
Revises: 001_initial
Create Date: 2026-02-19

Adds a boolean `active` column (default True) so owners can
deactivate user accounts without deleting them.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_user_active"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add active column to users table."""
    op.add_column(
        "users",
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Whether the account is active",
        ),
    )


def downgrade() -> None:
    """Remove active column from users table."""
    op.drop_column("users", "active")
