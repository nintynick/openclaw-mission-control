"""add agent provision confirmation

Revision ID: 6df47d330227
Revises: e0f28e965fa5
Create Date: 2026-02-04 17:16:44.472239

"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = '6df47d330227'
down_revision = 'e0f28e965fa5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS provision_requested_at TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS provision_confirm_token_hash VARCHAR"
    )
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS provision_action VARCHAR"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agents DROP COLUMN IF EXISTS provision_action"
    )
    op.execute(
        "ALTER TABLE agents DROP COLUMN IF EXISTS provision_confirm_token_hash"
    )
    op.execute(
        "ALTER TABLE agents DROP COLUMN IF EXISTS provision_requested_at"
    )
