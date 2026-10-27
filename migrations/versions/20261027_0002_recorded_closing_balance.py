"""Add recorded closing balance for reconciliation.

Revision ID: 20261027_0002
Revises: 20261027_0001
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0002"
down_revision: str | None = "20261027_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("bank_accounts")}
    if "recorded_closing_balance" not in columns:
        op.add_column(
            "bank_accounts",
            sa.Column("recorded_closing_balance", sa.Numeric(18, 2), nullable=True),
        )
    op.execute(
        "UPDATE bank_accounts SET recorded_closing_balance = opening_balance "
        "WHERE recorded_closing_balance IS NULL"
    )
    op.alter_column(
        "bank_accounts",
        "recorded_closing_balance",
        existing_type=sa.Numeric(18, 2),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "recorded_closing_balance")
