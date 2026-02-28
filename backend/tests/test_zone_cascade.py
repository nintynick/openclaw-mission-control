# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from app.models.trust_zones import TrustZone, ZONE_STATUS_TRANSITIONS
from app.services.trust_zones import (
    cascade_status,
    validate_status_transition,
)
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers — Fake session that tracks zone children in memory
# ---------------------------------------------------------------------------


@dataclass
class _FakeSession:
    """In-memory session for cascade tests."""

    zones: dict[Any, TrustZone] = field(default_factory=dict)
    added: list[Any] = field(default_factory=list)
    committed: int = 0

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed += 1

    async def refresh(self, _value: Any) -> None:
        pass

    async def exec(self, statement: Any) -> Any:
        return _FakeExecResult()


@dataclass
class _FakeExecResult:
    first_value: Any = None
    all_values: list[Any] | None = None

    def first(self) -> Any:
        return self.first_value

    def __iter__(self):
        return iter(self.all_values or [])


# ---------------------------------------------------------------------------
# Status transition tests
# ---------------------------------------------------------------------------


def test_valid_transitions_from_draft() -> None:
    assert ZONE_STATUS_TRANSITIONS["draft"] == {"active", "archived"}


def test_valid_transitions_from_active() -> None:
    assert ZONE_STATUS_TRANSITIONS["active"] == {"suspended", "archived"}


def test_valid_transitions_from_suspended() -> None:
    assert ZONE_STATUS_TRANSITIONS["suspended"] == {"active", "archived"}


def test_archived_is_terminal() -> None:
    assert ZONE_STATUS_TRANSITIONS["archived"] == set()


def test_validate_status_transition_valid() -> None:
    validate_status_transition("draft", "active")
    validate_status_transition("active", "suspended")
    validate_status_transition("suspended", "archived")


def test_validate_status_transition_invalid_target() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_status_transition("draft", "suspended")
    assert exc.value.status_code == 422


def test_validate_status_transition_archived_to_anything() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_status_transition("archived", "active")
    assert exc.value.status_code == 422


def test_validate_status_transition_unknown_status() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_status_transition("draft", "bogus")
    assert exc.value.status_code == 422
