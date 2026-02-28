"""Governance notification queue persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.services.queue import QueuedTask, enqueue_task
from app.services.queue import requeue_if_failed as generic_requeue_if_failed

logger = get_logger(__name__)
TASK_TYPE = "governance_notification"


@dataclass(frozen=True)
class GovernanceNotification:
    """Payload for a governance notification event."""

    event_type: str  # reviewers_selected | proposal_resolved | escalation_created | evaluation_created
    organization_id: UUID
    zone_id: UUID
    target_ids: list[UUID] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0


def _task_from_notification(notification: GovernanceNotification) -> QueuedTask:
    return QueuedTask(
        task_type=TASK_TYPE,
        payload={
            "event_type": notification.event_type,
            "organization_id": str(notification.organization_id),
            "zone_id": str(notification.zone_id),
            "target_ids": [str(tid) for tid in notification.target_ids],
            "payload": notification.payload,
        },
        created_at=notification.created_at,
        attempts=notification.attempts,
    )


def decode_notification_task(task: QueuedTask) -> GovernanceNotification:
    """Decode a QueuedTask into a GovernanceNotification."""
    if task.task_type != TASK_TYPE:
        raise ValueError(f"Unexpected task_type={task.task_type!r}; expected {TASK_TYPE!r}")

    p: dict[str, Any] = task.payload
    return GovernanceNotification(
        event_type=str(p["event_type"]),
        organization_id=UUID(p["organization_id"]),
        zone_id=UUID(p["zone_id"]),
        target_ids=[UUID(tid) for tid in p.get("target_ids", [])],
        payload=p.get("payload", {}),
        created_at=task.created_at,
        attempts=task.attempts,
    )


def enqueue_notification(notification: GovernanceNotification) -> bool:
    """Persist a governance notification in the Redis queue."""
    try:
        queued = _task_from_notification(notification)
        enqueue_task(queued, settings.rq_queue_name, redis_url=settings.rq_redis_url)
        logger.info(
            "governance.notification.enqueued",
            extra={
                "event_type": notification.event_type,
                "organization_id": str(notification.organization_id),
                "zone_id": str(notification.zone_id),
                "target_count": len(notification.target_ids),
            },
        )
        return True
    except Exception as exc:
        logger.warning(
            "governance.notification.enqueue_failed",
            extra={
                "event_type": notification.event_type,
                "organization_id": str(notification.organization_id),
                "error": str(exc),
            },
        )
        return False


def requeue_if_failed(
    notification: GovernanceNotification,
    *,
    delay_seconds: float = 0,
) -> bool:
    """Requeue a failed notification with capped retries."""
    try:
        return generic_requeue_if_failed(
            _task_from_notification(notification),
            settings.rq_queue_name,
            max_retries=settings.rq_dispatch_max_retries,
            redis_url=settings.rq_redis_url,
            delay_seconds=delay_seconds,
        )
    except Exception as exc:
        logger.warning(
            "governance.notification.requeue_failed",
            extra={
                "event_type": notification.event_type,
                "error": str(exc),
            },
        )
        return False
