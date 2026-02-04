from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import SQLModel


class AgentBase(SQLModel):
    board_id: UUID | None = None
    name: str
    status: str = "provisioning"
    heartbeat_config: dict[str, Any] | None = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(SQLModel):
    board_id: UUID | None = None
    name: str | None = None
    status: str | None = None
    heartbeat_config: dict[str, Any] | None = None


class AgentRead(AgentBase):
    id: UUID
    openclaw_session_id: str | None = None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentHeartbeat(SQLModel):
    status: str | None = None


class AgentHeartbeatCreate(AgentHeartbeat):
    name: str
    board_id: UUID | None = None


class AgentDeleteConfirm(SQLModel):
    token: str


class AgentProvisionConfirm(SQLModel):
    token: str
    action: str | None = None
