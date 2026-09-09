"""Qwen 的异步模型适配器；第三方 SDK 仅在显式 factory 内加载。"""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field

from oncall_pilot.llm.config import ProviderConfig
from oncall_pilot.llm.contracts import (
    ChatClient,
    EmbeddingClient,
    ModelKind,
    ProviderError,
    ProviderReadiness,
    RerankResult,
)

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from openai.resources.embeddings import AsyncEmbeddings


def _safe_failure(exc: Exception) -> ProviderError:
    if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
        code = "PROVIDER_TIMEOUT"
    elif "Status" in type(exc).__name__ or "Authentication" in type(exc).__name__:
        code = "PROVIDER_HTTP_ERROR"
    else:
        code = "PROVIDER_REQUEST_FAILED"
    return ProviderError(f"{code}: 模型请求失败，上游详情 [redacted]")


class _LangChainChat:
    def __init__(self, model: ChatOpenAI) -> None:
        self._model = model

    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        # 上游 tracing_context 的 parent 注解含未参数化 Mapping；此处不使用 parent。
        from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]

        # 项目未配置远程 tracing，不允许 SDK 环境变量旁路上传请求。
        with tracing_context(enabled=False):
            kwargs: dict[str, Any] = {} if max_tokens is None else {"max_tokens": max_tokens}
            message = await self._model.ainvoke(prompt, **kwargs)
        # 极小探测预算可能只消耗在模型推理上；有效的 length completion 仍证明就绪。
        if not isinstance(message.content, str) or (
            not message.content and message.response_metadata.get("finish_reason") != "length"
        ):
            raise ProviderError("PROVIDER_INVALID_RESPONSE: 对话响应没有文本")
        return message.content


class _OrderedEmbeddings:
    """保留 SDK 序列化，按协议 index 恢复顺序后交给 OpenAIEmbeddings。"""

    def __init__(self, resource: AsyncEmbeddings) -> None:
        self._resource = resource

    async def create(self, *, input: list[str], **kwargs: Any) -> dict[str, Any]:
        response = await self._resource.create(input=input, **kwargs)
        indices = [item.index for item in response.data]
        if any(type(i) is not int for i in indices) or sorted(indices) != list(range(len(input))):
            raise ProviderError("PROVIDER_INVALID_RESPONSE: 向量索引不完整")
        response.data.sort(key=lambda item: item.index)
        # 不让 SDK 的宽松响应对象在序列化 warning 中回显不可信值。
        return response.model_dump(warnings=False)


class _RerankItem(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    index: int = Field(ge=0)
    relevance_score: float = Field(allow_inf_nan=False)


class _RerankOutput(BaseModel):
    results: list[_RerankItem]


class _RerankResponse(BaseModel):
    output: _RerankOutput


class QwenOpenAIProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        chat_client: ChatClient,
        embedding_client: EmbeddingClient,
        rerank_client: httpx.AsyncClient,
    ) -> None:
        self._config = config
        self._chat = chat_client
        self._embedding = embedding_client
        self._rerank = rerank_client

    @property
    def context_window_tokens(self) -> int:
        return self._config.context_window_tokens

    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str:
        if not isinstance(cast(object, prompt), str) or not prompt.strip():
            raise ProviderError("PROVIDER_INVALID_INPUT: 提示不能为空")
        if max_tokens is not None and (type(max_tokens) is not int or max_tokens <= 0):
            raise ProviderError("PROVIDER_INVALID_INPUT: max_tokens 必须为正整数")
        try:
            return await self._chat.complete(prompt, max_tokens=max_tokens)
        except Exception as exc:
            failure = _safe_failure(exc)
        raise failure

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(not isinstance(cast(object, text), str) for text in texts):
            raise ProviderError("PROVIDER_INVALID_INPUT: 向量输入必须为字符串")
        result: list[list[float]] = []
        size = self._config.llm.embedding.chunk_size
        try:
            for start in range(0, len(texts), size):
                batch = texts[start : start + size]
                vectors = await self._embedding.aembed_documents(batch)
                if len(vectors) != len(batch) or any(
                    len(vector) != 1024
                    or any(isinstance(value, bool) or not math.isfinite(value) for value in vector)
                    for vector in vectors
                ):
                    raise ProviderError("PROVIDER_INVALID_RESPONSE: 向量数量或维度无效")
                result.extend(vectors)
            return result
        except Exception as exc:
            failure = _safe_failure(exc)
        raise failure

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int | None = None,
    ) -> list[RerankResult]:
        if (
            not isinstance(cast(object, query), str)
            or not query.strip()
            or any(not isinstance(cast(object, document), str) for document in documents)
        ):
            raise ProviderError("PROVIDER_INVALID_INPUT: 查询和文档必须为文本")
        if top_n is not None and (type(top_n) is not int or top_n <= 0):
            raise ProviderError("PROVIDER_INVALID_INPUT: top_n 必须为正整数")
        if not documents:
            return []
        count = min(top_n, len(documents)) if top_n is not None else len(documents)
        endpoint = self._config.llm.rerank
        body = {
            "model": endpoint.model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": count, "return_documents": False},
        }
        failure = ProviderError("PROVIDER_REQUEST_FAILED: 重排失败 [redacted]")
        for attempt in range(endpoint.retries + 1):
            retryable = False
            try:
                response = await asyncio.wait_for(
                    self._rerank.post(
                        endpoint.base_url,
                        json=body,
                        headers={"Authorization": f"Bearer {endpoint.api_key.get_secret_value()}"},
                        timeout=endpoint.timeout,
                    ),
                    timeout=endpoint.timeout,
                )
                response.raise_for_status()
                items = _RerankResponse.model_validate(response.json()).output.results
                indices = [item.index for item in items]
                if (
                    len(items) != count
                    or len(set(indices)) != count
                    or any(index >= len(documents) for index in indices)
                ):
                    raise ProviderError("PROVIDER_INVALID_RESPONSE: 重排索引无效")
                return [RerankResult(item.index, item.relevance_score) for item in items]
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                retryable = status in {408, 429} or 500 <= status < 600
                failure = _safe_failure(exc)
            except (httpx.TransportError, TimeoutError, asyncio.TimeoutError) as exc:
                retryable = True
                failure = _safe_failure(exc)
            except Exception as exc:
                failure = _safe_failure(exc)
            if not retryable or attempt == endpoint.retries:
                break
            await asyncio.sleep(min(0.1 * 2**attempt, 2))
        raise failure

    async def readiness(self, kind: ModelKind = "chat") -> ProviderReadiness:
        if kind not in {"chat", "embedding", "rerank"}:
            raise ProviderError("PROVIDER_INVALID_INPUT: 未知模型类别")
        endpoint = getattr(self._config.llm, kind)
        start = perf_counter()
        error: str | None = None
        try:
            if kind == "chat":
                await self.chat("请回复好", max_tokens=8)
            elif kind == "embedding":
                await self.embed_documents(["好"])
            else:
                await self.rerank("好", ["好"], top_n=1)
        except ProviderError as exc:
            error = str(exc)

        def redact(value: str) -> str:
            keys = {
                getattr(self._config.llm, name).api_key.get_secret_value()
                for name in ("chat", "embedding", "rerank")
            }
            for key in sorted(keys, key=len, reverse=True):
                if key:
                    value = value.replace(key, "[redacted]")
            return value

        return ProviderReadiness(
            provider=self._config.llm.provider,
            model=redact(endpoint.model),
            baseUrl=redact(endpoint.base_url),
            latency=(perf_counter() - start) * 1000,
            ready=error is None,
            error=error,
        )


@asynccontextmanager
async def open_qwen_provider(
    config: ProviderConfig,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    rerank_client: httpx.AsyncClient | None = None,
) -> AsyncGenerator[QwenOpenAIProvider]:
    """创建并释放自有 client；注入的 rerank client 生命周期由调用方管理。"""
    config.require_credentials()
    stack = AsyncExitStack()
    try:
        try:
            provider = await _create_provider(config, stack, transport, rerank_client)
        except Exception as exc:
            failure = _safe_failure(exc)
        else:
            yield provider
            return
        raise failure
    finally:
        await _close_clients(stack)


async def _close_clients(stack: AsyncExitStack) -> None:
    failure: ProviderError | None = None
    try:
        await stack.aclose()
    except Exception as exc:
        failure = _safe_failure(exc)
    if failure is not None:
        # 清理也可能发生在处理调用方异常时，不公开此前异常链。
        raise failure from None


async def _create_provider(
    config: ProviderConfig,
    stack: AsyncExitStack,
    transport: httpx.AsyncBaseTransport | None,
    rerank_client: httpx.AsyncClient | None,
) -> QwenOpenAIProvider:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from openai import AsyncOpenAI, OpenAI

    async def isolate_headers(request: httpx.Request) -> None:
        endpoint = (
            config.llm.embedding if request.url.path.endswith("/embeddings") else config.llm.chat
        )
        # SDK 可读取 OPENAI_CUSTOM_HEADERS。重建最小协议头，环境注入不能出网。
        request.headers = httpx.Headers(
            {
                "Host": request.url.netloc.decode("ascii"),
                "Authorization": f"Bearer {endpoint.api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Content-Length": str(len(request.content)),
            }
        )
        if request.url.path.endswith("/chat/completions"):
            # ChatOpenAI 使用 SDK with_raw_response，此头控制本地返回类型。
            request.headers["X-Stainless-Raw-Response"] = "true"

    sync_http = stack.enter_context(httpx.Client(trust_env=False))
    async_http = await stack.enter_async_context(
        httpx.AsyncClient(
            transport=transport, trust_env=False, event_hooks={"request": [isolate_headers]}
        )
    )
    rerank_http = rerank_client
    if rerank_http is None:
        rerank_http = await stack.enter_async_context(httpx.AsyncClient(trust_env=False))
    chat = config.llm.chat
    embedding = config.llm.embedding

    def sdk_options(endpoint: object) -> dict[str, Any]:
        from oncall_pilot.llm.config import ModelEndpoint

        assert isinstance(endpoint, ModelEndpoint)
        return {
            "api_key": endpoint.api_key.get_secret_value(),
            "base_url": endpoint.base_url,
            "timeout": endpoint.timeout,
            "max_retries": endpoint.retries,
            "organization": "",
            "project": "",
            "admin_api_key": "",
            "webhook_secret": "",
        }

    chat_sync = OpenAI(**sdk_options(chat), http_client=cast(Any, sync_http))
    chat_async = AsyncOpenAI(**sdk_options(chat), http_client=cast(Any, async_http))
    embed_sync = OpenAI(**sdk_options(embedding), http_client=cast(Any, sync_http))
    embed_async = AsyncOpenAI(**sdk_options(embedding), http_client=cast(Any, async_http))
    chat_model = ChatOpenAI(
        model=chat.model,
        api_key=chat.api_key,
        base_url=chat.base_url,
        temperature=chat.temperature,
        timeout=chat.timeout,
        max_retries=chat.retries,
        organization="oncall-pilot",
        openai_proxy="",
        output_version="v0",
        use_responses_api=False,
        stream_usage=False,
        client=chat_sync.chat.completions,
        async_client=chat_async.chat.completions,
        root_client=chat_sync,
        root_async_client=chat_async,
    )
    embedding_model = OpenAIEmbeddings(
        model=embedding.model,
        api_key=embedding.api_key,
        base_url=embedding.base_url,
        dimensions=embedding.dimensions,
        check_embedding_ctx_length=False,
        chunk_size=embedding.chunk_size,
        timeout=embedding.timeout,
        max_retries=embedding.retries,
        organization="oncall-pilot",
        openai_proxy="",
        openai_api_type="",
        api_version="",
        model_kwargs={"encoding_format": "float"},
        client=embed_sync.embeddings,
        async_client=_OrderedEmbeddings(embed_async.embeddings),
    )
    return QwenOpenAIProvider(
        config,
        chat_client=_LangChainChat(chat_model),
        embedding_client=embedding_model,
        rerank_client=rerank_http,
    )
