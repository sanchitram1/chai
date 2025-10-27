"""add text field to licenses table

Revision ID: b1e2c3d4e5f6
Revises: 3de32bb99a71
Create Date: 2025-08-21 21:48:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import Text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1e2c3d4e5f6"
down_revision: str | None = "3de32bb99a71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add text field to licenses table to store license content."""
    op.add_column("licenses", sa.Column("text", Text, nullable=True))


def downgrade() -> None:
    """Remove text field from licenses table."""
    op.drop_column("licenses", "text")