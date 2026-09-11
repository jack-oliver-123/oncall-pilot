from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncGenerator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx
import pytest
from scope_contract import assert_owner_parameter_contract
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_knowledge_core import pdf_bytes
from test_protocol import validator
from test_tenant_api import create_user

from oncall_pilot.app import create_app
from oncall_pilot.knowledge import (
    Document,
    DocumentChunkingService,
    DocumentConflict,
    DocumentNotFound,
    KnowledgeDocumentRepository,
    KnowledgeDocumentService,
    default_knowledge_base_id,
    knowledge_transaction,
)
from oncall_pilot.knowledge_chunking import ChunkingConfig
from oncall_pilot.knowledge_models import documents
from oncall_pilot.memory.scope import InvalidOwnerScope
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.memory.values import utc_now


class Vectors:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.fail = False
        self.database_path: str | None = None

    def delete_document(
        self, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> int:
        self.calls.append(
            {
                "owner_user_id": owner_user_id,
                "knowledge_base_id": knowledge_base_id,
                "document_id": document_id,
            }
        )
        if self.database_path:
            # 在独立连接中取得写锁，证明调用向量时 SQLite 写事务已结束且删除意图已提交。
            with sqlite3.connect(self.database_path, timeout=2) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT deleted_at FROM knowledge_documents WHERE id = ?", (document_id,)
                ).fetchone()
                assert row and row[0] is not None
        if self.fail:
            raise RuntimeError("test-only-vector-secret")
        return 1


@pytest.fixture
async def knowledge_client(
    migrated_config: Path, database: Database
) -> AsyncGenerator[tuple[httpx.AsyncClient, Vectors]]:
    vectors = Vectors()
    vectors.database_path = database.engine.url.database
    app = create_app(migrated_config, document_vectors=vectors)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"X-Request-ID": "knowledge-test"},
        ) as client:
            yield client, vectors


async def upload(
    client: httpx.AsyncClient,
    kb: str,
    headers: dict[str, str],
    *,
    content: bytes = b"# Heading\nknowledge content",
    name: str = "notes.md",
    mime: str = "text/markdown",
    data: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"/knowledge-bases/{kb}/documents",
        headers=headers,
        files={"file": (name, content, mime)},
        data=data,
    )


async def test_lifecycle_conflict_overwrite_pdf_and_preview(
    knowledge_client: tuple[httpx.AsyncClient, Vectors],
    database: Database,
) -> None:
    client, vectors = knowledge_client
    owner, token = await create_user(client, "docs@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    kb = default_knowledge_base_id(owner)
    # POST 不依赖先调用 GET 知识库列表。
    response = await upload(client, kb, headers, content=("正文" * 16000).encode())
    assert response.status_code == 200, response.text
    validator("KnowledgeDocumentResponse").validate(response.json())
    original = response.json()["data"]
    assert original["indexStatus"] == "pending" and "body" not in original
    assert original["chunkingConfig"] == ChunkingConfig().public()
    kbs = (await client.get("/knowledge-bases", headers=headers)).json()["data"]
    assert len(kbs) == 1 and kbs[0]["id"] == kb
    assert (await client.get("/knowledge-bases", headers=headers)).json()["data"] == kbs
    path = f"/knowledge-bases/{kb}/documents/{original['id']}"
    preview = await client.get(path + "/chunk-preview", headers=headers)
    assert preview.status_code == 200
    validator("ChunkPreviewResponse").validate(preview.json())
    chunks = preview.json()["data"]
    assert len(chunks) == 12 and all(len(c["excerpt"]) == 400 for c in chunks)
    assert chunks[0]["metadata"]["documentId"] == original["id"]
    assert chunks[0]["metadata"]["tenantId"] == owner
    assert chunks[0]["metadata"]["strategy"] == "fixed-character"
    assert (await client.get(path + "/chunk-preview", headers=headers)).json() == preview.json()
    assert (await client.get(path, headers=headers)).json()["data"] == original
    async with database.transaction() as session:
        record = await KnowledgeDocumentRepository(session).get(
            original["id"], owner_user_id=owner, knowledge_base_id=kb
        )
        assert record is not None
        assert DocumentChunkingService().preview(record) == chunks
        assert DocumentChunkingService().chunks(record)[0].text.startswith(chunks[0]["excerpt"])
    duplicate = await upload(client, kb, headers, content=("正文" * 16000).encode())
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "BUSINESS_CONFLICT"
    assert vectors.calls == []
    replacement = await upload(
        client,
        kb,
        headers,
        content=("正文" * 16000).encode(),
        data={"overwrite": "true", "chunkingConfig": '{"strategy":"paragraph"}'},
    )
    assert replacement.status_code == 200, replacement.text
    new = replacement.json()["data"]
    assert new["id"] != original["id"] and new["chunkingConfig"] == {"strategy": "paragraph"}
    assert vectors.calls == [
        {"owner_user_id": owner, "knowledge_base_id": kb, "document_id": original["id"]}
    ]
    assert (await client.get(path, headers=headers)).status_code == 403
    new_path = f"/knowledge-bases/{kb}/documents/{new['id']}"
    assert (await client.delete(new_path, headers=headers)).status_code == 200
    assert (await client.delete(new_path, headers=headers)).status_code == 200
    assert len(vectors.calls) == 2
    assert (await client.get(f"/knowledge-bases/{kb}/documents", headers=headers)).json()[
        "data"
    ] == []
    pdf = await upload(
        client, kb, headers, name="manual.pdf", mime="application/pdf", content=pdf_bytes()
    )
    assert pdf.status_code == 200, pdf.text
    pdf_id = pdf.json()["data"]["id"]
    async with database.transaction() as session:
        record = await KnowledgeDocumentRepository(session).get(
            pdf_id, owner_user_id=owner, knowledge_base_id=kb
        )
        assert record and "On-call PDF content" in record.body


async def test_all_routes_auth_owner_parent_isolation_and_logout(
    knowledge_client: tuple[httpx.AsyncClient, Vectors],
) -> None:
    client, vectors = knowledge_client
    a, ta = await create_user(client, "a-docs@example.com")
    b, tb = await create_user(client, "b-docs@example.com")
    ha, hb = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}
    ka, kb = default_knowledge_base_id(a), default_knowledge_base_id(b)
    results = await asyncio.gather(upload(client, ka, ha), upload(client, kb, hb))
    assert all(result.status_code == 200 for result in results)
    da, db = [result.json()["data"]["id"] for result in results]
    failures: list[Any] = []
    for method, suffix in [
        ("GET", ""),
        ("POST", ""),
        ("GET", f"/{da}"),
        ("DELETE", f"/{da}"),
        ("GET", f"/{da}/chunk-preview"),
    ]:
        for parent in [ka, "missing"]:
            path = f"/knowledge-bases/{parent}/documents{suffix}"
            kwargs: dict[str, Any] = (
                {"files": {"file": ("x.md", b"x", "text/markdown")}} if method == "POST" else {}
            )
            response = await client.request(method, path, headers=hb, **kwargs)
            assert response.status_code == 403, response.text
            failures.append(response.json())
            assert (await client.request(method, path, **kwargs)).status_code == 401
    for method, suffix in [("GET", ""), ("DELETE", ""), ("GET", "/chunk-preview")]:
        for document in [da, "missing"]:
            response = await client.request(
                method, f"/knowledge-bases/{kb}/documents/{document}{suffix}", headers=hb
            )
            assert response.status_code == 403
            failures.append(response.json())
    assert all(failure == failures[0] for failure in failures)
    assert (await client.get("/knowledge-bases")).status_code == 401
    assert vectors.calls == []
    assert (
        await client.get(f"/knowledge-bases/{kb}/documents/{db}", headers=hb)
    ).status_code == 200
    await client.post("/auth/logout", headers=ha)
    login = await client.post(
        "/auth/login", json={"email": "a-docs@example.com", "password": "scope-password"}
    )
    ha = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    assert (await client.get("/knowledge-bases", headers=ha)).json()["data"][0]["id"] == ka
    assert (
        await client.get(f"/knowledge-bases/{ka}/documents/{da}", headers=ha)
    ).status_code == 200


@pytest.mark.parametrize("overwrite", [False, True])
async def test_vector_failure_retry_hash_reservation(
    knowledge_client: tuple[httpx.AsyncClient, Vectors],
    database: Database,
    overwrite: bool,
) -> None:
    client, vectors = knowledge_client
    owner, token = await create_user(client, "retry-docs@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    kb = default_knowledge_base_id(owner)
    original = (await upload(client, kb, headers)).json()["data"]
    path = f"/knowledge-bases/{kb}/documents/{original['id']}"
    vectors.fail = True
    failed = (
        await upload(client, kb, headers, data={"overwrite": "true"})
        if overwrite
        else await client.delete(path, headers=headers)
    )
    assert failed.status_code == 500
    assert "test-only-vector-secret" not in failed.text
    assert (await client.get(path, headers=headers)).status_code == 403
    assert (await upload(client, kb, headers)).status_code == 409
    async with database.transaction() as session:
        record = await KnowledgeDocumentRepository(session).get(
            original["id"], owner_user_id=owner, knowledge_base_id=kb, include_deleted=True
        )
        assert record and record.deleted_at and not record.vectors_cleaned
    vectors.fail = False
    retry = (
        await upload(client, kb, headers, data={"overwrite": "true"})
        if overwrite
        else await client.delete(path, headers=headers)
    )
    assert retry.status_code == 200, retry.text
    assert len(vectors.calls) == 2 and vectors.calls[0] == vectors.calls[1]
    async with database.transaction() as session:
        record = await KnowledgeDocumentRepository(session).get(
            original["id"], owner_user_id=owner, knowledge_base_id=kb, include_deleted=True
        )
        assert record and record.vectors_cleaned


@pytest.mark.parametrize(
    "config",
    [
        "null",
        "[]",
        "oops",
        '{"overlap":1200}',
        '{"strategy":"paragraph","maxCharacters":1}',
        '{"maxCharacters":"1200"}',
        '{"strategy":"markdown-heading","overlap":null}',
        '{"extra":1}',
    ],
)
async def test_invalid_multipart_config_has_no_side_effects(
    knowledge_client: tuple[httpx.AsyncClient, Vectors],
    config: str,
) -> None:
    client, vectors = knowledge_client
    owner, token = await create_user(client, "bad-config@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    kb = default_knowledge_base_id(owner)
    response = await upload(client, kb, headers, data={"chunkingConfig": config})
    assert response.status_code == 400, response.text
    assert vectors.calls == []
    assert (await client.get(f"/knowledge-bases/{kb}/documents", headers=headers)).json()[
        "data"
    ] == []


async def test_repository_owner_parameter_contract() -> None:
    session = AsyncMock(spec=AsyncSession)
    repo = KnowledgeDocumentRepository(cast(AsyncSession, session))
    document = Document(
        "d",
        "owner",
        default_knowledge_base_id("owner"),
        "a.md",
        1,
        "text/markdown",
        "a" * 64,
        utc_now(),
        "pending",
        ChunkingConfig(),
        "x",
    )
    await assert_owner_parameter_contract(repo.ensure_default_kb)
    await assert_owner_parameter_contract(repo.list, knowledge_base_id="kb")
    await assert_owner_parameter_contract(repo.get, document_id="d", knowledge_base_id="kb")
    await assert_owner_parameter_contract(repo.find_hash, sha256="a", knowledge_base_id="kb")
    await assert_owner_parameter_contract(repo.add, document=document)
    await assert_owner_parameter_contract(repo.soft_delete, document_id="d", knowledge_base_id="kb")
    await assert_owner_parameter_contract(
        repo.confirm_cleanup, document_id="d", knowledge_base_id="kb"
    )
    assert session.mock_calls == []


async def test_http_file_policy_boundaries_and_unknown_fields(
    knowledge_client: tuple[httpx.AsyncClient, Vectors],
) -> None:
    from oncall_pilot.knowledge_documents import MAX_UPLOAD_BYTES

    client, vectors = knowledge_client
    owner, token = await create_user(client, "file-policy@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    kb = default_knowledge_base_id(owner)
    for name, mime, content in [
        ("a.txt", "text/plain", b"x"),
        ("a.md", "application/pdf", b"x"),
        ("a.md", "text/plain", b"\xff"),
        ("a.pdf", "application/pdf", b"broken"),
        ("a.md", "text/plain", b""),
        ("a.md", "text/plain", b"x" * (MAX_UPLOAD_BYTES + 1)),
    ]:
        response = await upload(client, kb, headers, name=name, mime=mime, content=content)
        assert response.status_code == 400, response.text
    assert (await upload(client, kb, headers, data={"chunking_config": "{}"})).status_code == 400
    assert (await upload(client, kb, headers, data={"overwrite": "not-bool"})).status_code == 422
    assert vectors.calls == []
    assert (await client.get(f"/knowledge-bases/{kb}/documents", headers=headers)).json()[
        "data"
    ] == []
    assert (await upload(client, kb, headers, content=b"x" * MAX_UPLOAD_BYTES)).status_code == 200
    assert (
        await upload(client, kb, headers, content=b"x" * (MAX_UPLOAD_BYTES + 65537))
    ).status_code == 400


async def test_repository_scope_unique_and_concurrent_uploads(
    knowledge_client: tuple[httpx.AsyncClient, Vectors],
    database: Database,
) -> None:
    client, vectors = knowledge_client
    a, _ = await create_user(client, "repo-a@example.com")
    b, _ = await create_user(client, "repo-b@example.com")
    ka, kb = default_knowledge_base_id(a), default_knowledge_base_id(b)
    service = KnowledgeDocumentService(lambda: knowledge_transaction(database), vectors)
    results = await asyncio.gather(
        *[
            service.upload(
                "a.md",
                "text/plain",
                b"same",
                owner_user_id=a,
                knowledge_base_id=ka,
                config=ChunkingConfig(),
            )
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(result, Document) for result in results) == 1
    assert sum(isinstance(result, DocumentConflict) for result in results) == 1
    original = next(result for result in results if isinstance(result, Document))
    await service.list_kbs(owner_user_id=b)
    async with database.transaction() as session:
        repo = KnowledgeDocumentRepository(session)
        assert await repo.get(original.id, owner_user_id=b, knowledge_base_id=kb) is None
        assert await repo.soft_delete(original.id, owner_user_id=b, knowledge_base_id=kb) is None
        await repo.confirm_cleanup(original.id, owner_user_id=b, knowledge_base_id=kb)
        with pytest.raises(DocumentNotFound):
            await repo.list(owner_user_id=b, knowledge_base_id=ka)
        with pytest.raises(InvalidOwnerScope):
            await repo.add(original, owner_user_id=b)
        with pytest.raises(DocumentNotFound):
            await repo.add(replace(original, knowledge_base_id=kb), owner_user_id=a)
    async with database.transaction() as session:
        with pytest.raises(DocumentConflict):
            await KnowledgeDocumentRepository(session).add(
                replace(original, id="duplicate"), owner_user_id=a
            )
    async with database.transaction() as session:
        rows = (
            (await session.execute(select(documents).where(documents.c.owner_user_id == a)))
            .mappings()
            .all()
        )
        assert len(rows) == 1 and rows[0]["deleted_at"] is None and not rows[0]["vectors_cleaned"]
