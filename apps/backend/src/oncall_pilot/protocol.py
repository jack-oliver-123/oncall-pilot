"""HTTP/SSE 协议适配；wire 声明全部来自生成合同。"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import JsonValue, TypeAdapter, ValidationError
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from oncall_pilot.generated_contracts import (
    ERROR_CATALOG,
    ApiError,
    ApiFailure,
    ApiSuccess,
    ErrorCode,
    RequestId,
    SseEvent,
)


def success(data: JsonValue, request_id: str) -> ApiSuccess:
    """保留任意 JSON 成功数据，包括 null 与 false。"""
    return ApiSuccess.model_validate({"ok": True, "data": data, "meta": {"requestId": request_id}})


def api_error(code: ErrorCode, details: dict[str, JsonValue] | None = None) -> ApiError:
    """只允许目录错误及调用者明确选择公开的 details。"""
    payload = dict(ERROR_CATALOG[code])
    if details is not None:
        payload["details"] = details
    return TypeAdapter[ApiError](ApiError).validate_python(payload)


def failure(error: ApiError, request_id: str) -> JSONResponse:
    envelope = ApiFailure.model_validate(
        {"ok": False, "error": error, "meta": {"requestId": request_id}}
    )
    return JSONResponse(
        envelope.model_dump(mode="json", exclude_unset=True),
        status_code=error.httpStatus,
        headers={"X-Request-ID": request_id},
    )


class ApiException(Exception):
    """业务层传递已登记的安全错误，不携带自由格式响应。"""

    def __init__(self, code: ErrorCode, details: dict[str, JsonValue] | None = None) -> None:
        self.error = api_error(code, details)
        super().__init__(self.error.message)


async def api_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiException)
    response = failure(exc.error, request.state.request_id)
    if exc.error.httpStatus == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    issues: list[JsonValue] = []
    for issue in exc.errors():
        issues.append(
            {"path": list(issue["loc"]), "type": issue["type"], "message": "字段值不符合要求。"}
        )
    return failure(
        api_error("VALIDATION_REQUEST_INVALID", {"issues": issues}), request.state.request_id
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    code: ErrorCode = "SYSTEM_INTERNAL_ERROR"
    for key, value in ERROR_CATALOG.items():
        if value["httpStatus"] == exc.status_code:
            code = key
            break
    response = failure(api_error(code), request.state.request_id)
    for name, value in (exc.headers or {}).items():
        if name.lower() in {"allow", "www-authenticate", "retry-after"}:
            response.headers[name] = value
    return response


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id: str = request.state.request_id
    logging.getLogger(__name__).error("请求处理失败 requestId=%s", request_id, exc_info=exc)
    return failure(api_error("SYSTEM_INTERNAL_ERROR"), request_id)


class RequestIdMiddleware:
    """纯 ASGI 包装，保证异常和流响应只发送一次响应头。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        try:
            request_id = TypeAdapter[str](RequestId).validate_python(headers.get("x-request-id"))
        except ValidationError:
            request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def send_with_id(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                outgoing = MutableHeaders(scope=message)
                outgoing["X-Request-ID"] = request_id
                if scope.get("path", "").startswith("/auth/"):
                    outgoing["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            if started:
                raise
            response = await unexpected_exception_handler(Request(scope), exc)
            await response(scope, receive, send_with_id)


def install_protocol(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(ApiException, api_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)


def serialize_sse(event: SseEvent) -> bytes:
    """协议事件序列化为一帧 UTF-8 SSE，不接受私有事件字典。"""
    validated = TypeAdapter[SseEvent](SseEvent).validate_python(event)
    data = json.dumps(
        validated.model_dump(mode="json", exclude_unset=True), ensure_ascii=False, allow_nan=False
    )
    return f"id: {validated.id}\nevent: {validated.type}\ndata: {data}\n\n".encode()
