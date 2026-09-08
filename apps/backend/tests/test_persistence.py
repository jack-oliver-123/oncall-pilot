from __future__ import annotations

import asyncio
import json
from dataclasses import FrozenInstanceError, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from migration_helpers import HEAD, write_database_config
from sqlalchemy import JSON, bindparam, event, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.memory import Repository, SchemaNotInitialized, SchemaRevision
from oncall_pilot.memory.sqlite import Database, SQLiteRepository, open_database
from oncall_pilot.memory.sqlite.database import database_url
from oncall_pilot.memory.sqlite.types import UTCDateTime
from oncall_pilot.memory.values import as_utc, deserialize_json, new_id, serialize_json, utc_now
from oncall_pilot.project_config import JsonValue, ProjectConfigError, load_project_config


@pytest.mark.parametrize(
    "raw",
    [
        None,
        3,
        "",
        "invalid-secret",
        "postgresql://u:secret@h/d",
        "sqlite:///x",
        "sqlite+aiosqlite:///:memory:",
        "sqlite+aiosqlite:///file:x",
        "sqlite+aiosqlite:///x?mode=ro",
        "sqlite+aiosqlite://u:secret@host/x",
    ],
)
def test_invalid_database_config_is_redacted(tmp_path: Path, raw: JsonValue) -> None:
    with pytest.raises(ProjectConfigError, match="database.url") as error:
        database_url({"database": {"url": raw}}, tmp_path)
    assert "secret" not in str(error.value)
    assert not list(tmp_path.iterdir())


async def test_merged_configuration_is_independent_of_cwd_and_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = write_database_config(tmp_path)
    (config_dir / "user.project.json").write_text(
        json.dumps({"database": {"url": "sqlite+aiosqlite:///other/空 格%25.db"}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(config_dir)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///wrong.db")
    url = database_url(load_project_config(config_dir), config_dir)
    expected = tmp_path / "other/空 格%25.db"
    assert url.database == expected.as_posix()
    assert not expected.parent.exists()
    async with open_database(config_dir) as database:
        assert not expected.exists()
        async with database.transaction() as session:
            assert await session.scalar(text("SELECT 1")) == 1
    assert expected.is_file()
    assert not (tmp_path / "var").exists()
    assert not (config_dir / "wrong.db").exists()


def test_absolute_url_and_missing_database(tmp_path: Path) -> None:
    expected = tmp_path / "absolute.db"
    url = database_url(
        {"database": {"url": f"sqlite+aiosqlite:///{expected.as_posix()}"}}, tmp_path / "config"
    )
    assert url.database == expected.as_posix()
    with pytest.raises(ProjectConfigError):
        database_url({}, tmp_path)


@dataclass
class FakeRepository:
    revision: SchemaRevision | None

    async def schema_revision(self) -> SchemaRevision:
        if self.revision is None:
            raise SchemaNotInitialized("请先执行迁移")
        return self.revision


@pytest.mark.parametrize("adapter", ["sqlite", "fake"])
async def test_repository_contract(database: Database, adapter: str) -> None:
    async with database.transaction() as session:
        repository: Repository = (
            SQLiteRepository(session)
            if adapter == "sqlite"
            else FakeRepository(SchemaRevision(HEAD))
        )
        record = await repository.schema_revision()
        assert record == SchemaRevision(HEAD)
        assert not hasattr(record, "_sa_instance_state")
        with pytest.raises(FrozenInstanceError):
            record.__setattr__("revision", "changed")
        assert await repository.schema_revision() == record


@pytest.mark.parametrize("adapter", ["sqlite", "fake"])
async def test_repository_contract_before_migration(tmp_path: Path, adapter: str) -> None:
    config_dir = write_database_config(tmp_path)
    async with open_database(config_dir) as database:
        async with database.transaction() as session:
            repository: Repository = (
                SQLiteRepository(session) if adapter == "sqlite" else FakeRepository(None)
            )
            with pytest.raises(SchemaNotInitialized):
                await repository.schema_revision()
            tables = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            assert tables.all() == []


async def _test_table(database: Database) -> None:
    async with database.transaction() as session:
        await session.execute(text("CREATE TABLE test_values (id TEXT PRIMARY KEY, value TEXT)"))


async def test_concurrent_async_sessions_commit_independently(database: Database) -> None:
    await _test_table(database)
    sessions: list[AsyncSession] = []
    ready = asyncio.Event()

    async def writer(index: int) -> None:
        async with database.transaction() as session:
            sessions.append(session)
            if len(sessions) == 6:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=5)
            await session.execute(
                text("INSERT INTO test_values VALUES (:id, :value)"),
                {"id": str(index), "value": str(index)},
            )
            await asyncio.sleep(0)

    await asyncio.wait_for(asyncio.gather(*(writer(i) for i in range(6))), timeout=15)
    assert len({id(session) for session in sessions}) == 6
    assert all(not session.in_transaction() for session in sessions)
    async with database.transaction() as session:
        assert await session.scalar(text("SELECT count(*) FROM test_values")) == 6


async def test_exception_and_cancellation_rollback_and_allow_reuse(database: Database) -> None:
    await _test_table(database)
    async with database.transaction() as session:
        await session.execute(text("INSERT INTO test_values VALUES ('kept', 'ok')"))
    with pytest.raises(ValueError, match="rollback"):
        async with database.transaction() as session:
            await session.execute(text("INSERT INTO test_values VALUES ('error', 'no')"))
            # adapter 读取不能偷偷提交调用方的写入。
            assert await SQLiteRepository(session).schema_revision() == SchemaRevision(HEAD)
            raise ValueError("rollback")
    inserted = asyncio.Event()
    never = asyncio.Event()

    async def cancelled_writer() -> None:
        async with database.transaction() as session:
            await session.execute(text("INSERT INTO test_values VALUES ('cancelled', 'no')"))
            inserted.set()
            await never.wait()

    task = asyncio.create_task(cancelled_writer())
    await asyncio.wait_for(inserted.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with database.transaction() as session:
        assert (await session.execute(text("SELECT id FROM test_values"))).scalars().all() == [
            "kept"
        ]
        await session.execute(text("INSERT INTO test_values VALUES ('after', 'ok')"))


async def test_foreign_keys_and_transactional_ddl(database: Database) -> None:
    async with database.transaction() as session:
        assert await session.scalar(text("PRAGMA foreign_keys")) == 1
        assert await session.scalar(text("PRAGMA busy_timeout")) == 5000
        await session.execute(text("CREATE TABLE test_parent (id INTEGER PRIMARY KEY)"))
        await session.execute(
            text("CREATE TABLE test_child (parent INTEGER REFERENCES test_parent)")
        )
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            await session.execute(text("INSERT INTO test_child VALUES (42)"))
    with pytest.raises(ValueError):
        async with database.transaction() as session:
            await session.execute(text("CREATE TABLE test_rolled_back (id INTEGER)"))
            raise ValueError("rollback")
    async with database.transaction() as session:
        assert (
            await session.scalar(
                text("SELECT count(*) FROM sqlite_master WHERE name='test_rolled_back'")
            )
            == 0
        )


async def test_close_releases_connections_and_rejects_new_transactions(database: Database) -> None:
    closed: list[object] = []

    def on_close(connection: object, record: object) -> None:
        closed.append(connection)

    event.listen(database.engine.sync_engine, "close", on_close)
    async with database.transaction() as session:
        await session.execute(text("SELECT 1"))
    assert len(closed) == 1
    await database.close()
    await database.close()
    with pytest.raises(RuntimeError, match="已关闭"):
        async with database.transaction():
            pytest.fail("关闭后不能打开事务")


async def test_values_round_trip(database: Database) -> None:
    await _test_table(database)
    value: JsonValue = {"中文": [None, True, 4, 2.5, {"nested": "ok"}]}
    identifier = new_id()
    assert UUID(identifier).version == 4
    assert identifier != new_id()
    stamp = datetime(2026, 9, 8, 12, 0, 1, 123456, timezone(timedelta(hours=8)))
    async with database.transaction() as session:
        await session.execute(text("CREATE TABLE test_time (stamp DATETIME)"))
        await session.execute(
            text("INSERT INTO test_values VALUES (:id, :value)").bindparams(
                bindparam("value", type_=JSON())
            ),
            {"id": identifier, "value": value},
        )
        await session.execute(
            text("INSERT INTO test_time VALUES (:stamp)").bindparams(
                bindparam("stamp", type_=UTCDateTime())
            ),
            {"stamp": stamp},
        )
    async with database.transaction() as session:
        actual = await session.scalar(text("SELECT value FROM test_values").columns(value=JSON()))
        assert actual == value
        actual_time = await session.scalar(
            text("SELECT stamp FROM test_time").columns(stamp=UTCDateTime())
        )
        assert actual_time == as_utc(stamp)
        assert actual_time.tzinfo == timezone.utc
    assert utc_now().tzinfo == timezone.utc


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), {"x": float("-inf")}, {1: "bad"}, {"x": object()}, (1, 2)]
)
async def test_invalid_json_rolls_back(database: Database, value: object) -> None:
    await _test_table(database)
    with pytest.raises(StatementError):
        async with database.transaction() as session:
            await session.execute(text("INSERT INTO test_values VALUES ('before', 'valid')"))
            await session.execute(
                text("INSERT INTO test_values VALUES ('invalid', :value)").bindparams(
                    bindparam("value", type_=JSON())
                ),
                {"value": value},
            )
    async with database.transaction() as session:
        assert await session.scalar(text("SELECT count(*) FROM test_values")) == 0


async def test_naive_datetime_is_rejected(database: Database) -> None:
    async with database.transaction() as session:
        await session.execute(text("CREATE TABLE test_time (stamp DATETIME)"))
    with pytest.raises(StatementError, match="时区"):
        async with database.transaction() as session:
            await session.execute(
                text("INSERT INTO test_time VALUES (:stamp)").bindparams(
                    bindparam("stamp", type_=UTCDateTime())
                ),
                {"stamp": datetime(2026, 9, 8)},
            )
    async with database.transaction() as session:
        assert await session.scalar(text("SELECT count(*) FROM test_time")) == 0


def test_json_helpers_reject_nonstandard_stored_values() -> None:
    assert deserialize_json(serialize_json({"a": [1, None]})) == {"a": [1, None]}
    for raw in ("NaN", "Infinity", '{"x":-Infinity}'):
        with pytest.raises(ValueError):
            deserialize_json(raw)
