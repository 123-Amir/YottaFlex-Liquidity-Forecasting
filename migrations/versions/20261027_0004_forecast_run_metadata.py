"""Add immutable forecast metadata and source summaries.

Revision ID: 20261027_0004
Revises: 20261027_0003
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0004"
down_revision: str | None = "20261027_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("forecast_runs")}
    if "information_cutoff" not in columns:
        op.add_column("forecast_runs", sa.Column("information_cutoff", sa.Date(), nullable=True))
    if "assumptions_snapshot" not in columns:
        op.add_column("forecast_runs", sa.Column("assumptions_snapshot", sa.Text(), nullable=True))
    if "source_reference" not in columns:
        op.add_column("forecast_runs", sa.Column("source_reference", sa.String(128), nullable=True))
    op.execute(
        "UPDATE forecast_runs SET information_cutoff = simulation_date, "
        "assumptions_snapshot = 'Existing baseline run; assumptions recorded before Phase 5', "
        "source_reference = 'legacy-phase4' "
        "WHERE information_cutoff IS NULL"
    )
    for column in ("information_cutoff", "assumptions_snapshot", "source_reference"):
        op.alter_column("forecast_runs", column, nullable=False)
    if "forecast_run_source_summaries" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "forecast_run_source_summaries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_kind", sa.String(32), nullable=False),
            sa.Column("record_count", sa.Integer(), nullable=False),
            sa.Column("source_checksum", sa.String(64), nullable=False),
            sa.Column("source_version", sa.String(64), nullable=False),
            sa.Column("forecast_run_id", sa.Integer(), sa.ForeignKey("forecast_runs.id"), nullable=False),
            sa.UniqueConstraint("forecast_run_id", "source_kind"),
        )


def downgrade() -> None:
    op.drop_table("forecast_run_source_summaries")
    op.drop_column("forecast_runs", "source_reference")
    op.drop_column("forecast_runs", "assumptions_snapshot")
    op.drop_column("forecast_runs", "information_cutoff")
