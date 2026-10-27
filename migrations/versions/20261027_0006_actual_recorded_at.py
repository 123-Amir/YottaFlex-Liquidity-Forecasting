"""Add actual cash-flow information timestamp.

Revision ID: 20261027_0006
Revises: 20261027_0005
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0006"
down_revision: str | None = "20261027_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("actual_cash_flows")}
    if "recorded_at" not in columns:
        op.add_column("actual_cash_flows", sa.Column("recorded_at", sa.Date(), nullable=True))
    op.execute("UPDATE actual_cash_flows SET recorded_at = occurred_on WHERE recorded_at IS NULL")
    op.alter_column("actual_cash_flows", "recorded_at", nullable=False)


def downgrade() -> None:
    op.drop_column("actual_cash_flows", "recorded_at")
