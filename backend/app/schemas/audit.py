"""Schemas for the audit query API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class AuditEntryRead(SQLModel):
    """Audit entry payload returned by read endpoints."""

    id: UUID
    organization_id: UUID
    zone_id: UUID | None = None
    actor_id: UUID
    actor_type: str
    action: str
    target_type: str
    target_id: UUID | None = None
    payload: dict[str, object] | None = None
    created_at: datetime
