"""Governance notification dispatch handler."""

from __future__ import annotations

from app.core.logging import get_logger
from app.services.governance_notifications.queue import (
    GovernanceNotification,
    decode_notification_task,
    requeue_if_failed,
)
from app.services.queue import QueuedTask

logger = get_logger(__name__)


def _dispatch(notification: GovernanceNotification) -> None:
    """Dispatch a governance notification.

    Currently logs the notification. This is the hook point for
    email/webhook/Slack integrations in future phases.
    """
    logger.info(
        "governance.notification.dispatch",
        extra={
            "event_type": notification.event_type,
            "organization_id": str(notification.organization_id),
            "zone_id": str(notification.zone_id),
            "target_ids": [str(tid) for tid in notification.target_ids],
            "payload_keys": list(notification.payload.keys()) if notification.payload else [],
        },
    )


async def process_notification_task(task: QueuedTask) -> None:
    """Decode and dispatch a governance notification task."""
    notification = decode_notification_task(task)
    _dispatch(notification)


def requeue_notification_task(task: QueuedTask, *, delay_seconds: float = 0) -> bool:
    """Requeue a failed notification task."""
    notification = decode_notification_task(task)
    return requeue_if_failed(notification, delay_seconds=delay_seconds)
