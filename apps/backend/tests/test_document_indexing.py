"""P11 的真实 SQLite/HTTP 与可注入 provider/vector 验收。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from test_knowledge_api import upload
from test_protocol import validator
from test_tenant_api import create_user

from oncall_pilot.app import create_app
from oncall_pilot.background_jobs import BackgroundJobRepository
from oncall_pilot.document_indexing import Embeddings
from oncall_pilot.knowledge import default_knowledge_base_id
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.vector_store import VectorChunk


class Vectors:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.rows: list[dict[str, Any]] = []
        self.fail = ""

    def initialize(self) -> None:
        self.calls.append("initialize")
        if self.fail == "initialize":
            raise RuntimeError("secret-initialize")

    def delete_document(
        self, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> int:
        self.calls.append("delete")
        if self.fail == "delete":
            raise RuntimeError("secret-delete")
        self.rows = [
            r
            for r in self.rows
            if not (
                r["tenantId"] == owner_user_id
                and r["knowledgeBaseId"] == knowledge_base_id
                and r["documentId"] == document_id
            )
        ]
        return 0

    def insert_chunks(self, chunks: Sequence[VectorChunk], *, owner_user_id: str) -> None:
        self.calls.append("insert")
        if self.fail == "insert":
            raise RuntimeError("secret-insert")
        self.rows.extend(c.row(owner_user_id=owner_user_id) for c in chunks)


class Embed:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.fail = False
        self.block = False
        self.started = asyncio.Event()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        self.started.set()
        if self.block:
            await asyncio.Event().wait()
        if self.fail:
            raise RuntimeError("secret-embedding")
        return [[float(i)] * 1024 for i in range(len(texts))]


@pytest.fixture
async def setup(migrated_config: Path):
    vectors, embed = Vectors(), Embed()

    @asynccontextmanager
    async def provider() -> AsyncGenerator[Embeddings]:
        yield embed

    app = create_app(
        migrated_config, document_vectors=vectors, index_vectors=vectors, index_provider=provider
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"X-Request-ID": "index-test"},
        ) as client:
            yield client, vectors, embed, app


async def document(client: httpx.AsyncClient, email: str = "index@example.com"):
    owner, token = await create_user(client, email)
    headers = {"Authorization": f"Bearer {token}"}
    kb = default_knowledge_base_id(owner)
    response = await upload(
        client,
        kb,
        headers,
        content="\n\n".join(f"段落 {i}" for i in range(23)).encode(),
        data={"chunkingConfig": '{"strategy":"paragraph"}'},
    )
    assert response.status_code == 200
    doc = response.json()["data"]
    return owner, kb, headers, doc, f"/knowledge-bases/{kb}/documents/{doc['id']}"


async def wait(client: httpx.AsyncClient, path: str, headers: dict[str, str], status: str):
    async def poll():
        while True:
            response = await client.get(path, headers=headers)
            assert response.status_code == 200, response.text
            value = response.json()["data"]
            if value["status"] == status:
                validator("DocumentIndexTaskResponse").validate(response.json())
                return value
            await asyncio.sleep(0.03)

    return await asyncio.wait_for(poll(), 15)


async def test_upload_explicit_create_rebuild_metadata(
    setup: tuple[httpx.AsyncClient, Vectors, Embed, FastAPI], database: Database
) -> None:
    client, vectors, embed, _ = setup
    owner, kb, headers, doc, path = await document(client)
    async with database.transaction() as session:
        assert await session.scalar(text("SELECT count(*) FROM background_jobs")) == 0
        assert await session.scalar(text("SELECT count(*) FROM document_index_tasks")) == 0
    created = await client.post(path + "/index-tasks", headers=headers)
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    assert task["status"] == "pending" and task["retryOfTaskId"] is None
    task_path = path + "/index-tasks/" + task["id"]
    await wait(client, task_path, headers, "succeeded")
    assert vectors.calls == ["initialize", "delete", "insert"]
    assert len(vectors.rows) == len(embed.texts) == 23
    assert [r["content"] for r in vectors.rows] == embed.texts
    for i, row in enumerate(vectors.rows):
        assert row["documentId"] == doc["id"] and row["knowledgeBaseId"] == kb
        assert row["ownerUserId"] == row["tenantId"] == owner
        assert row["source"] == "notes.md" and row["createdAt"] and row["chunkId"]
        assert row["metadata"]["index"] == i
        assert row["metadata"]["strategy"] == "paragraph"
        assert row["metadata"]["ownerUserId"] == owner
        assert row["vector"] == [float(i)] * 1024
    assert (await client.get(path, headers=headers)).json()["data"]["indexStatus"] == "succeeded"
    rebuilt = (await client.post(task_path + ":retry", headers=headers)).json()["data"]
    assert rebuilt["retryOfTaskId"] == task["id"] and rebuilt["id"] != task["id"]
    await wait(client, path + "/index-tasks/" + rebuilt["id"], headers, "succeeded")
    assert len(vectors.rows) == 23
    assert vectors.calls == ["initialize", "delete", "insert"] * 2
    async with database.transaction() as session:
        jobs = await BackgroundJobRepository(session).list(owner_user_id=owner)
        assert len(jobs) == 2 and jobs[0].resource_type == "document_index_task"
        assert jobs[0].resource_id == task["id"]
        assert (
            "job_id"
            not in (await session.execute(text("PRAGMA table_info(document_index_tasks)")))
            .scalars()
            .all()
        )


@pytest.mark.parametrize("failure", ["embedding", "initialize", "delete", "insert"])
async def test_failure_safe_retry(
    setup: tuple[httpx.AsyncClient, Vectors, Embed, FastAPI], database: Database, failure: str
) -> None:
    client, vectors, embed, _ = setup
    _, _, headers, _, path = await document(client)
    embed.fail = failure == "embedding"
    vectors.fail = failure
    task = (await client.post(path + "/index-tasks", headers=headers)).json()["data"]
    task_path = path + "/index-tasks/" + task["id"]
    failed = await wait(client, task_path, headers, "failed")
    assert failed["failureReason"] and "secret" not in failed["failureReason"]
    assert (await client.get(path, headers=headers)).json()["data"]["indexStatus"] == "failed"
    async with database.transaction() as session:
        job_id = await session.scalar(
            text("SELECT id FROM background_jobs WHERE resource_id=:i"), {"i": task["id"]}
        )
    assert (
        await client.post(f"/background-jobs/{job_id}:retry", headers=headers)
    ).status_code == 409
    embed.fail = False
    vectors.fail = ""
    new = (await client.post(task_path + ":retry", headers=headers)).json()["data"]
    await wait(client, path + "/index-tasks/" + new["id"], headers, "succeeded")
    assert new["retryOfTaskId"] == task["id"]
    assert (await client.get(task_path, headers=headers)).json()["data"]["status"] == "failed"


async def test_cancel_isolation_and_active_conflicts(
    setup: tuple[httpx.AsyncClient, Vectors, Embed, FastAPI],
) -> None:
    client, vectors, embed, _ = setup
    _, _, headers, _, path = await document(client)
    embed.block = True
    task = (await client.post(path + "/index-tasks", headers=headers)).json()["data"]
    task_path = path + "/index-tasks/" + task["id"]
    await asyncio.wait_for(embed.started.wait(), 5)
    assert (await client.post(path + "/index-tasks", headers=headers)).status_code == 409
    assert (await client.delete(path, headers=headers)).status_code == 409
    # 跨用户与不存在资源的错误 envelope 完全相同。
    _, _, other, _, other_path = await document(client, "other-index@example.com")
    for suffix, method in [("", "GET"), (":retry", "POST"), (":cancel", "POST")]:
        forbidden = await client.request(method, task_path + suffix, headers=other)
        missing = await client.request(
            method, other_path + "/index-tasks/missing" + suffix, headers=other
        )
        assert forbidden.status_code == missing.status_code == 403
        assert forbidden.json() == missing.json()
        assert (await client.request(method, task_path + suffix)).status_code == 401
    cancelled = await client.post(task_path + ":cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["data"]["cancelRequestedAt"]
    # 仅取消请求即可终止等待中的 provider，不需要关闭 worker。
    await wait(client, task_path, headers, "cancelled")
    assert vectors.calls == []
