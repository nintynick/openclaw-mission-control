from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from app.api import boards
from app.models.boards import Board


@dataclass
class _FakeSession:
    exec_results: list[Any]
    executed: list[Any] = field(default_factory=list)
    deleted: list[Any] = field(default_factory=list)
    committed: int = 0

    async def exec(self, _statement: Any) -> Any:
        if not self.exec_results:
            raise AssertionError("No more exec_results left for session.exec")
        return self.exec_results.pop(0)

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    async def delete(self, value: Any) -> None:
        self.deleted.append(value)

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_delete_board_cleans_org_board_access_rows() -> None:
    session = _FakeSession(exec_results=[[], []])
    board = Board(
        id=uuid4(),
        organization_id=uuid4(),
        name="Demo Board",
        slug="demo-board",
        gateway_id=None,
    )

    await boards.delete_board(session=session, board=board)

    deleted_table_names = [statement.table.name for statement in session.executed]
    assert "organization_board_access" in deleted_table_names
    assert "organization_invite_board_access" in deleted_table_names
    assert board in session.deleted
    assert session.committed == 1
