"""Add local payment archiving for the operational payments list.

Revision ID: 9b2e5c8d1f4a
Revises: 7e1c3a9d4b6f
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9b2e5c8d1f4a"
down_revision: str | None = "7e1c3a9d4b6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_payments_archived_at", "payments", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_archived_at", table_name="payments")
    op.drop_column("payments", "archived_at")
