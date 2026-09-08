"""仅在显式 Alembic 命令中加载配置、连接并迁移。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import context
from sqlalchemy.engine import URL, Connection

from oncall_pilot.auth import models as auth_models
from oncall_pilot.memory.sqlite.base import Base
from oncall_pilot.memory.sqlite.database import create_engine, database_url
from oncall_pilot.project_config import ProjectConfigError, load_project_config

assert auth_models.UserRow.metadata is Base.metadata
target_metadata = Base.metadata


def _configured_url() -> URL:
    raw = context.get_x_argument(as_dictionary=True).get("config-dir")
    if raw is None:
        raise ProjectConfigError("Alembic 必须通过 -x config-dir=<path> 显式指定配置目录")
    config_dir = Path(raw).resolve()
    return database_url(load_project_config(config_dir), config_dir)


def run_migrations_offline() -> None:
    context.configure(
        url=_configured_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_engine(_configured_url())
    try:
        async with engine.begin() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
