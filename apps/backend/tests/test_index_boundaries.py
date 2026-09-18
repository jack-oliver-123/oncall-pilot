"""归属参数、数据库约束与租约投影边界。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from scope_contract import assert_owner_parameter_contract
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from test_background_jobs import owners as owners

from oncall_pilot.background_jobs import BackgroundJobRepository, LeaseLost
from oncall_pilot.index_tasks import INDEX_KIND, IndexTaskRepository
from oncall_pilot.knowledge import Document, KnowledgeDocumentRepository, default_knowledge_base_id
from oncall_pilot.knowledge_chunking import ChunkingConfig
from oncall_pilot.memory.sqlite import Database


async def test_repository_scope_arguments_before_io() -> None:
    session = MagicMock(spec=AsyncSession)
    repo = IndexTaskRepository(session)
    await assert_owner_parameter_contract(repo.create, knowledge_base_id="k", document_id="d")
    for method in (repo.get, repo.job, repo.cancel):
        await assert_owner_parameter_contract(
            method, task_id="t", knowledge_base_id="k", document_id="d"
        )
    assert not session.mock_calls


@pytest.mark.usefixtures("owners")
async def test_fks_lease_cancel_and_no_job_id(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    from oncall_pilot import background_jobs

    now = datetime.now(timezone.utc)
    monkeypatch.setattr(background_jobs, "_utc_now", lambda: now)
    kb = default_knowledge_base_id("a")
    async with database.transaction() as session:
        repo = KnowledgeDocumentRepository(session)
        await repo.ensure_default_kb(owner_user_id="a")
        await repo.add(
            Document(
                "d",
                "a",
                kb,
                "a.md",
                1,
                "text/plain",
                "a" * 64,
                now,
                "pending",
                ChunkingConfig(),
                "x",
            ),
            owner_user_id="a",
        )
        task = await IndexTaskRepository(session).create(
            owner_user_id="a", knowledge_base_id=kb, document_id="d"
        )
        job = await BackgroundJobRepository(session).claim(
            owner_user_id="a", worker_id="old", kinds=(INDEX_KIND,), lease_seconds=1
        )
        assert job and job.lease_owner
        columns = (await session.execute(text("PRAGMA table_info(document_index_tasks)"))).all()
        assert "job_id" not in [row[1] for row in columns]
    for change in ("owner_user_id='b'", "document_id='missing'", "retry_of_task_id='missing'"):
        with pytest.raises(IntegrityError):
            async with database.transaction() as session:
                await session.execute(
                    text(f"UPDATE document_index_tasks SET {change} WHERE id=:i"), {"i": task.id}
                )
    now += timedelta(seconds=2)
    async with database.transaction() as session:
        assert await BackgroundJobRepository(session).recover_expired(owner_user_id="a") == 1
        current = await IndexTaskRepository(session).get(
            task.id, owner_user_id="a", knowledge_base_id=kb, document_id="d"
        )
        assert current.status == "pending" and current.failure_reason
    with pytest.raises(LeaseLost):
        async with database.transaction() as session:
            await BackgroundJobRepository(session).finish(
                job.id, owner_user_id="a", lease_owner=job.lease_owner, outcome="success"
            )
    now += timedelta(seconds=3)
    async with database.transaction() as session:
        repo = BackgroundJobRepository(session)
        second = await repo.claim(owner_user_id="a", worker_id="new", kinds=(INDEX_KIND,))
        assert second and second.lease_owner
        await repo.cancel(second.id, owner_user_id="a")
        await repo.finish(
            second.id, owner_user_id="a", lease_owner=second.lease_owner, outcome="success"
        )
        current = await IndexTaskRepository(session).get(
            task.id, owner_user_id="a", knowledge_base_id=kb, document_id="d"
        )
        assert current.status == "cancelled"
        assert (
            await session.scalar(
                text(
                    "SELECT index_status FROM knowledge_documents "
                    "WHERE owner_user_id='a' AND id='d'"
                )
            )
            == "cancelled"
        )
