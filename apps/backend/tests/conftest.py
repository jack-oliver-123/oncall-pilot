from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from migration_helpers import migrate, write_database_config

from oncall_pilot.memory.sqlite import Database, open_database


@pytest.fixture
def migrated_config(tmp_path: Path) -> Path:
    config_dir = write_database_config(tmp_path)
    migrate(config_dir, "upgrade", "head")
    return config_dir


@pytest.fixture
async def database(migrated_config: Path) -> AsyncGenerator[Database]:
    async with open_database(migrated_config) as database:
        yield database
