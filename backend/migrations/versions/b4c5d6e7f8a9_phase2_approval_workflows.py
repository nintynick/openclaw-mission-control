"""Phase 2: Proposals and approval requests tables.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-02-26 00:00:01.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("proposals"):
        op.create_table(
            "proposals",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("zone_id", sa.Uuid(), nullable=False),
            sa.Column("proposer_id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False, server_default=""),
            sa.Column("proposal_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending_review"),
            sa.Column("decision_model_override", sa.JSON(), nullable=True),
            sa.Column("legacy_approval_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["zone_id"], ["trust_zones.id"]),
            sa.ForeignKeyConstraint(["proposer_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["legacy_approval_id"], ["approvals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_proposals_organization_id"), "proposals", ["organization_id"])
        op.create_index(op.f("ix_proposals_zone_id"), "proposals", ["zone_id"])
        op.create_index(op.f("ix_proposals_proposer_id"), "proposals", ["proposer_id"])
        op.create_index(op.f("ix_proposals_proposal_type"), "proposals", ["proposal_type"])
        op.create_index(op.f("ix_proposals_status"), "proposals", ["status"])
        op.create_index(op.f("ix_proposals_legacy_approval_id"), "proposals", ["legacy_approval_id"])

    if not inspector.has_table("approval_requests"):
        op.create_table(
            "approval_requests",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("proposal_id", sa.Uuid(), nullable=False),
            sa.Column("reviewer_id", sa.Uuid(), nullable=False),
            sa.Column("reviewer_type", sa.String(), nullable=False, server_default="human"),
            sa.Column("selection_reason", sa.String(), nullable=False, server_default=""),
            sa.Column("decision", sa.String(), nullable=True),
            sa.Column("rationale", sa.String(), nullable=False, server_default=""),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("deadline", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_approval_requests_proposal_id"), "approval_requests", ["proposal_id"])
        op.create_index(op.f("ix_approval_requests_reviewer_id"), "approval_requests", ["reviewer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("approval_requests"):
        op.drop_index(op.f("ix_approval_requests_reviewer_id"), table_name="approval_requests")
        op.drop_index(op.f("ix_approval_requests_proposal_id"), table_name="approval_requests")
        op.drop_table("approval_requests")

    if inspector.has_table("proposals"):
        op.drop_index(op.f("ix_proposals_legacy_approval_id"), table_name="proposals")
        op.drop_index(op.f("ix_proposals_status"), table_name="proposals")
        op.drop_index(op.f("ix_proposals_proposal_type"), table_name="proposals")
        op.drop_index(op.f("ix_proposals_proposer_id"), table_name="proposals")
        op.drop_index(op.f("ix_proposals_zone_id"), table_name="proposals")
        op.drop_index(op.f("ix_proposals_organization_id"), table_name="proposals")
        op.drop_table("proposals")
