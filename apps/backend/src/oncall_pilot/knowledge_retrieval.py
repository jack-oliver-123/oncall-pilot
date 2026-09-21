"""Agent 可调用的 tenant-scoped 混合知识检索。"""

from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from oncall_pilot.generated_contracts import KnowledgeRetrievalOutput
from oncall_pilot.knowledge import default_knowledge_base_id
from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.llm.contracts import LlmProvider, ProviderError, RerankResult
from oncall_pilot.llm.qwen import open_qwen_provider
from oncall_pilot.memory.scope import OwnerScope, require_scope_id
from oncall_pilot.vector_store.store import MilvusVectorStore

_RRF_K = 60
_RECALL_LIMIT = 64
_RERANK_LIMIT = 20
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ASCII = re.compile(r"[A-Za-z0-9_$./:#-]+")


class RetrievalError(RuntimeError):
    """不携带 query、凭据或上游响应的安全检索错误。"""


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    owner_user_id: str
    tenant_id: str
    content: str
    source: str
    metadata: Mapping[str, Any]

    @classmethod
    def from_entity(cls, entity: Mapping[str, Any]) -> IndexedChunk:
        values = {
            key: entity.get(key)
            for key in (
                "chunkId",
                "documentId",
                "knowledgeBaseId",
                "ownerUserId",
                "tenantId",
                "content",
                "source",
                "metadata",
            )
        }
        ids = {
            key: require_scope_id(value)
            for key, value in values.items()
            if key in {"chunkId", "documentId", "knowledgeBaseId", "ownerUserId", "tenantId"}
        }
        if values["ownerUserId"] != values["tenantId"]:
            raise RetrievalError("检索语料归属校验失败。")
        if not isinstance(values["content"], str) or not isinstance(values["source"], str):
            raise RetrievalError("检索语料文本校验失败。")
        metadata = values["metadata"]
        if not isinstance(metadata, Mapping):
            raise RetrievalError("检索语料 metadata 校验失败。")
        return cls(
            ids["chunkId"],
            ids["documentId"],
            ids["knowledgeBaseId"],
            ids["ownerUserId"],
            ids["tenantId"],
            values["content"],
            values["source"],
            dict(cast(Mapping[str, Any], metadata)),
        )


class IndexedChunkSource(Protocol):
    async def list_chunks(
        self, *, owner_user_id: str, knowledge_base_ids: Sequence[str]
    ) -> list[IndexedChunk]: ...


class VectorRecall(Protocol):
    async def search(
        self,
        vector: Sequence[float],
        *,
        owner_user_id: str,
        knowledge_base_ids: Sequence[str],
        limit: int,
    ) -> list[Mapping[str, Any]]: ...


class MilvusIndexedChunkSource:
    def __init__(self, store: MilvusVectorStore) -> None:
        self._store = store

    async def list_chunks(
        self, *, owner_user_id: str, knowledge_base_ids: Sequence[str]
    ) -> list[IndexedChunk]:
        try:
            rows = await asyncio.to_thread(
                self._store.list_chunks,
                owner_user_id=owner_user_id,
                allowed_knowledge_base_ids=knowledge_base_ids,
            )
            return [IndexedChunk.from_entity(row.get("entity", row)) for row in rows]
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError("BM25L 语料读取失败。") from None


class MilvusVectorRecall:
    def __init__(self, store: MilvusVectorStore) -> None:
        self._store = store

    async def search(
        self,
        vector: Sequence[float],
        *,
        owner_user_id: str,
        knowledge_base_ids: Sequence[str],
        limit: int,
    ) -> list[Mapping[str, Any]]:
        try:
            rows = await asyncio.to_thread(
                self._store.search,
                vector,
                owner_user_id=owner_user_id,
                allowed_knowledge_base_ids=knowledge_base_ids,
                limit=limit,
            )
            return [cast(Mapping[str, Any], row) for row in rows]
        except Exception:
            raise RetrievalError("Milvus 向量召回失败。") from None


def tokenize(text: str) -> list[str]:
    """保留中文单字/bigram 和完整 ASCII 运维标识。"""
    tokens: list[str] = []
    cjk_run: list[str] = []

    def flush_cjk() -> None:
        if not cjk_run:
            return
        tokens.extend(cjk_run)
        tokens.extend("".join(cjk_run[index : index + 2]) for index in range(len(cjk_run) - 1))
        cjk_run.clear()

    index = 0
    while index < len(text):
        match = _CJK.match(text, index)
        if match:
            cjk_run.append(match.group())
            index = match.end()
            continue
        flush_cjk()
        match = _ASCII.match(text, index)
        if match:
            tokens.append(match.group().casefold())
            index = match.end()
            continue
        index += 1
    flush_cjk()
    return tokens


def bm25l_scores(query: str, documents: Sequence[str]) -> list[float]:
    """使用正 IDF 的 BM25L；不相交文档得 0，结果永不为负。"""
    query_terms = set(tokenize(query))
    corpus = [tokenize(document) for document in documents]
    count = len(corpus)
    if not query_terms or not count:
        return [0.0] * count
    lengths = [len(tokens) for tokens in corpus]
    average_length = sum(lengths) / count or 1.0
    document_frequency = Counter(
        term for tokens in corpus for term in set(tokens) if term in query_terms
    )
    scores: list[float] = []
    k1, b, delta = 1.5, 0.75, 0.5
    for tokens, length in zip(corpus, lengths, strict=True):
        counts = Counter(tokens)
        normalizer = k1 * (1 - b + b * length / average_length)
        score = 0.0
        for term in query_terms:
            term_frequency = counts.get(term, 0)
            if not term_frequency:
                continue
            df = document_frequency[term]
            idf = math.log1p((count - df + 0.5) / (df + 0.5))
            score += idf * (term_frequency * (k1 + 1) / (term_frequency + normalizer) + delta)
        scores.append(max(0.0, score))
    return scores


@dataclass(frozen=True, slots=True)
class _Record:
    chunk: IndexedChunk
    vector_rank: int | None = None
    vector_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None
    rrf_score: float = 0.0
    rerank_rank: int | None = None
    rerank_score: float | None = None


class KnowledgeRetrievalService:
    def __init__(
        self,
        *,
        provider_factory: Callable[[], Any],
        chunk_source: IndexedChunkSource,
        vector_recall: VectorRecall,
        owner_scope: OwnerScope,
        allowed_knowledge_base_ids: Sequence[str] | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._chunk_source = chunk_source
        self._vector_recall = vector_recall
        self._scope = owner_scope
        configured = (
            allowed_knowledge_base_ids
            if allowed_knowledge_base_ids is not None
            else [default_knowledge_base_id(owner_scope.owner_user_id)]
        )
        self._allowed_kbs = tuple(dict.fromkeys(require_scope_id(value) for value in configured))

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        knowledge_base_ids: Sequence[str] | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        self._validate_input(query, top_k)
        kbs = self._narrow_ids(knowledge_base_ids, self._allowed_kbs)
        docs = self._narrow_ids(document_ids, None)
        if kbs is None or not kbs:
            return self._empty()
        async with self._provider_factory() as provider:
            vector_task = asyncio.create_task(self._vector_branch(provider, query, kbs))
            bm25_task = asyncio.create_task(self._bm25_branch(query, kbs, docs))
            vector_result, bm25_result = await self._gather_required(vector_task, bm25_task)
            records = self._fuse(vector_result, bm25_result, docs)
            if not records:
                return self._empty()
            candidates = records[:_RERANK_LIMIT]
            try:
                reranked = await provider.rerank(
                    query, [record.chunk.content for record in candidates], top_n=len(candidates)
                )
            except ProviderError:
                raise RetrievalError("Qwen rerank 分支失败。") from None
            except Exception:
                raise RetrievalError("Qwen rerank 分支失败。") from None
            return self._serialize(candidates, reranked, top_k)

    async def _vector_branch(
        self, provider: LlmProvider, query: str, knowledge_base_ids: Sequence[str]
    ) -> list[tuple[IndexedChunk, float]]:
        try:
            vectors = await provider.embed_documents([query])
            if len(vectors) != 1:
                raise ValueError
            vector = vectors[0]
            if not vector or any(
                isinstance(value, bool) or not math.isfinite(value) for value in vector
            ):
                raise ValueError
        except Exception:
            raise RetrievalError("Qwen embedding 分支失败。") from None
        try:
            hits = await self._vector_recall.search(
                vector,
                owner_user_id=self._scope.owner_user_id,
                knowledge_base_ids=knowledge_base_ids,
                limit=_RECALL_LIMIT,
            )
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError("Milvus 向量召回失败。") from None
        result: list[tuple[IndexedChunk, float]] = []
        seen: set[str] = set()
        for hit in hits:
            try:
                entity = hit.get("entity", hit)
                chunk = IndexedChunk.from_entity(cast(Mapping[str, Any], entity))
                self._scope.require_owner(chunk.owner_user_id)
                if chunk.knowledge_base_id not in knowledge_base_ids or chunk.chunk_id in seen:
                    continue
                raw_score = hit.get("distance", hit.get("score"))
                if (
                    isinstance(raw_score, bool)
                    or not isinstance(raw_score, (int, float))
                    or not math.isfinite(raw_score)
                ):
                    raise ValueError
                seen.add(chunk.chunk_id)
                result.append((chunk, float(raw_score)))
            except RetrievalError:
                raise RetrievalError("Milvus 向量结果校验失败。") from None
            except Exception:
                raise RetrievalError("Milvus 向量结果校验失败。") from None
        return sorted(result, key=lambda item: (-item[1], item[0].chunk_id))

    async def _bm25_branch(
        self, query: str, knowledge_base_ids: Sequence[str], document_ids: Sequence[str] | None
    ) -> list[tuple[IndexedChunk, float]]:
        try:
            chunks = await self._chunk_source.list_chunks(
                owner_user_id=self._scope.owner_user_id, knowledge_base_ids=knowledge_base_ids
            )
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError("BM25L 关键词召回失败。") from None
        filtered = [
            chunk
            for chunk in chunks
            if self._scope.owner_user_id == chunk.owner_user_id
            and chunk.tenant_id == self._scope.tenant_id
            and chunk.knowledge_base_id in knowledge_base_ids
            and (document_ids is None or chunk.document_id in document_ids)
        ]
        try:
            scores = bm25l_scores(query, [chunk.content for chunk in filtered])
        except Exception:
            raise RetrievalError("BM25L 关键词召回失败。") from None
        return sorted(
            [(chunk, score) for chunk, score in zip(filtered, scores, strict=True) if score > 0],
            key=lambda item: (-item[1], item[0].chunk_id),
        )

    async def _gather_required(
        self, vector_task: asyncio.Task[Any], bm25_task: asyncio.Task[Any]
    ) -> tuple[Any, Any]:
        results = await asyncio.gather(vector_task, bm25_task, return_exceptions=True)
        failures = [result for result in results if isinstance(result, BaseException)]
        if failures:
            for task in (vector_task, bm25_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(vector_task, bm25_task, return_exceptions=True)
            for result in results:
                if isinstance(result, RetrievalError):
                    raise result
            raise RetrievalError("知识检索分支失败。") from None
        return cast(tuple[Any, Any], tuple(results))

    def _fuse(
        self,
        vector: Sequence[tuple[IndexedChunk, float]],
        bm25: Sequence[tuple[IndexedChunk, float]],
        document_ids: Sequence[str] | None,
    ) -> list[_Record]:
        vector_ranked = [
            (chunk, score)
            for chunk, score in vector
            if document_ids is None or chunk.document_id in document_ids
        ]
        data: dict[str, _Record] = {}
        for rank, (chunk, score) in enumerate(vector_ranked, 1):
            data[chunk.chunk_id] = _Record(chunk, rank, score)
        for rank, (chunk, score) in enumerate(bm25, 1):
            current = data.get(chunk.chunk_id)
            if current is None:
                data[chunk.chunk_id] = _Record(chunk, bm25_rank=rank, bm25_score=score)
            else:
                data[chunk.chunk_id] = _Record(
                    current.chunk, current.vector_rank, current.vector_score, rank, score
                )
        records: list[_Record] = []
        for record in data.values():
            rrf = sum(
                1 / (_RRF_K + rank) for rank in (record.vector_rank, record.bm25_rank) if rank
            )
            records.append(
                _Record(
                    record.chunk,
                    record.vector_rank,
                    record.vector_score,
                    record.bm25_rank,
                    record.bm25_score,
                    rrf,
                )
            )
        return sorted(
            records,
            key=lambda item: (
                -item.rrf_score,
                min(rank for rank in (item.vector_rank, item.bm25_rank) if rank is not None),
                item.chunk.chunk_id,
            ),
        )

    def _serialize(
        self, candidates: Sequence[_Record], reranked: Sequence[RerankResult], top_k: int
    ) -> dict[str, Any]:
        if len(reranked) != len(candidates) or len({item.index for item in reranked}) != len(
            candidates
        ):
            raise RetrievalError("Qwen rerank 返回结果不完整。")
        result_records: list[_Record] = []
        for rank, item in enumerate(reranked, 1):
            if (
                type(item.index) is not int
                or item.index < 0
                or item.index >= len(candidates)
                or not math.isfinite(item.relevance_score)
            ):
                raise RetrievalError("Qwen rerank 返回结果无效。")
            candidate = candidates[item.index]
            result_records.append(
                _Record(
                    candidate.chunk,
                    candidate.vector_rank,
                    candidate.vector_score,
                    candidate.bm25_rank,
                    candidate.bm25_score,
                    candidate.rrf_score,
                    rank,
                    float(item.relevance_score),
                )
            )
        results = [self._result(record) for record in result_records[:top_k]]
        return KnowledgeRetrievalOutput.model_validate(
            {"results": results, "citations": results}
        ).model_dump(mode="json")

    @staticmethod
    def _result(record: _Record) -> dict[str, Any]:
        return {
            "chunkId": record.chunk.chunk_id,
            "documentId": record.chunk.document_id,
            "knowledgeBaseId": record.chunk.knowledge_base_id,
            "source": record.chunk.source,
            "excerpt": record.chunk.content,
            "metadata": dict(record.chunk.metadata),
            "vectorRank": record.vector_rank,
            "vectorScore": record.vector_score,
            "bm25Rank": record.bm25_rank,
            "bm25Score": record.bm25_score,
            "rrfScore": record.rrf_score,
            "rerankRank": record.rerank_rank,
            "rerankScore": record.rerank_score,
            "score": record.rerank_score,
        }

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"results": [], "citations": []}

    @staticmethod
    def _validate_input(query: str, top_k: int) -> None:
        if type(cast(object, query)) is not str or not query.strip():
            raise RetrievalError("检索 query 不能为空。")
        if type(cast(object, top_k)) is not int or not 1 <= top_k <= 5:
            raise RetrievalError("topK 必须是 1 到 5 的整数。")

    @staticmethod
    def _narrow_ids(
        values: Sequence[str] | None, allowed: Sequence[str] | None
    ) -> tuple[str, ...] | None:
        if values is None:
            return None if allowed is None else tuple(allowed)
        if isinstance(cast(object, values), (str, bytes)):
            raise RetrievalError("检索过滤器格式无效。")
        try:
            normalized = tuple(dict.fromkeys(require_scope_id(value) for value in values))
        except Exception:
            raise RetrievalError("检索过滤器格式无效。") from None
        if allowed is None:
            return normalized
        return tuple(value for value in normalized if value in allowed)


class KnowledgeRetrievalArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1)
    topK: int = Field(default=5, ge=1, le=5)
    knowledgeBaseIds: list[str] | None = None
    documentIds: list[str] | None = None


def create_knowledge_retrieval_tool(
    *,
    owner_scope: OwnerScope,
    provider_factory: Callable[[], Any],
    chunk_source: IndexedChunkSource,
    vector_recall: VectorRecall,
    allowed_knowledge_base_ids: Sequence[str] | None = None,
) -> Any:
    """创建固定 owner scope 的 LangChain StructuredTool。"""
    from langchain_core.tools import StructuredTool

    service = KnowledgeRetrievalService(
        provider_factory=provider_factory,
        chunk_source=chunk_source,
        vector_recall=vector_recall,
        owner_scope=owner_scope,
        allowed_knowledge_base_ids=allowed_knowledge_base_ids,
    )

    async def invoke(
        query: str,
        topK: int = 5,
        knowledgeBaseIds: list[str] | None = None,
        documentIds: list[str] | None = None,
    ) -> dict[str, Any]:
        return await service.retrieve(
            query, top_k=topK, knowledge_base_ids=knowledgeBaseIds, document_ids=documentIds
        )

    return StructuredTool.from_function(
        coroutine=invoke,
        name="knowledge_retrieval",
        description="检索当前用户已成功索引的知识文档，并返回带阶段排名与分数的引用。",
        args_schema=KnowledgeRetrievalArgs,
    )


def qwen_retrieval_factory(config_dir: Path) -> Callable[[], Any]:
    @asynccontextmanager
    async def factory() -> AsyncGenerator[LlmProvider, None]:
        config = load_llm_config(config_dir)
        async with open_qwen_provider(config) as provider:
            yield provider

    return factory


def create_milvus_knowledge_retrieval_tool(
    *,
    owner_scope: OwnerScope,
    config_dir: Path,
    provider_factory: Callable[[], Any] | None = None,
    store: MilvusVectorStore | None = None,
) -> Any:
    vector_store = store or MilvusVectorStore(config_dir)
    return create_knowledge_retrieval_tool(
        owner_scope=owner_scope,
        provider_factory=provider_factory or qwen_retrieval_factory(config_dir),
        chunk_source=MilvusIndexedChunkSource(vector_store),
        vector_recall=MilvusVectorRecall(vector_store),
    )
