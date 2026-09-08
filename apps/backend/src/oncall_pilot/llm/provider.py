"""不依赖具体模型库的异步边界、校验和安全错误。"""

from __future__ import annotations

import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol, TypeVar
from urllib.parse import quote

from oncall_pilot.llm.config import ModelCapability, ProviderSettings

Capability = Literal["chat", "embedding", "rerank"]
T = TypeVar("T")


@dataclass(frozen=True)
class RerankResult:
    index: int
    relevanceScore: float


@dataclass(frozen=True)
class Readiness:
    capability: Capability
    provider: str
    model: str
    baseUrl: str
    latency: float
    ready: bool
    error: str | None = None


class ProviderError(RuntimeError):
    """可公开的模型错误，不附带请求或服务端响应。"""


class ChatClient(Protocol):
    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str: ...


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class RerankClient(Protocol):
    async def rerank(
        self, query: str, documents: list[str], *, top_n: int
    ) -> list[RerankResult]: ...


class LlmProvider(Protocol):
    @property
    def chat_capability(self) -> ModelCapability: ...

    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankResult]: ...

    async def readiness(self, capability: Capability) -> Readiness: ...


def redact(text: str, settings: ProviderSettings) -> str:
    secrets = {
        value
        for config in (settings.llm.chat, settings.llm.embedding, settings.llm.rerank)
        for key in [config.apiKey.get_secret_value()]
        if key
        for value in (key, quote(key, safe=""))
    }
    if not secrets:
        return text
    return re.sub(
        "|".join(re.escape(key) for key in sorted(secrets, key=len, reverse=True)),
        lambda _: "[redacted]",
        text,
    )


def safe_error(exc: Exception, settings: ProviderSettings) -> ProviderError:
    # 原文仅用于检测需要替换的凭据；不公开 body、URL、请求内容或异常类型名。
    message = "模型调用失败，请检查本地配置与服务状态"
    if redact(str(exc), settings) != str(exc):
        message += "；敏感信息 [redacted]"
    return ProviderError(message)


def _validate_text(text: object) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("模型输入必须是非空文本")


class QwenOpenAIProvider:
    def __init__(
        self,
        settings: ProviderSettings,
        *,
        chat_client: ChatClient,
        embedding_client: EmbeddingClient,
        rerank_client: RerankClient,
    ) -> None:
        self._settings = settings
        self._chat = chat_client
        self._embedding = embedding_client
        self._rerank = rerank_client

    @property
    def chat_capability(self) -> ModelCapability:
        return self._settings.chat_capability

    async def _call(self, operation: Callable[[], Awaitable[T]]) -> T:
        try:
            return await operation()
        except Exception as exc:
            failure = safe_error(exc, self._settings)
        # 在 except 外抛出，避免原始异常保留为 __context__。
        raise failure

    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str:
        _validate_text(prompt)
        if max_tokens is not None and (type(max_tokens) is not int or max_tokens < 1):
            raise ProviderError("max_tokens 必须是正整数")
        result = await self._call(lambda: self._chat.chat(prompt, max_tokens=max_tokens))
        if not result.strip():
            raise ProviderError("对话服务返回了无效文本")
        return result

    async def embed(self, texts: list[str]) -> list[list[float]]:
        for text in texts:
            _validate_text(text)
        vectors: list[list[float]] = []
        batch_size = self._settings.llm.embedding.chunk_size
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            result = await self._call(lambda batch=batch: self._embedding.embed(batch))
            if len(result) != len(batch) or any(
                len(vector) != 1024
                or any(
                    type(value) not in (int, float) or not math.isfinite(value) for value in vector
                )
                for vector in result
            ):
                raise ProviderError("向量服务返回了无效数量、维度或数值")
            vectors.extend(result)
        return vectors

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankResult]:
        _validate_text(query)
        for text in documents:
            _validate_text(text)
        if top_n is not None and (type(top_n) is not int or top_n < 1 or top_n > len(documents)):
            raise ProviderError("top_n 必须是候选数量范围内的正整数")
        if not documents:
            return []
        count = len(documents) if top_n is None else top_n
        result = await self._call(lambda: self._rerank.rerank(query, documents, top_n=count))
        if (
            len(result) != count
            or len({item.index for item in result}) != count
            or any(
                type(item.index) is not int
                or not 0 <= item.index < len(documents)
                or type(item.relevanceScore) not in (int, float)
                or not math.isfinite(item.relevanceScore)
                for item in result
            )
        ):
            raise ProviderError("排序服务返回了无效索引、数量或分数")
        return result

    async def readiness(self, capability: Capability) -> Readiness:
        if capability not in ("chat", "embedding", "rerank"):
            raise ProviderError("未知模型能力")
        endpoint = getattr(self._settings.llm, capability)
        started = perf_counter()
        error: str | None = None
        try:
            if capability == "chat":
                # 一 token 探测可能只产生 reasoning；不要求生成完整可见答案。
                await self._call(lambda: self._chat.chat("hi", max_tokens=1))
            elif capability == "embedding":
                await self.embed(["hi"])
            else:
                await self.rerank("hi", ["hi"], top_n=1)
        except ProviderError as exc:
            error = str(exc)
        return Readiness(
            capability=capability,
            provider=redact(self._settings.llm.provider, self._settings),
            model=redact(endpoint.model, self._settings),
            baseUrl=redact(endpoint.baseUrl, self._settings),
            latency=(perf_counter() - started) * 1000,
            ready=error is None,
            error=error,
        )
