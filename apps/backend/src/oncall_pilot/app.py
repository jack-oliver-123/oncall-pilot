"""创建 On-call Pilot FastAPI 应用。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request

from oncall_pilot.generated_contracts import OPERATION_DOCS, ApiFailure, HealthResponse
from oncall_pilot.project_config import load_project_config
from oncall_pilot.protocol import install_protocol, success


async def _health(request: Request) -> HealthResponse:
    return HealthResponse.model_validate(
        success({"status": "ok"}, request.state.request_id).model_dump()
    )


def create_app(config_dir: Path | None = None) -> FastAPI:
    """加载本地配置并创建无外部连接的应用。"""

    resolved_config_dir = config_dir if config_dir is not None else Path.cwd() / "config"
    project_config = load_project_config(resolved_config_dir)
    app = FastAPI(title="On-call Pilot", version="0.2.0")
    app.state.project_config = project_config
    install_protocol(app)
    app.add_api_route(
        "/health",
        _health,
        methods=["GET"],
        response_model=HealthResponse,
        operation_id="getHealth",
        tags=["foundation"],
        openapi_extra=OPERATION_DOCS["getHealth"],
        responses={
            422: {"model": ApiFailure},
            500: {"model": ApiFailure},
            "default": {"model": ApiFailure},
        },
    )
    return app
