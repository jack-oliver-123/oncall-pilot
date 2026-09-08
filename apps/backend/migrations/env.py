"""仅在显式 Alembic 命令中加载数据库配置。"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from oncall_pilot.project_config import JsonObject, ProjectConfigError, load_project_config

config = context.config
if config.config_file_name is not None and config.get_section("loggers") is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _explicit_config_dir() -> Path:
    raw = context.get_x_argument(as_dictionary=True).get("config-dir")
    if raw is None:
        raise ProjectConfigError("Alembic 必须通过 -x config-dir=<path> 显式指定配置目录")
    return Path(raw).resolve()


def _database_url(project_config: JsonObject, config_dir: Path) -> str:
    database = project_config.get("database")
    if not isinstance(database, dict):
        raise ProjectConfigError("project.json 缺少 database object")
    value = database.get("url")
    if not isinstance(value, str) or not value:
        raise ProjectConfigError("project.json 缺少 database.url")

    prefix = "sqlite+aiosqlite:///"
    if not value.startswith(prefix):
        return value

    raw_path = value.removeprefix(prefix)
    database_path = Path(raw_path)
    if database_path.is_absolute():
        return value

    resolved_path = (config_dir.parent / database_path).resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{resolved_path.as_posix()}"


def _configure_database_url() -> None:
    config_dir = _explicit_config_dir()
    project_config = load_project_config(config_dir)
    config.set_main_option("sqlalchemy.url", _database_url(project_config, config_dir))


def run_migrations_offline() -> None:
    _configure_database_url()
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    _configure_database_url()
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
