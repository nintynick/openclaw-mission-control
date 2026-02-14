"""Webhook dispatch scheduler bootstrap for rq-scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis import Redis
from rq_scheduler import Scheduler  # type: ignore[import-untyped]

from app.core.config import settings
from app.services.webhooks import dispatch


def bootstrap_webhook_dispatch_schedule(interval_seconds: int | None = None) -> None:
    """Register a recurring queue-flush job and keep it idempotent."""
    connection = Redis.from_url(settings.webhook_redis_url)
    scheduler = Scheduler(queue_name=settings.webhook_leads_rq_queue_name, connection=connection)

    for job in scheduler.get_jobs():
        if job.id == settings.webhook_dispatch_schedule_id:
            scheduler.cancel(job)

    effective_interval_seconds = (
        settings.webhook_dispatch_schedule_interval_seconds
        if interval_seconds is None
        else interval_seconds
    )

    scheduler.schedule(
        datetime.now(tz=timezone.utc) + timedelta(seconds=5),
        func=dispatch.run_flush_webhook_delivery_queue,
        interval=effective_interval_seconds,
        repeat=None,
        id=settings.webhook_dispatch_schedule_id,
        queue_name=settings.webhook_leads_rq_queue_name,
    )
