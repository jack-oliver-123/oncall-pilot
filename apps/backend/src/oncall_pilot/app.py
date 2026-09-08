"""创建 On-call Pilot FastAPI 应用。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from oncall_pilot.project_config import load_project_config


class HealthResponse(BaseModel):
    """进程存活响应。"""

    status: Literal["ok"] = "ok"


async def _health() -> HealthResponse:
    return HealthResponse()


def create_app(config_dir: Path | None = None) -> FastAPI:
    """加载本地配置并创建无外部连接的应用。"""

    resolved_config_dir = config_dir if config_dir is not None else Path.cwd() / "config"
    project_config = load_project_config(resolved_config_dir)
    app = FastAPI(title="On-call Pilot")
    app.state.project_config = project_config
    app.add_api_route("/health", _health, methods=["GET"], response_model=HealthResponse)
    return app
