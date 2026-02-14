# ruff: noqa: INP001
"""Webhook queue and dispatch worker tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.services.webhooks import dispatch
from app.services.webhooks.queue import (
    QueuedWebhookDelivery,
    dequeue_webhook_delivery,
    enqueue_webhook_delivery,
    requeue_if_failed,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.values: list[str] = []

    def lpush(self, key: str, value: str) -> None:
        self.values.insert(0, value)

    def rpop(self, key: str) -> str | None:
        if not self.values:
            return None
        return self.values.pop()


@pytest.mark.parametrize("attempts", [0, 1, 2])
def test_webhook_queue_roundtrip(monkeypatch: pytest.MonkeyPatch, attempts: int) -> None:
    fake = _FakeRedis()

    def _fake_redis() -> _FakeRedis:
        return fake

    board_id = uuid4()
    webhook_id = uuid4()
    payload_id = uuid4()
    payload = QueuedWebhookDelivery(
        board_id=board_id,
        webhook_id=webhook_id,
        payload_id=payload_id,
        payload_event="push",
        received_at=datetime.now(UTC),
        attempts=attempts,
    )

    monkeypatch.setattr("app.services.webhooks.queue._redis_client", _fake_redis)
    assert enqueue_webhook_delivery(payload)

    dequeued = dequeue_webhook_delivery()
    assert dequeued is not None
    assert dequeued.board_id == board_id
    assert dequeued.webhook_id == webhook_id
    assert dequeued.payload_id == payload_id
    assert dequeued.payload_event == "push"
    assert dequeued.attempts == attempts


@pytest.mark.parametrize("attempts", [0, 1, 2, 3])
def test_requeue_respects_retry_cap(monkeypatch: pytest.MonkeyPatch, attempts: int) -> None:
    fake = _FakeRedis()

    def _fake_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr("app.services.webhooks.queue._redis_client", _fake_redis)

    payload = QueuedWebhookDelivery(
        board_id=uuid4(),
        webhook_id=uuid4(),
        payload_id=uuid4(),
        payload_event="push",
        received_at=datetime.now(UTC),
        attempts=attempts,
    )

    if attempts >= 3:
        assert requeue_if_failed(payload) is False
        assert fake.values == []
    else:
        assert requeue_if_failed(payload) is True
        requeued = dequeue_webhook_delivery()
        assert requeued is not None
        assert requeued.attempts == attempts + 1


class _FakeQueuedItem:
    def __init__(self, attempts: int = 0) -> None:
        self.payload_id = uuid4()
        self.webhook_id = uuid4()
        self.board_id = uuid4()
        self.attempts = attempts


def _patch_dequeue(monkeypatch: pytest.MonkeyPatch, items: list[QueuedWebhookDelivery | None]) -> None:
    def _dequeue() -> QueuedWebhookDelivery | None:
        if not items:
            return None
        return items.pop(0)

    monkeypatch.setattr(dispatch, "dequeue_webhook_delivery", _dequeue)


@pytest.mark.asyncio
async def test_dispatch_flush_processes_items_and_throttles(monkeypatch: pytest.MonkeyPatch) -> None:
    items: list[QueuedWebhookDelivery | None] = [
        _FakeQueuedItem(),
        _FakeQueuedItem(),
        None,
    ]
    _patch_dequeue(monkeypatch, items)

    processed: list[UUID] = []
    throttles: list[float] = []

    async def _process(item: QueuedWebhookDelivery) -> None:
        processed.append(item.payload_id)

    monkeypatch.setattr(dispatch, "_process_single_item", _process)
    monkeypatch.setattr(dispatch.settings, "webhook_dispatch_throttle_seconds", 0)

    async def _sleep(seconds: float) -> None:
        throttles.append(float(seconds))

    monkeypatch.setattr(dispatch.asyncio, "sleep", _sleep)

    await dispatch.flush_webhook_delivery_queue()

    assert len(processed) == 2
    assert throttles == [0.0, 0.0]


@pytest.mark.asyncio
async def test_dispatch_flush_requeues_on_process_error(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _FakeQueuedItem()
    _patch_dequeue(monkeypatch, [item, None])

    async def _process(_: QueuedWebhookDelivery) -> None:
        raise RuntimeError("boom")

    requeued: list[QueuedWebhookDelivery] = []

    def _requeue(payload: QueuedWebhookDelivery) -> bool:
        requeued.append(payload)
        return True

    monkeypatch.setattr(dispatch, "_process_single_item", _process)
    monkeypatch.setattr(dispatch, "requeue_if_failed", _requeue)
    monkeypatch.setattr(dispatch.settings, "webhook_dispatch_throttle_seconds", 0)

    async def _sleep(_: float) -> None:
        return None

    monkeypatch.setattr(dispatch.asyncio, "sleep", _sleep)

    await dispatch.flush_webhook_delivery_queue()

    assert len(requeued) == 1
    assert requeued[0].payload_id == item.payload_id


@pytest.mark.asyncio
async def test_dispatch_flush_recovers_from_dequeue_error(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _FakeQueuedItem()
    call_count = 0

    def _dequeue() -> QueuedWebhookDelivery | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("dequeue broken")
        if call_count == 2:
            return item
        return None

    monkeypatch.setattr(dispatch, "dequeue_webhook_delivery", _dequeue)

    processed = 0

    async def _process(_: QueuedWebhookDelivery) -> None:
        nonlocal processed
        processed += 1

    monkeypatch.setattr(dispatch, "_process_single_item", _process)
    monkeypatch.setattr(dispatch.settings, "webhook_dispatch_throttle_seconds", 0)

    async def _sleep(_: float) -> None:
        return None

    monkeypatch.setattr(dispatch.asyncio, "sleep", _sleep)

    await dispatch.flush_webhook_delivery_queue()

    assert call_count == 3
    assert processed == 1


def test_dispatch_run_entrypoint_calls_async_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    async def _flush() -> None:
        called.append(True)

    monkeypatch.setattr(dispatch, "flush_webhook_delivery_queue", _flush)

    dispatch.run_flush_webhook_delivery_queue()

    assert called == [True]
