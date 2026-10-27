"""Add daily account balances and FX provenance.

Revision ID: 20261027_0003
Revises: 20261027_0002
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0003"
down_revision: str | None = "20261027_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "daily_account_balances" not in inspector.get_table_names():
        op.create_table(
            "daily_account_balances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("position_date", sa.Date(), nullable=False),
            sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False),
            sa.Column("ledger_movements", sa.Numeric(18, 2), nullable=False),
            sa.Column("closing_balance", sa.Numeric(18, 2), nullable=False),
            sa.Column("source_currency", sa.String(3), nullable=False),
            sa.Column("source_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("fx_rate", sa.Numeric(20, 8), nullable=False),
            sa.Column("fx_rate_date", sa.Date(), nullable=False),
            sa.Column("base_currency", sa.String(3), nullable=False),
            sa.Column("base_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("legal_entity_id", sa.Integer(), sa.ForeignKey("legal_entities.id"), nullable=False),
            sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_accounts.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("bank_account_id", "position_date"),
            sa.CheckConstraint("fx_rate > 0", name="fx_rate_positive"),
        )


def downgrade() -> None:
    op.drop_table("daily_account_balances")
