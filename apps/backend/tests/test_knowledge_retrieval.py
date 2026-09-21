"""混合知识检索算法、scope 和 LangChain Tool 合同测试。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest

from oncall_pilot.knowledge_retrieval import (
    IndexedChunk,
    KnowledgeRetrievalService,
    RetrievalError,
    bm25l_scores,
    create_knowledge_retrieval_tool,
    tokenize,
)
from oncall_pilot.llm.contracts import RerankResult
from oncall_pilot.memory.scope import OwnerScope


@dataclass
class FakeProvider:
    embeddings: list[list[float]] | None = None
    rerank_results: list[RerankResult] | None = None
    embedding_error: Exception | None = None
    rerank_error: Exception | None = None
    started: asyncio.Event | None = None
    release: asyncio.Event | None = None
    rerank_calls: list[tuple[str, list[str], int | None]] | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.embedding_error is not None:
            raise self.embedding_error
        return self.embeddings or [[0.1]]

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankResult]:
        if self.rerank_calls is not None:
            self.rerank_calls.append((query, documents, top_n))
        if self.rerank_error is not None:
            raise self.rerank_error
        return self.rerank_results or [
            RerankResult(index, float(len(documents) - index)) for index in range(len(documents))
        ]


@dataclass
class FakeChunks:
    chunks: list[IndexedChunk]
    error: Exception | None = None
    started: asyncio.Event | None = None

    async def list_chunks(
        self, *, owner_user_id: str, knowledge_base_ids: Sequence[str]
    ) -> list[IndexedChunk]:
        if self.started is not None:
            self.started.set()
        if self.error is not None:
            raise self.error
        return self.chunks


@dataclass
class FakeVector:
    hits: Sequence[Mapping[str, Any]]
    error: Exception | None = None

    async def search(
        self,
        vector: Sequence[float],
        *,
        owner_user_id: str,
        knowledge_base_ids: Sequence[str],
        limit: int,
    ) -> list[Mapping[str, Any]]:
        if self.error is not None:
            raise self.error
        return list(self.hits[:limit])


@asynccontextmanager
async def provider_context(provider: FakeProvider) -> AsyncGenerator[FakeProvider, None]:
    yield provider


def chunk(
    chunk_id: str,
    content: str,
    *,
    owner: str = "user-a",
    kb: str = "kb-a",
    document: str = "doc-a",
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id,
        document,
        kb,
        owner,
        owner,
        content,
        f"source-{chunk_id}",
        {"kind": "runbook"},
    )


def entity(item: IndexedChunk, distance: float) -> dict[str, Any]:
    return {
        "distance": distance,
        "entity": {
            "chunkId": item.chunk_id,
            "documentId": item.document_id,
            "knowledgeBaseId": item.knowledge_base_id,
            "ownerUserId": item.owner_user_id,
            "tenantId": item.tenant_id,
            "content": item.content,
            "source": item.source,
            "metadata": dict(item.metadata),
        },
    }


def service(
    provider: FakeProvider,
    chunks: list[IndexedChunk],
    hits: Sequence[Mapping[str, Any]],
    *,
    owner: str = "user-a",
    chunk_source: FakeChunks | None = None,
    vector: FakeVector | None = None,
) -> KnowledgeRetrievalService:
    return KnowledgeRetrievalService(
        provider_factory=lambda: provider_context(provider),
        chunk_source=chunk_source or FakeChunks(chunks),
        vector_recall=vector or FakeVector(hits),
        owner_scope=OwnerScope(owner),
        allowed_knowledge_base_ids=("kb-a",),
    )


def test_tokenizer_keeps_chinese_unigrams_bigrams_and_ascii_operations_tokens() -> None:
    tokens = tokenize("服务 JavaClass traceId service-42 2026")

    assert "服" in tokens and "务" in tokens and "服务" in tokens
    assert {"javaclass", "traceid", "service-42", "2026"}.issubset(tokens)


def test_bm25l_uses_positive_idf_and_zero_for_disjoint_terms() -> None:
    scores = bm25l_scores("告警", ["告警服务", "服务", "完全不同"])

    assert scores[0] > 0
    assert scores[1] == 0
    assert scores[2] == 0
    assert all(score >= 0 for score in scores)


def test_rrf_formula_and_stable_tie_break() -> None:
    first = chunk("a", "命中")
    second = chunk("b", "命中")
    provider = FakeProvider(rerank_results=[RerankResult(0, 1.0), RerankResult(1, 0.5)])
    retrieval = service(provider, [first, second], [entity(first, 0.9), entity(second, 0.8)])

    output = asyncio.run(retrieval.retrieve("命中"))

    assert abs(output["results"][0]["rrfScore"] - (1 / 61 + 1 / 61)) < 1e-12
    assert [item["chunkId"] for item in output["results"]] == ["a", "b"]


@pytest.mark.asyncio
async def test_vector_and_bm25_start_in_parallel() -> None:
    vector_started = asyncio.Event()
    bm25_started = asyncio.Event()
    release = asyncio.Event()
    provider = FakeProvider(started=vector_started, release=release)
    source = FakeChunks([chunk("a", "告警")], started=bm25_started)
    task = asyncio.create_task(
        service(
            provider,
            source.chunks,
            [entity(source.chunks[0], 0.9)],
            chunk_source=source,
        ).retrieve("告警")
    )

    await asyncio.wait_for(asyncio.gather(vector_started.wait(), bm25_started.wait()), timeout=1)
    release.set()
    await task


@pytest.mark.asyncio
async def test_rerank_reordering_preserves_all_stage_fields_and_top_k() -> None:
    first = chunk("a", "other")
    second = chunk("b", "alpha")
    provider = FakeProvider(
        rerank_results=[RerankResult(1, 9.0), RerankResult(0, 1.0)], rerank_calls=[]
    )
    output = await service(
        provider,
        [first, second],
        [entity(first, 0.9)],
    ).retrieve("alpha", top_k=1)

    item = output["results"][0]
    assert item["chunkId"] == "b"
    assert item["vectorRank"] is None
    assert item["bm25Rank"] == 1
    assert item["vectorScore"] is None
    assert item["bm25Score"] is not None
    assert item["rerankRank"] == 1
    assert item["score"] == item["rerankScore"] == 9.0
    assert output["citations"] == output["results"]
    assert provider.rerank_calls and provider.rerank_calls[0][2] == 2


@pytest.mark.asyncio
async def test_filters_only_narrow_current_scope_and_exclude_foreign_rows() -> None:
    allowed = chunk("allowed", "trace service", document="doc-a")
    other_document = chunk("other", "trace service", document="doc-b")
    foreign = chunk("foreign", "trace service", owner="user-b", kb="kb-b", document="doc-b")
    provider = FakeProvider(rerank_results=[RerankResult(0, 2.0)])
    output = await service(
        provider,
        [allowed, other_document, foreign],
        [entity(allowed, 0.8)],
    ).retrieve("trace", document_ids=["doc-a"])

    assert [item["chunkId"] for item in output["results"]] == ["allowed"]
    assert output["results"][0]["bm25Rank"] == 1
    assert output["results"][0]["vectorRank"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "error", "expected"),
    [
        ("embedding", RuntimeError("embedding"), "Qwen embedding 分支失败"),
        ("vector", RuntimeError("milvus"), "Milvus 向量召回失败"),
        ("bm25", RuntimeError("source"), "BM25L 关键词召回失败"),
        ("rerank", RuntimeError("rerank"), "Qwen rerank 分支失败"),
    ],
)
async def test_required_branch_failures_are_safe(
    field: str, error: Exception, expected: str
) -> None:
    item = chunk("a", "告警")
    provider = FakeProvider(
        embedding_error=error if field == "embedding" else None,
        rerank_error=error if field == "rerank" else None,
    )
    source = FakeChunks([item], error=error if field == "bm25" else None)
    vector = FakeVector([entity(item, 0.9)], error=error if field == "vector" else None)

    with pytest.raises(RetrievalError, match=expected):
        await service(
            provider,
            [item],
            [entity(item, 0.9)],
            chunk_source=source,
            vector=vector,
        ).retrieve("告警")


@pytest.mark.asyncio
async def test_empty_results_do_not_call_rerank_or_generate_fallback() -> None:
    provider = FakeProvider(rerank_calls=[])
    output = await service(provider, [], []).retrieve("不存在")

    assert output == {"results": [], "citations": []}
    assert provider.rerank_calls == []


@pytest.mark.asyncio
async def test_rerank_candidates_are_limited_to_twenty_and_default_top_k_is_five() -> None:
    chunks = [chunk(str(index), "告警") for index in range(21)]
    provider = FakeProvider(rerank_calls=[])
    output = await service(
        provider,
        chunks,
        [entity(item, 1.0 - index / 100) for index, item in enumerate(chunks)],
    ).retrieve("告警")

    assert len(output["results"]) == 5
    assert provider.rerank_calls and len(provider.rerank_calls[0][1]) == 20
    assert provider.rerank_calls[0][2] == 20


@pytest.mark.asyncio
async def test_tool_is_named_and_scope_is_fixed() -> None:
    item = chunk("a", "告警")
    provider = FakeProvider(rerank_results=[RerankResult(0, 3.0)])
    tool = create_knowledge_retrieval_tool(
        owner_scope=OwnerScope("user-a"),
        provider_factory=lambda: provider_context(provider),
        chunk_source=FakeChunks([item]),
        vector_recall=FakeVector([entity(item, 0.9)]),
    )

    assert tool.name == "knowledge_retrieval"
    output = await tool.ainvoke({"query": "告警", "knowledgeBaseIds": ["kb-b"]})
    assert output == {"results": [], "citations": []}


@pytest.mark.asyncio
async def test_invalid_input_does_not_call_any_provider_or_recall() -> None:
    provider = FakeProvider()
    source = FakeChunks([])
    vector = FakeVector([])
    retrieval = service(provider, [], [], chunk_source=source, vector=vector)

    with pytest.raises(RetrievalError, match="query"):
        await retrieval.retrieve(" ")
    with pytest.raises(RetrievalError, match="topK"):
        await retrieval.retrieve("告警", top_k=6)
    assert source.started is None
