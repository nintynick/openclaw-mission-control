"""Append-only audit log model for governance actions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class AuditEntry(QueryModel, table=True):
    """Append-only audit log entry for governance and zone actions."""

    __tablename__ = "audit_entries"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    zone_id: UUID | None = Field(
        default=None, foreign_key="trust_zones.id", index=True
    )
    actor_id: UUID = Field(index=True)
    actor_type: str = Field(index=True)
    action: str = Field(index=True)
    target_type: str = Field(default="")
    target_id: UUID | None = None
    payload: dict[str, object] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
