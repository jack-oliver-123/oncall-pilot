"""调用方可替换的模型边界和不可变结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ModelKind = Literal["chat", "embedding", "rerank"]


class ProviderError(RuntimeError):
    """只包含可公开错误类别，不携带上游响应。"""


@dataclass(frozen=True)
class RerankResult:
    index: int
    relevance_score: float


@dataclass(frozen=True)
class ProviderReadiness:
    provider: str
    model: str
    baseUrl: str
    latency: float
    ready: bool
    error: str | None = None


class ChatClient(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str: ...


class EmbeddingClient(Protocol):
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...


class LlmProvider(Protocol):
    @property
    def context_window_tokens(self) -> int: ...

    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankResult]: ...

    async def readiness(self, kind: ModelKind = "chat") -> ProviderReadiness: ...
