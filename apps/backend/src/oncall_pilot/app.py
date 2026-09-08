"""创建 On-call Pilot FastAPI 应用。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from oncall_pilot.auth.api import install_auth
from oncall_pilot.auth.passwords import PasswordManager
from oncall_pilot.auth.repository import auth_transaction
from oncall_pilot.auth.service import AuthService
from oncall_pilot.generated_contracts import OPERATION_DOCS, ApiFailure, HealthResponse
from oncall_pilot.memory.sqlite import open_database
from oncall_pilot.project_config import load_project_config
from oncall_pilot.protocol import install_protocol, success


async def _health(request: Request) -> HealthResponse:
    return HealthResponse.model_validate(
        success({"status": "ok"}, request.state.request_id).model_dump()
    )


def create_app(config_dir: Path | None = None) -> FastAPI:
    """加载本地配置并创建无外部连接的应用。"""

    resolved_config_dir = (
        config_dir if config_dir is not None else Path.cwd() / "config"
    ).resolve()
    project_config = load_project_config(resolved_config_dir)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        async with open_database(resolved_config_dir) as database:
            passwords = await run_in_threadpool(PasswordManager)
            application.state.auth_service = AuthService(
                lambda: auth_transaction(database), passwords
            )
            try:
                yield
            finally:
                del application.state.auth_service

    app = FastAPI(title="On-call Pilot", version="0.2.0", lifespan=lifespan)
    app.state.project_config = project_config
    install_protocol(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
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
    install_auth(app)
    return app
