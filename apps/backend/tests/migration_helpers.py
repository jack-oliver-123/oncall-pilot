"""测试专用迁移入口；所有调用方显式传入临时配置。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
HEAD = "0001_persistence_foundation"


def write_database_config(root: Path, url: str = "sqlite+aiosqlite:///var/test.db") -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "project.json").write_text(
        json.dumps({"database": {"url": url}}), encoding="utf-8"
    )
    return config_dir


def migrate(config_dir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_ROOT / "alembic.ini"),
            "-x",
            f"config-dir={config_dir}",
            *arguments,
        ],
        cwd=config_dir.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result
