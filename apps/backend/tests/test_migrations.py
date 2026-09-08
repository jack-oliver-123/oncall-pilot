from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_runs_only_when_given_an_explicit_config_directory(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "project.json").write_text(
        json.dumps({"database": {"url": "sqlite+aiosqlite:///var/migration-test.db"}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "-x",
            f"config-dir={config_dir}",
            "current",
        ],
        cwd=BACKEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "var/migration-test.db").is_file()
    assert not list((BACKEND_ROOT / "migrations/versions").glob("*.py"))
