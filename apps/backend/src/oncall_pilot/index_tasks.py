"""文档索引领域记录与同事务入队。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, JsonValue
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.background_jobs import BackgroundJobRepository, InvalidJobState, Job
from oncall_pilot.generated_contracts import DocumentIndexStatus
from oncall_pilot.index_models import index_tasks
from oncall_pilot.knowledge import DocumentNotFound, KnowledgeDocumentRepository, require_default_kb
from oncall_pilot.memory.scope import OwnerScope

INDEX_KIND = "document_index"
INDEX_RESOURCE = "document_index_task"


class IndexTask(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    owner_user_id: str
    knowledge_base_id: str
    document_id: str
    status: DocumentIndexStatus
    failure_reason: str | None
    retry_of_task_id: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None
    cancel_requested_at: str | None

    def public(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "ownerUserId": self.owner_user_id,
            "knowledgeBaseId": self.knowledge_base_id,
            "documentId": self.document_id,
            "status": self.status,
            "failureReason": self.failure_reason,
            "retryOfTaskId": self.retry_of_task_id,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "cancelRequestedAt": self.cancel_requested_at,
        }


class IndexTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _lock(self, owner_user_id: str) -> None:
        OwnerScope(owner_user_id)
        await self.session.execute(
            text("UPDATE knowledge_documents SET id=id WHERE owner_user_id=:o AND 0"),
            {"o": owner_user_id},
        )

    async def get(
        self, task_id: str, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> IndexTask:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        document = await KnowledgeDocumentRepository(self.session).get(
            document_id, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
        )
        if document is None:
            raise DocumentNotFound
        row = (
            (
                await self.session.execute(
                    select(index_tasks).where(
                        index_tasks.c.id == task_id,
                        index_tasks.c.owner_user_id == owner_user_id,
                        index_tasks.c.knowledge_base_id == knowledge_base_id,
                        index_tasks.c.document_id == document_id,
                    )
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DocumentNotFound
        return IndexTask.model_validate(dict(row))

    async def create(
        self,
        *,
        owner_user_id: str,
        knowledge_base_id: str,
        document_id: str,
        retry_of_task_id: str | None = None,
    ) -> IndexTask:
        require_default_kb(owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id)
        await self._lock(owner_user_id)
        document = await KnowledgeDocumentRepository(self.session).get(
            document_id, owner_user_id=owner_user_id, knowledge_base_id=knowledge_base_id
        )
        if document is None:
            raise DocumentNotFound
        previous = (
            (
                await self.session.execute(
                    select(index_tasks)
                    .where(
                        index_tasks.c.owner_user_id == owner_user_id,
                        index_tasks.c.knowledge_base_id == knowledge_base_id,
                        index_tasks.c.document_id == document_id,
                    )
                    .order_by(index_tasks.c.created_at.desc(), index_tasks.c.id.desc())
                )
            )
            .mappings()
            .all()
        )
        if retry_of_task_id is not None:
            source = await self.get(
                retry_of_task_id,
                owner_user_id=owner_user_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
            )
            if source.status not in ("succeeded", "failed", "cancelled"):
                raise InvalidJobState
        elif previous:
            retry_of_task_id = previous[0]["id"]
        if any(row["status"] in ("pending", "running") for row in previous):
            raise InvalidJobState
        task_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        await self.session.execute(
            index_tasks.insert().values(
                id=task_id,
                owner_user_id=owner_user_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                status="pending",
                created_at=now,
                updated_at=now,
                retry_of_task_id=retry_of_task_id,
            )
        )
        await BackgroundJobRepository(self.session).create(
            owner_user_id=owner_user_id,
            kind=INDEX_KIND,
            payload={"knowledgeBaseId": knowledge_base_id, "documentId": document_id},
            resource_type=INDEX_RESOURCE,
            resource_id=task_id,
        )
        return await self.get(
            task_id,
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )

    async def job(
        self, task_id: str, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> Job:
        await self.get(
            task_id,
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        row = (
            (
                await self.session.execute(
                    text(
                        "SELECT * FROM background_jobs WHERE owner_user_id=:o "
                        "AND resource_type=:rt "
                        "AND resource_id=:i AND kind=:k"
                    ),
                    {"o": owner_user_id, "rt": INDEX_RESOURCE, "i": task_id, "k": INDEX_KIND},
                )
            )
            .mappings()
            .one()
        )
        return Job.model_validate(dict(row))

    async def cancel(
        self, task_id: str, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> IndexTask:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        job = await self.job(
            task_id,
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        await BackgroundJobRepository(self.session).cancel(job.id, owner_user_id=owner_user_id)
        return await self.get(
            task_id,
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
