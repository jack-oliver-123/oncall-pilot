"""后台任务 HTTP adapter；所有 DTO 来自 canonical OpenAPI。"""

from copy import deepcopy
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from oncall_pilot.auth.api import current_user, protected_router, require_owned_resource
from oncall_pilot.background_jobs import BackgroundJobRepository, InvalidJobState, Job, JobNotFound
from oncall_pilot.generated_contracts import (
    OPERATION_DOCS,
    ApiFailure,
    BackgroundJob,
    BackgroundJobListResponse,
    BackgroundJobResponse,
)
from oncall_pilot.memory.scope import CurrentUser
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.protocol import ApiException


def _public(job: Job) -> BackgroundJob:
    fields = job.model_dump()
    wire: dict[str, object] = {}
    for name, value in fields.items():
        parts = name.split("_")
        wire[parts[0] + "".join(part.title() for part in parts[1:])] = value
    wire["payload"] = job.payload_value()
    return BackgroundJob.model_validate(wire)


def _database(request: Request) -> Database:
    return cast(Database, request.app.state.background_database)


async def list_jobs(
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> BackgroundJobListResponse:
    async with _database(request).transaction() as session:
        jobs = await BackgroundJobRepository(session).list(owner_user_id=user.user_id)
    return BackgroundJobListResponse.model_validate(
        {
            "ok": True,
            "data": [_public(job) for job in jobs],
            "meta": {"requestId": request.state.request_id},
        }
    )


async def _operate(
    id: str, request: Request, user: CurrentUser, action: str
) -> BackgroundJobResponse:
    try:
        async with _database(request).transaction() as session:
            repo = BackgroundJobRepository(session)
            if action == "cancel":
                job = await repo.cancel(id, owner_user_id=user.user_id)
            elif action == "retry":
                job = await repo.retry(id, owner_user_id=user.user_id)
            else:
                job = require_owned_resource(await repo.get(id, owner_user_id=user.user_id))
    except JobNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    except InvalidJobState:
        raise ApiException("BUSINESS_CONFLICT") from None
    return BackgroundJobResponse.model_validate(
        {
            "ok": True,
            "data": _public(job),
            "meta": {"requestId": request.state.request_id},
        }
    )


async def get_job(
    id: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> BackgroundJobResponse:
    return await _operate(id, request, user, "get")


async def cancel_job(
    id: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> BackgroundJobResponse:
    return await _operate(id, request, user, "cancel")


async def retry_job(
    id: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> BackgroundJobResponse:
    return await _operate(id, request, user, "retry")


def install_background_jobs(app: FastAPI) -> None:
    router = protected_router()
    for path, method, endpoint, model, operation in (
        ("/background-jobs", "GET", list_jobs, BackgroundJobListResponse, "listBackgroundJobs"),
        ("/background-jobs/{id}", "GET", get_job, BackgroundJobResponse, "getBackgroundJob"),
        (
            "/background-jobs/{id}:cancel",
            "POST",
            cancel_job,
            BackgroundJobResponse,
            "cancelBackgroundJob",
        ),
        (
            "/background-jobs/{id}:retry",
            "POST",
            retry_job,
            BackgroundJobResponse,
            "retryBackgroundJob",
        ),
    ):
        responses: dict[int | str, dict[str, object]] = {
            422: {"model": ApiFailure},
            500: {"model": ApiFailure},
            "default": {"model": ApiFailure},
        }
        if method == "POST":
            responses[409] = {"model": ApiFailure}
        docs = deepcopy(OPERATION_DOCS[operation])
        # path 参数由 FastAPI 从签名生成；避免 openapi_extra 再追加一份。
        docs["parameters"] = [p for p in docs["parameters"] if p["in"] != "path"]
        router.add_api_route(
            path,
            endpoint,
            methods=[method],
            response_model=model,
            operation_id=operation,
            tags=["background-jobs"],
            openapi_extra=docs,
            responses=responses,
        )
    app.include_router(router)
