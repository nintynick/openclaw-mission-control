"""Zone assignment model linking organization members to trust zone roles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class ZoneAssignment(QueryModel, table=True):
    """Assignment of an organization member to a role within a trust zone."""

    __tablename__ = "zone_assignments"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "zone_id",
            "member_id",
            "role",
            name="uq_zone_assignments_zone_member_role",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    zone_id: UUID = Field(foreign_key="trust_zones.id", index=True)
    member_id: UUID = Field(foreign_key="organization_members.id", index=True)
    role: str = Field(index=True)
    assigned_by: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
