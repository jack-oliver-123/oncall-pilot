from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from migration_helpers import BACKEND_ROOT, HEAD, migrate, write_database_config
from sqlalchemy import Column, Integer, MetaData, Table, inspect, text
from sqlalchemy.engine import Connection

from oncall_pilot.auth.models import UserRow
from oncall_pilot.memory import SchemaRevision
from oncall_pilot.memory.sqlite import Database, SQLiteRepository, open_database
from oncall_pilot.memory.sqlite.base import Base


def _assert_metadata_matches(connection: Connection) -> None:
    assert UserRow.metadata is Base.metadata
    assert inspect(connection).get_table_names() == ["alembic_version", "auth_sessions", "users"]
    context = MigrationContext.configure(connection)
    assert compare_metadata(context, Base.metadata) == []
    # 负向探针证明比较器真的能发现未迁移的表，不只比较两个空集合。
    probe = MetaData()
    Table("test_missing_migration", probe, Column("id", Integer, primary_key=True))
    assert compare_metadata(context, probe)


async def test_fresh_repeat_upgrade_and_metadata_consistency(tmp_path: Path) -> None:
    config_dir = write_database_config(tmp_path, "sqlite+aiosqlite:///var/空 格%25.db")
    migrate(config_dir, "upgrade", "head")
    migrate(config_dir, "upgrade", "head")
    assert HEAD in migrate(config_dir, "current").stdout
    assert "No new upgrade operations detected" in migrate(config_dir, "check").stdout
    async with open_database(config_dir) as database:
        async with database.engine.connect() as connection:
            await connection.run_sync(_assert_metadata_matches)
        async with database.transaction() as session:
            assert await SQLiteRepository(session).schema_revision() == SchemaRevision(HEAD)


async def test_downgrade_and_upgrade_again(tmp_path: Path) -> None:
    config_dir = write_database_config(tmp_path)
    migrate(config_dir, "upgrade", "0001_persistence_foundation")
    async with open_database(config_dir) as database:
        async with database.engine.connect() as connection:
            tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
            assert tables == ["alembic_version"]
    migrate(config_dir, "upgrade", "head")
    migrate(config_dir, "downgrade", "0001_persistence_foundation")
    async with open_database(config_dir) as database:
        async with database.engine.connect() as connection:
            tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
            assert tables == ["alembic_version"]
    migrate(config_dir, "upgrade", "head")
    migrate(config_dir, "downgrade", "base")
    async with open_database(config_dir) as database:
        async with database.transaction() as session:
            assert await session.scalar(text("SELECT count(*) FROM alembic_version")) == 0
    migrate(config_dir, "upgrade", "head")
    assert HEAD in migrate(config_dir, "current").stdout


def test_offline_upgrade_does_not_create_directories_or_database(tmp_path: Path) -> None:
    config_dir = write_database_config(tmp_path)
    result = migrate(config_dir, "upgrade", "head", "--sql")
    assert "CREATE TABLE alembic_version" in result.stdout
    assert HEAD in result.stdout
    assert not (tmp_path / "var").exists()


def test_alembic_requires_explicit_config(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_ROOT / "alembic.ini"),
            "upgrade",
            "head",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "config-dir" in result.stderr
    assert not list(tmp_path.iterdir())


async def test_two_temporary_databases_are_isolated(
    database: Database,
    tmp_path: Path,
) -> None:
    other_config = write_database_config(tmp_path / "other")
    migrate(other_config, "upgrade", "head")
    async with database.transaction() as session:
        await session.execute(text("CREATE TABLE test_private (id INTEGER)"))
        await session.execute(text("INSERT INTO test_private VALUES (1)"))
    async with open_database(other_config) as other:
        async with other.transaction() as session:
            assert await SQLiteRepository(session).schema_revision() == SchemaRevision(HEAD)
            assert (
                await session.scalar(
                    text("SELECT count(*) FROM sqlite_master WHERE name='test_private'")
                )
                == 0
            )
