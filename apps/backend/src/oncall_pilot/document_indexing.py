"""在 P09 持久租约内执行 P10/P06/P07 文档索引。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypeVar
from uuid import uuid4

from oncall_pilot.background_jobs import BackgroundJobRepository, LeaseLost
from oncall_pilot.background_runtime import JobContext
from oncall_pilot.index_tasks import INDEX_RESOURCE, IndexTaskRepository
from oncall_pilot.knowledge import (
    DocumentChunkingService,
    DocumentNotFound,
    KnowledgeDocumentRepository,
)
from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.llm.qwen import open_qwen_provider
from oncall_pilot.vector_store import VectorChunk


class Embeddings(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class IndexVectors(Protocol):
    def initialize(self) -> None: ...
    def delete_document(
        self, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> int: ...
    def insert_chunks(self, chunks: Sequence[VectorChunk], *, owner_user_id: str) -> None: ...


ProviderFactory = Callable[[], AbstractAsyncContextManager[Embeddings]]
T = TypeVar("T")


async def bounded_thread(call: Callable[[], T]) -> T:
    # asyncio 取消不能强杀 SDK 线程，必须等有界 I/O 收尾再释放执行槽。
    task = asyncio.create_task(asyncio.to_thread(call))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise


def qwen_factory(config_dir: Path) -> ProviderFactory:
    @asynccontextmanager
    async def factory():  # type annotation below is inferred from the typed yield
        config = load_llm_config(config_dir)
        async with open_qwen_provider(config) as provider:
            yield provider

    return factory


class IndexCancelled(Exception):
    pass


class DocumentIndexHandler:
    def __init__(
        self,
        provider: ProviderFactory,
        vectors: IndexVectors,
        splitter: DocumentChunkingService | None = None,
    ) -> None:
        self.provider = provider
        self.vectors = vectors
        self.splitter = splitter or DocumentChunkingService()

    async def __call__(self, context: JobContext) -> None:
        job = context.job
        owner = context.scope.owner_user_id
        payload = job.payload_value()
        if (
            job.resource_type != INDEX_RESOURCE
            or job.resource_id is None
            or not isinstance(payload, dict)
            or not isinstance(payload.get("knowledgeBaseId"), str)
            or not isinstance(payload.get("documentId"), str)
        ):
            raise DocumentNotFound
        kb = str(payload["knowledgeBaseId"])
        document_id = str(payload["documentId"])

        async def checkpoint() -> None:
            async with context.database.transaction() as session:
                current = await BackgroundJobRepository(session).get(job.id, owner_user_id=owner)
                if current is None or job.lease_owner is None:
                    raise LeaseLost
                BackgroundJobRepository.require_lease(current, job.lease_owner)
                if current.cancel_requested_at or context.cancelled.is_set():
                    raise IndexCancelled
                await IndexTaskRepository(session).get(
                    job.resource_id or "",
                    owner_user_id=owner,
                    knowledge_base_id=kb,
                    document_id=document_id,
                )

        reason = "文档读取失败。"
        try:
            await checkpoint()
            async with context.database.transaction() as session:
                document = await KnowledgeDocumentRepository(session).get(
                    document_id, owner_user_id=owner, knowledge_base_id=kb
                )
            if document is None:
                raise DocumentNotFound
            reason = "文档切分失败。"
            chunks = await bounded_thread(lambda: self.splitter.chunks(document))
            if not chunks:
                raise ValueError("文档没有可索引片段")
            await checkpoint()
            reason = "文档向量生成失败。"
            async with self.provider() as provider:
                vectors = await provider.embed_documents([chunk.text for chunk in chunks])
            if len(vectors) != len(chunks):
                raise ValueError("向量数量不匹配")
            created = datetime.now(timezone.utc)
            records = [
                VectorChunk(
                    chunk_id=str(uuid4()),
                    document_id=document.id,
                    knowledge_base_id=kb,
                    content=chunk.text,
                    source=document.filename,
                    created_at=created,
                    metadata={
                        **chunk.metadata(),
                        "index": chunk.index,
                        "chunkingConfig": document.chunking_config.public(),
                    },
                    vector=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            # 在删除旧向量之前校验整批，不能让错误向量清空可用索引。
            for record in records:
                record.row(owner_user_id=owner)
            await checkpoint()
            reason = "向量存储初始化失败。"
            await bounded_thread(self.vectors.initialize)
            await checkpoint()
            reason = "旧向量清理失败。"
            await bounded_thread(
                lambda: self.vectors.delete_document(
                    owner_user_id=owner, knowledge_base_id=kb, document_id=document_id
                )
            )
            await checkpoint()
            reason = "文档向量写入失败。"
            await bounded_thread(lambda: self.vectors.insert_chunks(records, owner_user_id=owner))
            await checkpoint()
        except IndexCancelled:
            return
        except LeaseLost:
            raise
        except Exception:
            context.failure_reason = reason
            raise RuntimeError(reason) from None
