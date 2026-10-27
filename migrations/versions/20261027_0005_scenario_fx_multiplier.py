"""Add scenario FX multiplier.

Revision ID: 20261027_0005
Revises: 20261027_0004
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0005"
down_revision: str | None = "20261027_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("scenario_cash_flow_adjustments")
    }
    if "fx_multiplier" not in columns:
        op.add_column(
            "scenario_cash_flow_adjustments",
            sa.Column("fx_multiplier", sa.Numeric(8, 4), nullable=False, server_default="1.0000"),
        )
    op.execute(
        "UPDATE scenario_cash_flow_adjustments AS adjustment "
        "SET fx_multiplier = 0.9500 "
        "FROM liquidity_scenarios AS scenario "
        "WHERE adjustment.scenario_id = scenario.id "
        "AND scenario.scenario_code = 'STRESS'"
    )
    op.alter_column("scenario_cash_flow_adjustments", "fx_multiplier", server_default=None)


def downgrade() -> None:
    op.drop_column("scenario_cash_flow_adjustments", "fx_multiplier")
