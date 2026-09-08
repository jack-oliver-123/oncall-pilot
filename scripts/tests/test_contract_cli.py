"""合同 CLI 在 Windows 重定向输出下仍提供可读的中文反馈。"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ContractCliTests(unittest.TestCase):
    def test_check_outputs_utf8_under_legacy_windows_encoding(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1252"
        environment["PYTHONUTF8"] = "0"
        result = subprocess.run(
            [sys.executable, "scripts/generate_contracts.py", "--check"],
            cwd=ROOT, env=environment, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertIn("合同生成物检查通过", result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
