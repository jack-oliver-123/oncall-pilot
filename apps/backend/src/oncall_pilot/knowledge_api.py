"""知识文档 HTTP adapter。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Annotated, cast

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from oncall_pilot.auth.api import current_user, protected_router
from oncall_pilot.generated_contracts import (
    OPERATION_DOCS,
    ApiFailure,
    ChunkPreviewResponse,
    KnowledgeBaseListResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
)
from oncall_pilot.knowledge import (
    DocumentChunkingService,
    DocumentConflict,
    DocumentNotFound,
    KnowledgeDocumentService,
    VectorCleanupError,
    require_default_kb,
)
from oncall_pilot.knowledge_chunking import ChunkingConfig, ChunkingError, normalize_chunking_config
from oncall_pilot.knowledge_documents import MAX_UPLOAD_BYTES, DocumentInputError
from oncall_pilot.memory.scope import CurrentUser
from oncall_pilot.protocol import ApiException, success


def _service(request: Request) -> KnowledgeDocumentService:
    return cast(KnowledgeDocumentService, request.app.state.knowledge_service)


class KnowledgeUploadLimit:
    """在 multipart 解析器写临时文件前限制累计请求字节；正文另做精确校验。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not scope.get("path", "").startswith("/knowledge-bases/")
        ):
            await self.app(scope, receive, send)
            return
        total = 0

        async def limited_receive() -> Message:
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > MAX_UPLOAD_BYTES + 65536:
                    raise MultiPartException("上传请求超过大小限制")
            return message

        await self.app(scope, limited_receive, send)


def _config(value: str | None) -> ChunkingConfig:
    try:
        result: object = {} if value is None else json.loads(value)
        if result is None:
            raise ChunkingError("切分配置必须为对象")
        return normalize_chunking_config(result)
    except (json.JSONDecodeError, ChunkingError) as exc:
        raise ApiException("VALIDATION_BAD_REQUEST") from exc


async def list_kbs(
    request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> KnowledgeBaseListResponse:
    rows = await _service(request).list_kbs(owner_user_id=user.user_id)
    return KnowledgeBaseListResponse.model_validate(
        success(
            [row.public() for row in rows],
            request.state.request_id,
        ).model_dump()
    )


async def list_documents(
    kb: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> KnowledgeDocumentListResponse:
    try:
        rows = await _service(request).list(owner_user_id=user.user_id, knowledge_base_id=kb)
    except DocumentNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    return KnowledgeDocumentListResponse.model_validate(
        success([row.public() for row in rows], request.state.request_id).model_dump()
    )


async def upload_document(
    kb: str,
    request: Request,
    file: Annotated[UploadFile, File(...)],
    user: Annotated[CurrentUser, Depends(current_user)],
    overwrite: Annotated[bool, Form()] = False,
    chunking_config: Annotated[str | None, Form(alias="chunkingConfig")] = None,
) -> KnowledgeDocumentResponse:
    try:
        require_default_kb(owner_user_id=user.user_id, knowledge_base_id=kb)
        form = await request.form()
        if set(form) - {"file", "overwrite", "chunkingConfig"} or any(
            len(form.getlist(key)) != 1 for key in form
        ):
            raise ApiException("VALIDATION_BAD_REQUEST")
        config = _config(chunking_config)
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        document = await _service(request).upload(
            file.filename or "",
            file.content_type,
            content,
            owner_user_id=user.user_id,
            knowledge_base_id=kb,
            config=config,
            overwrite=overwrite,
        )
    except DocumentNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    except (DocumentInputError, ChunkingError):
        raise ApiException("VALIDATION_BAD_REQUEST") from None
    except DocumentConflict:
        raise ApiException("BUSINESS_CONFLICT") from None
    except VectorCleanupError:
        raise ApiException("SYSTEM_INTERNAL_ERROR") from None
    finally:
        await file.close()
    return KnowledgeDocumentResponse.model_validate(
        success(document.public(), request.state.request_id).model_dump()
    )


async def get_document(
    kb: str, document: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> KnowledgeDocumentResponse:
    try:
        row = await _service(request).get(
            document, owner_user_id=user.user_id, knowledge_base_id=kb
        )
    except DocumentNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    return KnowledgeDocumentResponse.model_validate(
        success(row.public(), request.state.request_id).model_dump()
    )


async def delete_document(
    kb: str, document: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> KnowledgeDocumentResponse:
    try:
        row = await _service(request).delete(
            document, owner_user_id=user.user_id, knowledge_base_id=kb
        )
    except VectorCleanupError:
        raise ApiException("SYSTEM_INTERNAL_ERROR") from None
    except DocumentNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    return KnowledgeDocumentResponse.model_validate(
        success(row.public(), request.state.request_id).model_dump()
    )


async def preview_document(
    kb: str, document: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> ChunkPreviewResponse:
    try:
        row = await _service(request).get(
            document, owner_user_id=user.user_id, knowledge_base_id=kb
        )
    except DocumentNotFound:
        raise ApiException("AUTH_FORBIDDEN") from None
    preview = await run_in_threadpool(DocumentChunkingService().preview, row)
    return ChunkPreviewResponse.model_validate(
        success(preview, request.state.request_id).model_dump()
    )


def install_knowledge(app: FastAPI) -> None:
    app.add_middleware(KnowledgeUploadLimit)
    router = protected_router()
    entries = [
        ("/knowledge-bases", "GET", list_kbs, KnowledgeBaseListResponse, "listKnowledgeBases"),
        (
            "/knowledge-bases/{kb}/documents",
            "GET",
            list_documents,
            KnowledgeDocumentListResponse,
            "listKnowledgeDocuments",
        ),
        (
            "/knowledge-bases/{kb}/documents",
            "POST",
            upload_document,
            KnowledgeDocumentResponse,
            "uploadKnowledgeDocument",
        ),
        (
            "/knowledge-bases/{kb}/documents/{document}",
            "GET",
            get_document,
            KnowledgeDocumentResponse,
            "getKnowledgeDocument",
        ),
        (
            "/knowledge-bases/{kb}/documents/{document}",
            "DELETE",
            delete_document,
            KnowledgeDocumentResponse,
            "deleteKnowledgeDocument",
        ),
        (
            "/knowledge-bases/{kb}/documents/{document}/chunk-preview",
            "GET",
            preview_document,
            ChunkPreviewResponse,
            "previewKnowledgeDocumentChunks",
        ),
    ]
    for path, method, endpoint, model, operation in entries:
        responses: dict[int | str, dict[str, object]] = {
            422: {"model": ApiFailure},
            500: {"model": ApiFailure},
            "default": {"model": ApiFailure},
        }
        if method == "POST":
            responses[400] = {"model": ApiFailure}
            responses[409] = {"model": ApiFailure}
        docs = deepcopy(OPERATION_DOCS[operation])
        docs["parameters"] = [p for p in docs["parameters"] if p["in"] != "path"]
        router.add_api_route(
            path,
            endpoint,
            methods=[method],
            response_model=model,
            operation_id=operation,
            tags=["knowledge"],
            openapi_extra=docs,
            responses=responses,
        )
    app.include_router(router)
