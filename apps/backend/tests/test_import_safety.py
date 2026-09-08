from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_importing_all_package_modules_has_no_application_io_side_effects() -> None:
    script = r'''
import importlib
import pkgutil
import socket
import sqlite3
from pathlib import Path

import fastapi
import httpx
import sqlalchemy
import sqlalchemy.ext.asyncio
import uvicorn

def forbidden(*args, **kwargs):
    raise AssertionError("module import 触发了应用 I/O")

Path.open = forbidden
Path.read_text = forbidden
Path.write_text = forbidden
socket.create_connection = forbidden
sqlite3.connect = forbidden
fastapi.FastAPI = forbidden
httpx.Client = forbidden
httpx.AsyncClient = forbidden
sqlalchemy.create_engine = forbidden
sqlalchemy.ext.asyncio.create_async_engine = forbidden
uvicorn.run = forbidden

import oncall_pilot

for module in pkgutil.walk_packages(oncall_pilot.__path__, oncall_pilot.__name__ + "."):
    importlib.import_module(module.name)
'''
    database_files_before = set(BACKEND_ROOT.rglob("*.db"))

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert set(BACKEND_ROOT.rglob("*.db")) == database_files_before
