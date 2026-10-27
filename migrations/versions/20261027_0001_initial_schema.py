"""Create Phase 2 liquidity schema.

Revision ID: 20261027_0001
Revises:
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20261027_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.models import entities  # noqa: F401
    from app.models.base import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.models import entities  # noqa: F401
    from app.models.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
