"""文档索引 HTTP adapter，统一 owner 与 envelope。"""

from copy import deepcopy
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from oncall_pilot.auth.api import current_user, protected_router
from oncall_pilot.background_jobs import InvalidJobState
from oncall_pilot.generated_contracts import OPERATION_DOCS, ApiFailure, DocumentIndexTaskResponse
from oncall_pilot.index_tasks import IndexTaskRepository
from oncall_pilot.knowledge import DocumentNotFound
from oncall_pilot.memory.scope import CurrentUser
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.protocol import ApiException, success


async def operate(
    kb: str, document: str, task: str | None, action: str, request: Request, user: CurrentUser
) -> DocumentIndexTaskResponse:
    database = cast(Database, request.app.state.background_database)
    try:
        async with database.transaction() as session:
            repo = IndexTaskRepository(session)
            scope = {
                "owner_user_id": user.user_id,
                "knowledge_base_id": kb,
                "document_id": document,
            }
            if action == "create":
                result = await repo.create(**scope)
            elif action == "retry":
                result = await repo.create(**scope, retry_of_task_id=task)
            elif action == "cancel":
                result = await repo.cancel(task or "", **scope)
            else:
                result = await repo.get(task or "", **scope)
    except DocumentNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    except InvalidJobState:
        raise ApiException("BUSINESS_CONFLICT") from None
    return DocumentIndexTaskResponse.model_validate(
        success(result.public(), request.state.request_id).model_dump()
    )


async def create_task(
    kb: str, document: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> DocumentIndexTaskResponse:
    return await operate(kb, document, None, "create", request, user)


async def get_task(
    kb: str,
    document: str,
    task: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> DocumentIndexTaskResponse:
    return await operate(kb, document, task, "get", request, user)


async def retry_task(
    kb: str,
    document: str,
    task: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> DocumentIndexTaskResponse:
    return await operate(kb, document, task, "retry", request, user)


async def cancel_task(
    kb: str,
    document: str,
    task: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> DocumentIndexTaskResponse:
    return await operate(kb, document, task, "cancel", request, user)


def install_index_tasks(app: FastAPI) -> None:
    router = protected_router()
    base = "/knowledge-bases/{kb}/documents/{document}/index-tasks"
    for suffix, method, endpoint, operation in [
        ("", "POST", create_task, "createDocumentIndexTask"),
        ("/{task}", "GET", get_task, "getDocumentIndexTask"),
        ("/{task}:retry", "POST", retry_task, "retryDocumentIndexTask"),
        ("/{task}:cancel", "POST", cancel_task, "cancelDocumentIndexTask"),
    ]:
        docs = deepcopy(OPERATION_DOCS[operation])
        docs["parameters"] = [p for p in docs["parameters"] if p["in"] != "path"]
        responses: dict[int | str, dict[str, object]] = {
            422: {"model": ApiFailure},
            500: {"model": ApiFailure},
            "default": {"model": ApiFailure},
        }
        if method == "POST":
            responses[409] = {"model": ApiFailure}
        router.add_api_route(
            base + suffix,
            endpoint,
            methods=[method],
            response_model=DocumentIndexTaskResponse,
            operation_id=operation,
            tags=["knowledge"],
            openapi_extra=docs,
            responses=responses,
        )
    app.include_router(router)
