"""Phase 1: Trust zones, zone assignments, audit entries, and model extensions.

Revision ID: a3b4c5d6e7f8
Revises: f1b2c3d4e5a6
Create Date: 2026-02-26 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "f1b2c3d4e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- trust_zones table ---
    if not inspector.has_table("trust_zones"):
        op.create_table(
            "trust_zones",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("parent_zone_id", sa.Uuid(), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False, server_default=""),
            sa.Column(
                "status", sa.String(), nullable=False, server_default="draft"
            ),
            sa.Column("created_by", sa.Uuid(), nullable=False),
            sa.Column("responsibilities", sa.JSON(), nullable=True),
            sa.Column("resource_scope", sa.JSON(), nullable=True),
            sa.Column("agent_qualifications", sa.JSON(), nullable=True),
            sa.Column("alignment_requirements", sa.JSON(), nullable=True),
            sa.Column("incentive_model", sa.JSON(), nullable=True),
            sa.Column("constraints", sa.JSON(), nullable=True),
            sa.Column("decision_model", sa.JSON(), nullable=True),
            sa.Column("approval_policy", sa.JSON(), nullable=True),
            sa.Column("escalation_policy", sa.JSON(), nullable=True),
            sa.Column("evaluation_criteria", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"]
            ),
            sa.ForeignKeyConstraint(
                ["parent_zone_id"], ["trust_zones.id"]
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_trust_zones_organization_id"),
            "trust_zones",
            ["organization_id"],
        )
        op.create_index(
            op.f("ix_trust_zones_parent_zone_id"),
            "trust_zones",
            ["parent_zone_id"],
        )
        op.create_index(
            op.f("ix_trust_zones_slug"), "trust_zones", ["slug"]
        )
        op.create_index(
            op.f("ix_trust_zones_status"), "trust_zones", ["status"]
        )
        op.create_index(
            op.f("ix_trust_zones_created_by"), "trust_zones", ["created_by"]
        )

    # --- zone_assignments table ---
    if not inspector.has_table("zone_assignments"):
        op.create_table(
            "zone_assignments",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("zone_id", sa.Uuid(), nullable=False),
            sa.Column("member_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("assigned_by", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["zone_id"], ["trust_zones.id"]),
            sa.ForeignKeyConstraint(
                ["member_id"], ["organization_members.id"]
            ),
            sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "zone_id",
                "member_id",
                "role",
                name="uq_zone_assignments_zone_member_role",
            ),
        )
        op.create_index(
            op.f("ix_zone_assignments_zone_id"),
            "zone_assignments",
            ["zone_id"],
        )
        op.create_index(
            op.f("ix_zone_assignments_member_id"),
            "zone_assignments",
            ["member_id"],
        )
        op.create_index(
            op.f("ix_zone_assignments_role"),
            "zone_assignments",
            ["role"],
        )
        op.create_index(
            op.f("ix_zone_assignments_assigned_by"),
            "zone_assignments",
            ["assigned_by"],
        )

    # --- audit_entries table ---
    if not inspector.has_table("audit_entries"):
        op.create_table(
            "audit_entries",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("zone_id", sa.Uuid(), nullable=True),
            sa.Column("actor_id", sa.Uuid(), nullable=False),
            sa.Column("actor_type", sa.String(), nullable=False),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("target_type", sa.String(), nullable=False, server_default=""),
            sa.Column("target_id", sa.Uuid(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"]
            ),
            sa.ForeignKeyConstraint(
                ["zone_id"], ["trust_zones.id"]
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_audit_entries_organization_id"),
            "audit_entries",
            ["organization_id"],
        )
        op.create_index(
            op.f("ix_audit_entries_zone_id"),
            "audit_entries",
            ["zone_id"],
        )
        op.create_index(
            op.f("ix_audit_entries_actor_id"),
            "audit_entries",
            ["actor_id"],
        )
        op.create_index(
            op.f("ix_audit_entries_actor_type"),
            "audit_entries",
            ["actor_type"],
        )
        op.create_index(
            op.f("ix_audit_entries_action"),
            "audit_entries",
            ["action"],
        )

    # --- Add reputation_score to organization_members ---
    member_columns = {
        column["name"] for column in inspector.get_columns("organization_members")
    }
    if "reputation_score" not in member_columns:
        op.add_column(
            "organization_members",
            sa.Column(
                "reputation_score",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.0"),
            ),
        )

    # --- Add zone_id to boards ---
    board_columns = {column["name"] for column in inspector.get_columns("boards")}
    if "zone_id" not in board_columns:
        op.add_column(
            "boards",
            sa.Column("zone_id", sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            "fk_boards_zone_id",
            "boards",
            "trust_zones",
            ["zone_id"],
            ["id"],
        )
        op.create_index(
            op.f("ix_boards_zone_id"), "boards", ["zone_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Remove zone_id from boards
    board_columns = {column["name"] for column in inspector.get_columns("boards")}
    if "zone_id" in board_columns:
        op.drop_index(op.f("ix_boards_zone_id"), table_name="boards")
        op.drop_constraint("fk_boards_zone_id", "boards", type_="foreignkey")
        op.drop_column("boards", "zone_id")

    # Remove reputation_score from organization_members
    member_columns = {
        column["name"] for column in inspector.get_columns("organization_members")
    }
    if "reputation_score" in member_columns:
        op.drop_column("organization_members", "reputation_score")

    # Drop tables
    if inspector.has_table("audit_entries"):
        op.drop_index(op.f("ix_audit_entries_action"), table_name="audit_entries")
        op.drop_index(op.f("ix_audit_entries_actor_type"), table_name="audit_entries")
        op.drop_index(op.f("ix_audit_entries_actor_id"), table_name="audit_entries")
        op.drop_index(op.f("ix_audit_entries_zone_id"), table_name="audit_entries")
        op.drop_index(
            op.f("ix_audit_entries_organization_id"), table_name="audit_entries"
        )
        op.drop_table("audit_entries")

    if inspector.has_table("zone_assignments"):
        op.drop_index(
            op.f("ix_zone_assignments_assigned_by"), table_name="zone_assignments"
        )
        op.drop_index(op.f("ix_zone_assignments_role"), table_name="zone_assignments")
        op.drop_index(
            op.f("ix_zone_assignments_member_id"), table_name="zone_assignments"
        )
        op.drop_index(
            op.f("ix_zone_assignments_zone_id"), table_name="zone_assignments"
        )
        op.drop_table("zone_assignments")

    if inspector.has_table("trust_zones"):
        op.drop_index(op.f("ix_trust_zones_created_by"), table_name="trust_zones")
        op.drop_index(op.f("ix_trust_zones_status"), table_name="trust_zones")
        op.drop_index(op.f("ix_trust_zones_slug"), table_name="trust_zones")
        op.drop_index(
            op.f("ix_trust_zones_parent_zone_id"), table_name="trust_zones"
        )
        op.drop_index(
            op.f("ix_trust_zones_organization_id"), table_name="trust_zones"
        )
        op.drop_table("trust_zones")
