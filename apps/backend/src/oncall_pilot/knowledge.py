"""知识文档记录、归属查询及事务外向量清理。"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import JsonValue
from sqlalchemy import RowMapping, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from oncall_pilot.knowledge_chunking import (
    MAX_PREVIEW_CHUNKS,
    ChunkingConfig,
    DocumentChunk,
    chunk_document_text,
    normalize_chunking_config,
    preview_chunks,
)
from oncall_pilot.knowledge_documents import extract_document
from oncall_pilot.knowledge_models import documents, knowledge_bases
from oncall_pilot.memory.scope import OwnerScope, require_scope_id
from oncall_pilot.memory.sqlite import Database


class DocumentConflict(Exception):
    """同一 owner/KB 的活动或待清理 hash 已存在。"""


class DocumentNotFound(Exception):
    """资源不属于当前 scope 或已不存在。"""


class VectorCleanupError(Exception):
    """清理未完成；隐藏 provider 异常，允许同一资源重试。"""


class VectorDeletion(Protocol):
    def delete_document(
        self, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    id: str
    owner_user_id: str
    created_at: datetime

    def public(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "ownerUserId": self.owner_user_id,
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    owner_user_id: str
    knowledge_base_id: str
    filename: str
    size: int
    mime_type: str
    sha256: str
    uploaded_at: datetime
    index_status: str
    chunking_config: ChunkingConfig
    body: str
    deleted_at: datetime | None = None
    vectors_cleaned: bool = False

    def public(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "ownerUserId": self.owner_user_id,
            "knowledgeBaseId": self.knowledge_base_id,
            "filename": self.filename,
            "size": self.size,
            "mimeType": self.mime_type,
            "sha256": self.sha256,
            "uploadedAt": self.uploaded_at.isoformat(),
            "indexStatus": self.index_status,
            "chunkingConfig": self.chunking_config.public(),
        }


def default_knowledge_base_id(owner_user_id: str) -> str:
    require_scope_id(owner_user_id)
    return str(uuid5(NAMESPACE_URL, f"oncall-pilot:knowledge-base:{owner_user_id}"))


def require_default_kb(*, owner_user_id: str, knowledge_base_id: str) -> None:
    if default_knowledge_base_id(owner_user_id) != knowledge_base_id:
        raise DocumentNotFound


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _document(row: RowMapping) -> Document:
    return Document(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        knowledge_base_id=row["knowledge_base_id"],
        filename=row["filename"],
        size=row["size"],
        mime_type=row["mime_type"],
        sha256=row["sha256"],
        uploaded_at=_time(row["uploaded_at"]),
        index_status=row["index_status"],
        chunking_config=normalize_chunking_config(row["chunking_config"]),
        body=row["body"],
        deleted_at=None if row["deleted_at"] is None else _time(row["deleted_at"]),
        vectors_cleaned=row["vectors_cleaned"],
    )


class KnowledgeRepositoryPort(Protocol):
    async def ensure_default_kb(self, *, owner_user_id: str) -> KnowledgeBase: ...
    async def list(self, *, owner_user_id: str, knowledge_base_id: str) -> list[Document]: ...
    async def get(
        self,
        document_id: str,
        *,
        owner_user_id: str,
        knowledge_base_id: str,
        include_deleted: bool = False,
    ) -> Document | None: ...
    async def find_hash(
        self, sha256: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> Document | None: ...
    async def add(self, document: Document, *, owner_user_id: str) -> Document: ...
    async def soft_delete(
        self, document_id: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> Document | None: ...
    async def confirm_cleanup(
        self, document_id: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> None: ...


KnowledgeTransactions = Callable[[], AbstractAsyncContextManager[KnowledgeRepositoryPort]]


@asynccontextmanager
async def knowledge_transaction(database: Database) -> AsyncGenerator[KnowledgeRepositoryPort]:
    async with database.transaction() as session:
        yield KnowledgeDocumentRepository(session)


class KnowledgeDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_default_kb(self, *, owner_user_id: str) -> KnowledgeBase:
        kb_id = default_knowledge_base_id(owner_user_id)
        # INSERT 首先获取 SQLite 写锁；并发首次访问不会发生读锁升级。
        await self._session.execute(
            insert(knowledge_bases)
            .values(
                id=kb_id,
                owner_user_id=owner_user_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            .on_conflict_do_nothing(index_elements=[knowledge_bases.c.id])
        )
        row = (
            (
                await self._session.execute(
                    select(knowledge_bases).where(
                        knowledge_bases.c.id == kb_id,
                        knowledge_bases.c.owner_user_id == owner_user_id,
                    )
                )
            )
            .mappings()
            .one()
        )
        return KnowledgeBase(row["id"], row["owner_user_id"], _time(row["created_at"]))

    async def list(self, *, owner_user_id: str, knowledge_base_id: str) -> list[Document]:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        rows = (
            await self._session.execute(
                select(documents)
                .where(
                    documents.c.owner_user_id == owner_user_id,
                    documents.c.knowledge_base_id == knowledge_base_id,
                    documents.c.deleted_at.is_(None),
                )
                .order_by(documents.c.uploaded_at, documents.c.id)
            )
        ).mappings()
        return [_document(row) for row in rows]

    async def get(
        self,
        document_id: str,
        *,
        owner_user_id: str,
        knowledge_base_id: str,
        include_deleted: bool = False,
    ) -> Document | None:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        statement = select(documents).where(
            documents.c.id == document_id,
            documents.c.owner_user_id == owner_user_id,
            documents.c.knowledge_base_id == knowledge_base_id,
        )
        if not include_deleted:
            statement = statement.where(documents.c.deleted_at.is_(None))
        row = (await self._session.execute(statement)).mappings().first()
        return None if row is None else _document(row)

    async def find_hash(
        self, sha256: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> Document | None:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        row = (
            (
                await self._session.execute(
                    select(documents).where(
                        documents.c.sha256 == sha256,
                        documents.c.owner_user_id == owner_user_id,
                        documents.c.knowledge_base_id == knowledge_base_id,
                        documents.c.vectors_cleaned.is_(False),
                    )
                )
            )
            .mappings()
            .first()
        )
        return None if row is None else _document(row)

    async def add(self, document: Document, *, owner_user_id: str) -> Document:
        OwnerScope(owner_user_id).require_owner(document.owner_user_id)
        require_default_kb(
            owner_user_id=owner_user_id, knowledge_base_id=document.knowledge_base_id
        )
        try:
            await self._session.execute(
                documents.insert().values(
                    id=document.id,
                    owner_user_id=owner_user_id,
                    knowledge_base_id=document.knowledge_base_id,
                    filename=document.filename,
                    size=document.size,
                    mime_type=document.mime_type,
                    sha256=document.sha256,
                    uploaded_at=document.uploaded_at.isoformat(),
                    index_status=document.index_status,
                    chunking_config=document.chunking_config.public(),
                    body=document.body,
                    deleted_at=None,
                    vectors_cleaned=False,
                )
            )
        except IntegrityError as exc:
            if "UNIQUE constraint failed: knowledge_documents." in str(exc.orig):
                raise DocumentConflict from None
            raise
        return document

    async def soft_delete(
        self, document_id: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> Document | None:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        await self._session.execute(
            update(documents)
            .where(
                documents.c.id == document_id,
                documents.c.owner_user_id == owner_user_id,
                documents.c.knowledge_base_id == knowledge_base_id,
                documents.c.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(timezone.utc).isoformat())
        )
        return await self.get(
            document_id,
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            include_deleted=True,
        )

    async def confirm_cleanup(
        self, document_id: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> None:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        await self._session.execute(
            update(documents)
            .where(
                documents.c.id == document_id,
                documents.c.owner_user_id == owner_user_id,
                documents.c.knowledge_base_id == knowledge_base_id,
                documents.c.deleted_at.is_not(None),
            )
            .values(vectors_cleaned=True)
        )


class DocumentChunkingService:
    def chunks(self, document: Document, *, limit: int | None = None) -> list[DocumentChunk]:
        return [
            replace(
                chunk,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                owner_user_id=document.owner_user_id,
            )
            for chunk in chunk_document_text(document.body, document.chunking_config, limit=limit)
        ]

    def preview(self, document: Document) -> list[JsonValue]:
        return preview_chunks(self.chunks(document, limit=MAX_PREVIEW_CHUNKS))


class KnowledgeDocumentService:
    def __init__(self, transactions: KnowledgeTransactions, vector: VectorDeletion) -> None:
        self._transactions = transactions
        self._vector = vector

    async def list_kbs(self, *, owner_user_id: str) -> list[KnowledgeBase]:
        async with self._transactions() as repository:
            return [await repository.ensure_default_kb(owner_user_id=owner_user_id)]

    async def list(self, *, owner_user_id: str, knowledge_base_id: str) -> list[Document]:
        async with self._transactions() as repository:
            return await repository.list(
                owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
            )

    async def get(
        self, document_id: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> Document:
        async with self._transactions() as repository:
            result = await repository.get(
                document_id, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
            )
        if result is None:
            raise DocumentNotFound
        return result

    async def upload(
        self,
        filename: str,
        content_type: str | None,
        content: bytes,
        *,
        owner_user_id: str,
        knowledge_base_id: str,
        config: ChunkingConfig,
        overwrite: bool = False,
    ) -> Document:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        config = normalize_chunking_config(config.public())
        name, size, mime, digest, body = await run_in_threadpool(
            extract_document, filename, content_type, content
        )
        async with self._transactions() as repository:
            await repository.ensure_default_kb(owner_user_id=owner_user_id)
            existing = await repository.find_hash(
                digest, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
            )
        if existing is not None:
            if not overwrite:
                raise DocumentConflict
            await self.delete(
                existing.id, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
            )
        document = Document(
            str(uuid4()),
            owner_user_id,
            knowledge_base_id,
            name,
            size,
            mime,
            digest,
            datetime.now(timezone.utc),
            "pending",
            config,
            body,
        )
        async with self._transactions() as repository:
            return await repository.add(document, owner_user_id=owner_user_id)

    async def delete(
        self, document_id: str, *, owner_user_id: str, knowledge_base_id: str
    ) -> Document:
        async with self._transactions() as repository:
            document = await repository.soft_delete(
                document_id, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
            )
        if document is None:
            raise DocumentNotFound
        if not document.vectors_cleaned:
            try:
                await run_in_threadpool(
                    self._vector.delete_document,
                    owner_user_id=owner_user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                )
            except Exception:
                raise VectorCleanupError from None
            async with self._transactions() as repository:
                await repository.confirm_cleanup(
                    document_id, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
                )
        return document
