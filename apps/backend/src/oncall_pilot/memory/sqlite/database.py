"""由组合层显式拥有的 SQLite engine 和事务资源。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from sqlalchemy import event
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from oncall_pilot.memory.values import deserialize_json, serialize_json
from oncall_pilot.project_config import JsonObject, ProjectConfigError, load_project_config


def database_url(project_config: JsonObject, config_dir: Path) -> URL:
    """只解析注入配置，不创建目录或连接；错误不包含原始 URL。"""
    database = project_config.get("database")
    raw = database.get("url") if isinstance(database, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        raise ProjectConfigError("本地配置必须包含非空 database.url")
    try:
        url = make_url(raw)
    except (ArgumentError, ValueError):
        raise ProjectConfigError("database.url 格式无效") from None
    if (
        url.drivername != "sqlite+aiosqlite"
        or not url.database
        or url.database == ":memory:"
        or url.database.startswith("file:")
        or url.query
        or url.host is not None
        or url.username is not None
        or url.password is not None
        or url.port is not None
    ):
        raise ProjectConfigError("database.url 必须是 sqlite+aiosqlite 本地文件 URL")
    path = Path(url.database)
    if not path.is_absolute():
        path = config_dir.resolve().parent / path
    return url.set(database=path.resolve().as_posix())


def _configure_connection(raw_connection: object, connection_record: object) -> None:
    connection = cast(DBAPIConnection, raw_connection)
    connection.isolation_level = None
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def _begin(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN")


def create_engine(url: URL) -> AsyncEngine:
    """供显式初始化及 Alembic 共用；只接收 database_url 的已校验结果。"""
    if url.database is None:
        raise ProjectConfigError("database.url 缺少文件路径")
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        json_serializer=serialize_json,
        json_deserializer=deserialize_json,
    )
    event.listen(engine.sync_engine, "connect", _configure_connection)
    event.listen(engine.sync_engine, "begin", _begin)
    return engine


class Database:
    """每个事务拥有一个 session；关闭前调用方必须等待在途工作结束。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._closed = False

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession]:
        if self._closed:
            raise RuntimeError("数据库资源已关闭")
        async with self._sessions.begin() as session:
            yield session

    async def close(self) -> None:
        self._closed = True
        await self.engine.dispose()


@asynccontextmanager
async def open_database(config_dir: Path) -> AsyncGenerator[Database]:
    """显式加载本地配置并管理资源；不自动迁移或建表。"""
    url = database_url(load_project_config(config_dir), config_dir)
    database = Database(create_engine(url))
    try:
        yield database
    finally:
        await database.close()
