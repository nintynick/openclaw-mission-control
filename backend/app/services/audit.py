"""Audit logging service for governance actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.time import utcnow
from app.models.audit_entries import AuditEntry

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def record_audit(
    session: AsyncSession,
    *,
    organization_id: UUID,
    actor_id: UUID,
    actor_type: str,
    action: str,
    zone_id: UUID | None = None,
    target_type: str = "",
    target_id: UUID | None = None,
    payload: dict[str, object] | None = None,
    commit: bool = True,
) -> AuditEntry:
    """Create an append-only audit log entry."""
    entry = AuditEntry(
        organization_id=organization_id,
        zone_id=zone_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        created_at=utcnow(),
    )
    session.add(entry)
    if commit:
        await session.commit()
        await session.refresh(entry)
    return entry
