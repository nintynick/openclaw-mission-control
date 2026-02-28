"""Phase 6: Gap fixes — add risk_level and conflicts_detected to proposals.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2025-05-01 00:00:06.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c["name"] for c in inspector.get_columns("proposals")}

    if "risk_level" not in existing_columns:
        op.add_column("proposals", sa.Column("risk_level", sa.String(), nullable=True))
        op.create_index("ix_proposals_risk_level", "proposals", ["risk_level"])

    if "conflicts_detected" not in existing_columns:
        op.add_column("proposals", sa.Column("conflicts_detected", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_proposals_risk_level", table_name="proposals")
    op.drop_column("proposals", "risk_level")
    op.drop_column("proposals", "conflicts_detected")
