"""Phase 3: Escalation engine — escalations and escalation_cosigners tables.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2025-05-01 00:00:03.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "escalations" not in existing_tables:
        op.create_table(
            "escalations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("escalation_type", sa.String(), nullable=False),
            sa.Column("source_proposal_id", sa.Uuid(), nullable=True),
            sa.Column("source_zone_id", sa.Uuid(), nullable=False),
            sa.Column("target_zone_id", sa.Uuid(), nullable=False),
            sa.Column("escalator_id", sa.Uuid(), nullable=False),
            sa.Column("reason", sa.String(), server_default="", nullable=False),
            sa.Column("status", sa.String(), server_default="pending", nullable=False),
            sa.Column("resulting_proposal_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["source_proposal_id"], ["proposals.id"]),
            sa.ForeignKeyConstraint(["source_zone_id"], ["trust_zones.id"]),
            sa.ForeignKeyConstraint(["target_zone_id"], ["trust_zones.id"]),
            sa.ForeignKeyConstraint(["escalator_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["resulting_proposal_id"], ["proposals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_escalations_organization_id", "escalations", ["organization_id"])
        op.create_index("ix_escalations_escalation_type", "escalations", ["escalation_type"])
        op.create_index("ix_escalations_source_proposal_id", "escalations", ["source_proposal_id"])
        op.create_index("ix_escalations_source_zone_id", "escalations", ["source_zone_id"])
        op.create_index("ix_escalations_target_zone_id", "escalations", ["target_zone_id"])
        op.create_index("ix_escalations_escalator_id", "escalations", ["escalator_id"])
        op.create_index("ix_escalations_status", "escalations", ["status"])
        op.create_index("ix_escalations_resulting_proposal_id", "escalations", ["resulting_proposal_id"])

    if "escalation_cosigners" not in existing_tables:
        op.create_table(
            "escalation_cosigners",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("escalation_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["escalation_id"], ["escalations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("escalation_id", "user_id", name="uq_escalation_cosigner"),
        )
        op.create_index("ix_escalation_cosigners_escalation_id", "escalation_cosigners", ["escalation_id"])
        op.create_index("ix_escalation_cosigners_user_id", "escalation_cosigners", ["user_id"])


def downgrade() -> None:
    op.drop_table("escalation_cosigners")
    op.drop_table("escalations")
