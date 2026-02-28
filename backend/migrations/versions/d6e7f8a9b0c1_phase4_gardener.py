"""Phase 4: Gardener intelligence — gardener_feedback table.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2025-05-01 00:00:04.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "gardener_feedback" not in existing_tables:
        op.create_table(
            "gardener_feedback",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("proposal_id", sa.Uuid(), nullable=False),
            sa.Column("reviewer_id", sa.Uuid(), nullable=False),
            sa.Column("selected_by", sa.String(), nullable=False),
            sa.Column("reviewed_in_time", sa.Boolean(), nullable=True),
            sa.Column("decision_overturned", sa.Boolean(), nullable=True),
            sa.Column("work_outcome", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_gardener_feedback_proposal_id", "gardener_feedback", ["proposal_id"])
        op.create_index("ix_gardener_feedback_reviewer_id", "gardener_feedback", ["reviewer_id"])
        op.create_index("ix_gardener_feedback_selected_by", "gardener_feedback", ["selected_by"])


def downgrade() -> None:
    op.drop_table("gardener_feedback")
