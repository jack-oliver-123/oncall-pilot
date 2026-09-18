"""P06 批次与 P09 恢复贯穿索引 handler。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from llm_helpers import model_project
from test_document_indexing import Embed, Vectors, document, wait

from oncall_pilot.app import create_app
from oncall_pilot.background_jobs import BackgroundJobRepository
from oncall_pilot.background_runtime import BackgroundWorker, HandlerRegistry
from oncall_pilot.document_indexing import DocumentIndexHandler, Embeddings
from oncall_pilot.index_tasks import INDEX_KIND, IndexTaskRepository
from oncall_pilot.knowledge import Document, DocumentChunkingService
from oncall_pilot.knowledge_chunking import DocumentChunk
from oncall_pilot.llm.config import validate_llm_config
from oncall_pilot.llm.qwen import QwenOpenAIProvider
from oncall_pilot.memory.sqlite import Database


class BatchEmbed:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        start = sum(len(batch) for batch in self.batches)
        self.batches.append(texts)
        return [[float(start + i)] * 1024 for i in range(len(texts))]


class Chat:
    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        return "unused"


async def test_qwen_batches_ten_ten_three_one_insert(migrated_config: Path) -> None:
    batch, vectors = BatchEmbed(), Vectors()
    async with httpx.AsyncClient() as rerank:

        @asynccontextmanager
        async def factory() -> AsyncGenerator[Embeddings]:
            yield QwenOpenAIProvider(
                validate_llm_config(dict(model_project())),
                chat_client=Chat(),
                embedding_client=batch,
                rerank_client=rerank,
            )

        app = create_app(migrated_config, index_vectors=vectors, index_provider=factory)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                _, _, headers, _, path = await document(client)
                task = (await client.post(path + "/index-tasks", headers=headers)).json()["data"]
                await wait(client, path + "/index-tasks/" + task["id"], headers, "succeeded")
                assert [len(b) for b in batch.batches] == [10, 10, 3]
                assert vectors.calls == ["initialize", "delete", "insert"]
                assert [r["content"] for r in vectors.rows] == [t for b in batch.batches for t in b]
                assert [r["vector"][0] for r in vectors.rows] == list(range(23))


async def test_persistent_restart_and_cancel_without_get(
    migrated_config: Path, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import text

    from oncall_pilot import background_jobs
    from oncall_pilot.memory.sqlite import open_database

    app = create_app(migrated_config)
    # 不启动 worker，仅使用已初始化的认证/文档服务完成上传，然后先停止轮询。
    async with app.router.lifespan_context(app):
        app.state.background_worker.stop_event.set()
        await asyncio.gather(*app.state.background_worker.tasks)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            owner, kb, headers, doc, path = await document(client)
            task = (await client.post(path + "/index-tasks", headers=headers)).json()["data"]
    # 独立进程领取并退出，下一 engine 恢复磁盘记录。
    import sys

    code = """
import asyncio,sys
from pathlib import Path
from oncall_pilot.memory.sqlite import open_database
from oncall_pilot.background_jobs import BackgroundJobRepository
async def run():
 async with open_database(Path(sys.argv[1])) as db:
  async with db.transaction() as s:
   assert await BackgroundJobRepository(s).claim(
    owner_user_id=sys.argv[2],worker_id='exited',
    kinds=('document_index',),lease_seconds=.01)
asyncio.run(run())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", code, str(migrated_config), owner
    )
    assert await asyncio.wait_for(process.wait(), 15) == 0
    now = datetime.now(timezone.utc) + timedelta(seconds=1)
    monkeypatch.setattr(background_jobs, "_utc_now", lambda: now)
    vectors = Vectors()

    @asynccontextmanager
    async def factory() -> AsyncGenerator[Embeddings]:
        yield Embed()

    async with open_database(migrated_config) as reopened:
        async with reopened.transaction() as session:
            assert await BackgroundJobRepository(session).recover_expired(owner_user_id=owner) == 1
            row = await IndexTaskRepository(session).get(
                task["id"], owner_user_id=owner, knowledge_base_id=kb, document_id=doc["id"]
            )
            assert row.status == "pending"
        now += timedelta(seconds=3)
        registry = HandlerRegistry()
        registry.register(INDEX_KIND, DocumentIndexHandler(factory, vectors))
        async with BackgroundWorker(reopened, registry).lifespan():
            status: object = None
            for _ in range(300):
                async with reopened.transaction() as session:
                    status = await session.scalar(
                        text(
                            "SELECT status FROM document_index_tasks "
                            "WHERE id=:i AND owner_user_id=:o"
                        ),
                        {"i": task["id"], "o": owner},
                    )
                if status == "succeeded":
                    break
                await asyncio.sleep(0.02)
            assert status == "succeeded"
        assert vectors.calls == ["initialize", "delete", "insert"]
        async with reopened.transaction() as session:
            repo = IndexTaskRepository(session)
            new = await repo.create(
                owner_user_id=owner, knowledge_base_id=kb, document_id=doc["id"]
            )
            cancelled = await repo.cancel(
                new.id, owner_user_id=owner, knowledge_base_id=kb, document_id=doc["id"]
            )
            assert cancelled.status == "cancelled"
            assert (
                await session.scalar(
                    text(
                        "SELECT index_status FROM knowledge_documents "
                        "WHERE id=:i AND owner_user_id=:o"
                    ),
                    {"i": doc["id"], "o": owner},
                )
                == "cancelled"
            )


class BrokenSplitter(DocumentChunkingService):
    def chunks(self, document: Document, *, limit: int | None = None) -> list[DocumentChunk]:
        raise RuntimeError("secret-split")


async def test_split_failure_no_vector_side_effect(
    migrated_config: Path, database: Database
) -> None:
    vectors = Vectors()

    @asynccontextmanager
    async def factory() -> AsyncGenerator[Embeddings]:
        yield Embed()

    registry = HandlerRegistry()
    registry.register(INDEX_KIND, DocumentIndexHandler(factory, vectors, BrokenSplitter()))
    app = create_app(migrated_config, job_handlers=registry)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            _, _, headers, _, path = await document(client)
            task = (await client.post(path + "/index-tasks", headers=headers)).json()["data"]
            result = await wait(client, path + "/index-tasks/" + task["id"], headers, "failed")
            assert result["failureReason"] == "文档切分失败。"
            assert vectors.calls == []
