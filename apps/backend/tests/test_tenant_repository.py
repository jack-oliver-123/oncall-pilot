from typing import Any
from unittest.mock import AsyncMock

import pytest
from scope_contract import assert_owner_parameter_contract
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tenant_probe import ChildRow, ParentRow, ProbeBase, ProbeRepository, Resource

from oncall_pilot.memory.sqlite import Database


async def create_probe_tables(database: Database) -> None:
    async with database.transaction() as session:
        connection = await session.connection()
        await connection.run_sync(ProbeBase.metadata.create_all)


async def test_all_future_repository_parameters_fail_without_io() -> None:
    session = AsyncMock(spec=AsyncSession)
    repo = ProbeRepository(session)
    cases: dict[str, dict[str, Any]] = {
        "create_parent": {"resource": Resource("p", "private")},
        "get_parent": {"resource_id": "p"},
        "list_parents": {},
        "update_parent": {"resource_id": "p", "name": "changed"},
        "delete_parent": {"resource_id": "p"},
        "create_child": {"parent_id": "p", "resource": Resource("c", "private")},
        "list_children": {"parent_id": "p"},
        "get_child": {"parent_id": "p", "resource_id": "c"},
        "update_child": {"parent_id": "p", "resource_id": "c", "name": "changed"},
        "delete_child": {"parent_id": "p", "resource_id": "c"},
    }
    for method, arguments in cases.items():
        await assert_owner_parameter_contract(getattr(repo, method), **arguments)
    assert session.mock_calls == []


async def test_two_owners_crud_parents_children_and_sql_scope(database: Database) -> None:
    await create_probe_tables(database)
    async with database.transaction() as session:
        repo = ProbeRepository(session)
        for owner in ["a", "b"]:
            await repo.create_parent(Resource("shared-id", f"{owner}-private"), owner_user_id=owner)
            await repo.create_parent(Resource(f"{owner}-parent", owner), owner_user_id=owner)
            assert await repo.create_child(
                f"{owner}-parent",
                Resource(f"{owner}-child", f"{owner}-secret"),
                owner_user_id=owner,
            )
        assert (
            await repo.create_child("a-parent", Resource("invalid", "bad"), owner_user_id="b")
            is None
        )

    statements: list[tuple[str, Any]] = []

    def capture(
        conn: Connection, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        statements.append((statement, parameters))

    async with database.transaction() as session:
        connection = await session.connection()
        event.listen(connection.sync_connection, "before_cursor_execute", capture)
        repo = ProbeRepository(session)
        # 同一 session 先缓存甲对象，乙查询仍必须执行 SQL owner 条件。
        cached = await session.get(ParentRow, ("a", "shared-id"))
        statements.clear()
        assert cached is not None
        assert await repo.get_parent("shared-id", owner_user_id="b") == Resource(
            "shared-id", "b-private"
        )
        assert await repo.get_parent("a-parent", owner_user_id="b") is None
        assert await repo.get_parent("missing", owner_user_id="b") is None
        assert {r.name for r in await repo.list_parents(owner_user_id="b")} == {"b", "b-private"}
        assert await repo.update_parent("a-parent", "bad", owner_user_id="b") is None
        assert await repo.delete_parent("a-parent", owner_user_id="b") is None
        assert await repo.list_children("a-parent", owner_user_id="b") is None
        assert await repo.list_children("missing", owner_user_id="b") is None
        assert await repo.list_children("shared-id", owner_user_id="b") == []
        for parent, child in [
            ("a-parent", "a-child"),
            ("b-parent", "a-child"),
            ("shared-id", "b-child"),
            ("missing", "b-child"),
        ]:
            assert await repo.get_child(parent, child, owner_user_id="b") is None
            assert await repo.update_child(parent, child, "bad", owner_user_id="b") is None
            assert await repo.delete_child(parent, child, owner_user_id="b") is None
        # 不只是返回值：实际读写 SQL 都带 WHERE owner，且 owner 使用绑定参数。
        assert len(statements) >= 20
        for statement, parameters in statements:
            where = statement.partition("WHERE")[2]
            assert "owner_user_id = ?" in where, statement
            assert "b" in parameters
        event.remove(connection.sync_connection, "before_cursor_execute", capture)
        assert await repo.get_child("a-parent", "a-child", owner_user_id="a") == Resource(
            "a-child", "a-secret"
        )
        assert await repo.update_parent("shared-id", "b-updated", owner_user_id="b")
        assert await repo.get_parent("shared-id", owner_user_id="a") == Resource(
            "shared-id", "a-private"
        )
        assert await repo.update_child("b-parent", "b-child", "b-updated", owner_user_id="b")
        assert await repo.get_child("b-parent", "b-child", owner_user_id="b") == Resource(
            "b-child", "b-updated"
        )
        assert await repo.delete_child("b-parent", "b-child", owner_user_id="b")
        assert await repo.delete_parent("shared-id", owner_user_id="b")
        assert await repo.get_parent("shared-id", owner_user_id="a") is not None
        assert await repo.get_parent("shared-id", owner_user_id="b") is None

    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(ChildRow(id="bad", owner_user_id="b", parent_id="a-parent", name="invalid"))
            await session.flush()

    # cascade 只能删除当前 owner 的父子资源。
    async with database.transaction() as session:
        repo = ProbeRepository(session)
        assert await repo.delete_parent("a-parent", owner_user_id="a")
        assert await repo.get_child("a-parent", "a-child", owner_user_id="a") is None
        assert await repo.get_parent("b-parent", owner_user_id="b") is not None
