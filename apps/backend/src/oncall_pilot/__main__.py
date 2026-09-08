"""On-call Pilot 后端主机进程入口。"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import uvicorn

from oncall_pilot.app import create_app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动 On-call Pilot 后端")
    parser.add_argument("--config-dir", required=True, help="本地 JSON 配置目录")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", default=8000, type=int, help="监听端口")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """解析显式进程参数并启动 Uvicorn。"""

    arguments = _build_parser().parse_args(argv)
    config_dir = Path(cast(str, arguments.config_dir))
    host = cast(str, arguments.host)
    port = cast(int, arguments.port)
    uvicorn.run(create_app(config_dir), host=host, port=port)


if __name__ == "__main__":
    main()
