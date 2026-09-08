"""显式创建并拥有 LangChain 与 HTTP client；import 只声明。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING

import httpx

from oncall_pilot.llm.config import ProviderSettings
from oncall_pilot.llm.provider import QwenOpenAIProvider, safe_error
from oncall_pilot.llm.rerank import QwenRerankClient

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings


class LangChainChatClient:
    def __init__(self, client: ChatOpenAI) -> None:
        self._client = client

    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str:
        from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]

        with tracing_context(enabled=False):
            if max_tokens is None:
                message = await self._client.ainvoke(prompt)
            else:
                message = await self._client.ainvoke(prompt, max_tokens=max_tokens)
        if not isinstance(message.content, str):
            raise ValueError("对话结果必须是文本")
        return message.content


class LangChainEmbeddingClient:
    def __init__(self, client: OpenAIEmbeddings) -> None:
        self._client = client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]

        with tracing_context(enabled=False):
            return await self._client.aembed_documents(texts)


@asynccontextmanager
async def create_qwen_provider(
    settings: ProviderSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    rerank_transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncGenerator[QwenOpenAIProvider, None]:
    """上下文拥有所有创建的 client 和 transport；注入的 transport 也随之关闭。"""
    settings.require_credentials()
    async with AsyncExitStack() as stack:
        failure: Exception | None = None
        provider: QwenOpenAIProvider | None = None
        try:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
            from openai import AsyncOpenAI, OpenAI

            sync_http = stack.enter_context(httpx.Client(trust_env=False, follow_redirects=False))
            async_http = await stack.enter_async_context(
                httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False)
            )
            rerank_http = await stack.enter_async_context(
                httpx.AsyncClient(
                    transport=rerank_transport, trust_env=False, follow_redirects=False
                )
            )
            chat_config = settings.llm.chat
            embedding_config = settings.llm.embedding

            # 显式 SDK 对象阻断 project/webhook/organization 的环境默认值。
            # SDK 只负责传输配置；所有推理仍经由 ChatOpenAI/OpenAIEmbeddings。
            chat_sync = OpenAI(
                api_key=chat_config.apiKey.get_secret_value(),
                base_url=chat_config.baseUrl,
                timeout=chat_config.timeout,
                max_retries=chat_config.retries,
                organization="",
                project="",
                webhook_secret="",
                http_client=sync_http,
            )
            chat_async = AsyncOpenAI(
                api_key=chat_config.apiKey.get_secret_value(),
                base_url=chat_config.baseUrl,
                timeout=chat_config.timeout,
                max_retries=chat_config.retries,
                organization="",
                project="",
                webhook_secret="",
                http_client=async_http,
            )
            embedding_sync = OpenAI(
                api_key=embedding_config.apiKey.get_secret_value(),
                base_url=embedding_config.baseUrl,
                timeout=embedding_config.timeout,
                max_retries=embedding_config.retries,
                organization="",
                project="",
                webhook_secret="",
                http_client=sync_http,
            )
            embedding_async = AsyncOpenAI(
                api_key=embedding_config.apiKey.get_secret_value(),
                base_url=embedding_config.baseUrl,
                timeout=embedding_config.timeout,
                max_retries=embedding_config.retries,
                organization="",
                project="",
                webhook_secret="",
                http_client=async_http,
            )
            chat = ChatOpenAI(
                model=chat_config.model,
                temperature=chat_config.temperature,
                api_key=chat_config.apiKey,
                base_url=chat_config.baseUrl,
                timeout=chat_config.timeout,
                max_retries=chat_config.retries,
                organization="local-json",
                openai_proxy="",
                stream_usage=False,
                use_responses_api=False,
                output_version="v0",
                cache=False,
                client=chat_sync.chat.completions,
                async_client=chat_async.chat.completions,
                root_client=chat_sync,
                root_async_client=chat_async,
            )
            embedding = OpenAIEmbeddings(
                model=embedding_config.model,
                dimensions=embedding_config.dimensions,
                api_key=embedding_config.apiKey,
                base_url=embedding_config.baseUrl,
                timeout=embedding_config.timeout,
                max_retries=embedding_config.retries,
                organization="local-json",
                openai_proxy="",
                openai_api_type="",
                api_version="",
                check_embedding_ctx_length=False,
                chunk_size=embedding_config.chunk_size,
                model_kwargs={"encoding_format": "float"},
                client=embedding_sync.embeddings,
                async_client=embedding_async.embeddings,
            )
            provider = QwenOpenAIProvider(
                settings,
                chat_client=LangChainChatClient(chat),
                embedding_client=LangChainEmbeddingClient(embedding),
                rerank_client=QwenRerankClient(settings.llm.rerank, rerank_http),
            )
        except Exception as exc:
            failure = safe_error(exc, settings)
        if failure is not None:
            raise failure
        assert provider is not None
        yield provider
