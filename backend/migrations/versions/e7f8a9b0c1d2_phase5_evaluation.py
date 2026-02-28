"""Phase 5: Evaluation + completion — evaluations, evaluation_scores, incentive_signals tables.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2025-05-01 00:00:05.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "evaluations" not in existing_tables:
        op.create_table(
            "evaluations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("zone_id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=True),
            sa.Column("proposal_id", sa.Uuid(), nullable=True),
            sa.Column("executor_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(), server_default="pending", nullable=False),
            sa.Column("aggregate_result", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["zone_id"], ["trust_zones.id"]),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
            sa.ForeignKeyConstraint(["executor_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_evaluations_zone_id", "evaluations", ["zone_id"])
        op.create_index("ix_evaluations_organization_id", "evaluations", ["organization_id"])
        op.create_index("ix_evaluations_task_id", "evaluations", ["task_id"])
        op.create_index("ix_evaluations_proposal_id", "evaluations", ["proposal_id"])
        op.create_index("ix_evaluations_executor_id", "evaluations", ["executor_id"])
        op.create_index("ix_evaluations_status", "evaluations", ["status"])

    if "evaluation_scores" not in existing_tables:
        op.create_table(
            "evaluation_scores",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("evaluation_id", sa.Uuid(), nullable=False),
            sa.Column("evaluator_id", sa.Uuid(), nullable=False),
            sa.Column("criterion_name", sa.String(), nullable=False),
            sa.Column("criterion_weight", sa.Float(), server_default="1.0", nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("rationale", sa.String(), server_default="", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "evaluation_id", "evaluator_id", "criterion_name",
                name="uq_evaluation_score",
            ),
        )
        op.create_index("ix_evaluation_scores_evaluation_id", "evaluation_scores", ["evaluation_id"])
        op.create_index("ix_evaluation_scores_evaluator_id", "evaluation_scores", ["evaluator_id"])

    if "incentive_signals" not in existing_tables:
        op.create_table(
            "incentive_signals",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("evaluation_id", sa.Uuid(), nullable=False),
            sa.Column("target_id", sa.Uuid(), nullable=False),
            sa.Column("signal_type", sa.String(), nullable=False),
            sa.Column("magnitude", sa.Float(), server_default="1.0", nullable=False),
            sa.Column("reason", sa.String(), server_default="", nullable=False),
            sa.Column("applied", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_incentive_signals_evaluation_id", "incentive_signals", ["evaluation_id"])
        op.create_index("ix_incentive_signals_target_id", "incentive_signals", ["target_id"])
        op.create_index("ix_incentive_signals_signal_type", "incentive_signals", ["signal_type"])


def downgrade() -> None:
    op.drop_table("incentive_signals")
    op.drop_table("evaluation_scores")
    op.drop_table("evaluations")
