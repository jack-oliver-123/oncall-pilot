from __future__ import annotations

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("console_encoding", ["utf-8", "cp1252"])
def test_module_entrypoint_documents_explicit_process_arguments(console_encoding: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "oncall_pilot", "--help"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": console_encoding},
    )

    assert result.returncode == 0
    assert "--config-dir" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "本地 JSON 配置目录" in result.stdout
