from __future__ import annotations

import subprocess
import sys


def test_module_entrypoint_documents_explicit_process_arguments() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "oncall_pilot", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--config-dir" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
