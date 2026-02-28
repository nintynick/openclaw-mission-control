"""FastAPI dependency factory for trust zone permission checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.api.deps import require_org_member
from app.db.session import get_session
from app.models.trust_zones import TrustZone
from app.services.organizations import OrganizationContext
from app.services.permission_resolver import resolve_zone_permission

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class ZoneAuthContext:
    """Resolved zone + organization context after permission check."""

    zone: TrustZone
    org_ctx: OrganizationContext


def require_zone_permission(action: str) -> ZoneAuthContext:  # type: ignore[return]
    """FastAPI dependency factory that checks zone-level permissions.

    Usage:
        @router.post(...)
        async def my_endpoint(
            zone_ctx: ZoneAuthContext = Depends(require_zone_permission("zone.write")),
        ):
            ...
    """

    async def _dependency(
        zone_id: UUID,
        session: AsyncSession = Depends(get_session),
        org_ctx: OrganizationContext = Depends(require_org_member),
    ) -> ZoneAuthContext:
        zone = await TrustZone.objects.by_id(zone_id).first(session)
        if zone is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if zone.organization_id != org_ctx.organization.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        allowed = await resolve_zone_permission(
            session,
            member=org_ctx.member,
            zone=zone,
            action=action,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {action}",
            )
        return ZoneAuthContext(zone=zone, org_ctx=org_ctx)

    return Depends(_dependency)  # type: ignore[return-value]
