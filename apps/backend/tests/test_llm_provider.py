from __future__ import annotations

import asyncio
import json
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import cast

import httpx
import pytest

from oncall_pilot.llm.config import ProviderSettings, load_provider_settings
from oncall_pilot.llm.factory import create_qwen_provider
from oncall_pilot.llm.provider import (
    Capability,
    LlmProvider,
    ProviderError,
    QwenOpenAIProvider,
    RerankResult,
    redact,
)
from oncall_pilot.project_config import ProjectConfigError


@pytest.fixture
def settings(tmp_path: Path) -> ProviderSettings:
    config = {
        "llm": {
            "chat": {"apiKey": "chat-secret", "baseUrl": "https://chat.test/v1"},
            "embedding": {"apiKey": "embedding-secret", "baseUrl": "https://embed.test/v1"},
            "rerank": {"apiKey": "rerank-secret", "baseUrl": "https://rank.test/text-rerank"},
        },
        "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 1000000}},
    }
    (tmp_path / "project.json").write_text(json.dumps(config), encoding="utf-8")
    return load_provider_settings(tmp_path)


def success(request: httpx.Request) -> httpx.Response:
    body = cast(dict[str, object], json.loads(request.content))
    if request.url.host == "chat.test":
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "就绪"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    if request.url.host == "embed.test":
        texts = cast(list[str], body["input"])
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": body["model"],
                "data": [
                    {
                        "object": "embedding",
                        "index": i,
                        "embedding": [float(text.split(":")[0]) if ":" in text else 1.0] * 1024,
                    }
                    for i, text in enumerate(texts)
                ],
            },
        )
    params = cast(dict[str, object], body["parameters"])
    inputs = cast(dict[str, object], body["input"])
    docs = cast(list[str], inputs["documents"])
    count = cast(int, params["top_n"])
    return httpx.Response(
        200,
        json={
            "output": {
                "results": [
                    {"index": len(docs) - i - 1, "relevance_score": 0.95 - i * 0.1}
                    for i in range(count)
                ]
            },
        },
    )


async def test_real_langchain_clients_emit_configured_payloads(settings: ProviderSettings) -> None:
    requests: list[httpx.Request] = []
    rerank_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return success(request)

    def rank_handler(request: httpx.Request) -> httpx.Response:
        rerank_requests.append(request)
        return success(request)

    async with create_qwen_provider(
        settings,
        transport=httpx.MockTransport(handler),
        rerank_transport=httpx.MockTransport(rank_handler),
    ) as concrete:
        provider: LlmProvider = concrete
        assert provider.chat_capability.contextWindowTokens == 1000000
        assert await provider.chat("排查错误") == "就绪"
        texts = [f"{i}:中文\n 原始字符串" for i in range(25)]
        vectors = await provider.embed(texts)
        assert [v[0] for v in vectors] == list(range(25))
        assert all(len(v) == 1024 for v in vectors)
        assert await provider.rerank("原因", ["候选一", "候选二"], top_n=1) == [
            RerankResult(index=1, relevanceScore=0.95)
        ]
        assert await provider.embed([]) == []
        assert await provider.rerank("问题", []) == []

    assert len(requests) == 4
    chat = requests[0]
    chat_body = json.loads(chat.content)
    assert chat.url.path == "/v1/chat/completions"
    assert chat.headers["authorization"] == "Bearer chat-secret"
    assert chat_body["model"] == "qwen3.7-max"
    assert chat_body["temperature"] == 0.2
    assert chat_body["messages"] == [{"role": "user", "content": "排查错误"}]
    batches = [json.loads(r.content) for r in requests[1:]]
    assert [len(body["input"]) for body in batches] == [10, 10, 5]
    assert [text for body in batches for text in body["input"]] == texts
    for request, body in zip(requests[1:], batches, strict=True):
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer embedding-secret"
        assert body["model"] == "text-embedding-v4"
        assert body["dimensions"] == 1024
        assert body["encoding_format"] == "float"
    assert len(rerank_requests) == 1
    assert rerank_requests[0].headers["authorization"] == "Bearer rerank-secret"
    assert json.loads(rerank_requests[0].content) == {
        "model": "qwen3-vl-rerank",
        "input": {"query": "原因", "documents": ["候选一", "候选二"]},
        "parameters": {"top_n": 1, "return_documents": False},
    }
    for request in requests + rerank_requests:
        assert request.extensions["timeout"] == dict.fromkeys(
            ("connect", "read", "write", "pool"), 120
        )


@pytest.mark.parametrize("capability", ["chat", "embedding", "rerank"])
async def test_readiness_makes_minimal_request(
    settings: ProviderSettings, capability: Capability
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return success(request)

    async with create_qwen_provider(
        settings,
        transport=httpx.MockTransport(handler),
        rerank_transport=httpx.MockTransport(handler),
    ) as provider:
        result = await provider.readiness(capability)
    assert result.ready and result.error is None and result.latency >= 0
    assert result.provider == "qwen-openai" and result.capability == capability
    assert result.model == getattr(settings.llm, capability).model
    assert result.baseUrl == getattr(settings.llm, capability).baseUrl
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    if capability == "chat":
        assert payload.get("max_tokens") == 1 or payload.get("max_completion_tokens") == 1
    elif capability == "embedding":
        assert payload["input"] == ["hi"]
    else:
        assert payload["input"] == {"query": "hi", "documents": ["hi"]}


@pytest.mark.parametrize("capability", ["chat", "embedding", "rerank"])
@pytest.mark.parametrize(
    ("failure", "recover", "expected_attempts"),
    [
        (429, True, 2),
        (500, False, 3),
        (401, False, 1),
        ("timeout", False, 3),
    ],
)
async def test_timeout_retry_policy(
    settings: ProviderSettings,
    capability: Capability,
    failure: int | str,
    recover: bool,
    expected_attempts: int,
) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if recover and len(attempts) > 1:
            return success(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("chat-secret embedding-secret rerank-secret", request=request)
        return httpx.Response(
            cast(int, failure),
            headers={"retry-after-ms": "1"},
            json={
                "error": {"message": "chat-secret embedding-secret rerank-secret private-body"},
            },
        )

    async with create_qwen_provider(
        settings,
        transport=httpx.MockTransport(handler),
        rerank_transport=httpx.MockTransport(handler),
    ) as provider:
        result = await provider.readiness(capability)
    assert len(attempts) == expected_attempts
    assert result.ready is recover
    serialized = json.dumps(asdict(result))
    for key in ("chat-secret", "embedding-secret", "rerank-secret", "private-body"):
        assert key not in serialized


async def test_environment_cannot_override_json(
    settings: ProviderSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import langsmith

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("不允许创建 tracing client")

    monkeypatch.setattr(langsmith, "Client", forbidden)
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "OPENAI_ORGANIZATION",
        "OPENAI_PROJECT_ID",
        "OPENAI_PROXY",
        "OPENAI_API_TYPE",
        "OPENAI_API_VERSION",
        "OPENAI_WEBHOOK_SECRET",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
    ):
        monkeypatch.setenv(name, "environment-secret")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer environment-secret")
    monkeypatch.setenv("LC_OUTPUT_VERSION", "invalid")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "environment-secret" not in str(request.url)
        assert "environment-secret" not in str(request.headers)
        assert "environment-secret" not in request.content.decode()
        return success(request)

    async with create_qwen_provider(
        settings,
        transport=httpx.MockTransport(handler),
        rerank_transport=httpx.MockTransport(handler),
    ) as provider:
        for capability in ("chat", "embedding", "rerank"):
            assert (await provider.readiness(capability)).ready
    assert len(requests) == 3


class FailingClients:
    def __init__(self, error: Exception | asyncio.CancelledError) -> None:
        self.error = error

    async def chat(self, prompt: str, *, max_tokens: int | None = None) -> str:
        raise self.error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise self.error

    async def rerank(self, query: str, documents: list[str], *, top_n: int) -> list[RerankResult]:
        raise self.error


@pytest.mark.parametrize("capability", ["chat", "embedding", "rerank"])
async def test_injected_errors_redact_all_keys_and_do_not_chain(
    settings: ProviderSettings, capability: Capability
) -> None:
    fake = FailingClients(ValueError("chat-secret embedding-secret rerank-secret private"))
    provider = QwenOpenAIProvider(
        settings, chat_client=fake, embedding_client=fake, rerank_client=fake
    )
    result = await provider.readiness(capability)
    assert not result.ready and "[redacted]" in str(result.error)
    assert "secret" not in repr(result) and "private" not in repr(result)
    with pytest.raises(ProviderError) as caught:
        await provider.chat("hi")
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "chat-secret" not in "".join(traceback.format_exception(caught.value))
    assert redact("chat-secret/embedding-secret/rerank-secret", settings) == "/".join(
        ["[redacted]"] * 3
    )


@pytest.mark.parametrize("capability", ["chat", "embedding", "rerank"])
async def test_cancellation_propagates(settings: ProviderSettings, capability: Capability) -> None:
    fake = FailingClients(asyncio.CancelledError())
    provider = QwenOpenAIProvider(
        settings, chat_client=fake, embedding_client=fake, rerank_client=fake
    )
    with pytest.raises(asyncio.CancelledError):
        await provider.readiness(capability)


async def test_empty_credentials_fail_before_client_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: ProviderSettings
) -> None:
    config = settings.model_dump(mode="json")
    config["llm"]["chat"]["apiKey"] = " "
    (tmp_path / "project.json").write_text(json.dumps(config), encoding="utf-8")
    no_key = load_provider_settings(tmp_path)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("缺少凭据时构造 client")

    monkeypatch.setattr(httpx, "Client", forbidden)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    with pytest.raises(ProjectConfigError, match="llm.chat.apiKey"):
        async with create_qwen_provider(no_key):
            pytest.fail("不应进入上下文")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"output": {"results": []}},
        {"output": {"results": [{"index": 7, "relevance_score": 0.8}]}},
        {"output": {"results": [{"index": 0, "relevance_score": "secret"}]}},
        {"output": {"results": [{"index": True, "relevance_score": 0.8}]}},
    ],
)
async def test_malformed_rerank_never_falls_back(
    settings: ProviderSettings, payload: dict[str, object]
) -> None:
    async with create_qwen_provider(
        settings, rerank_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as provider:
        assert not (await provider.readiness("rerank")).ready


@pytest.mark.parametrize("dimension", [0, 512, 1025])
async def test_wrong_embedding_dimension_fails(settings: ProviderSettings, dimension: int) -> None:
    async with create_qwen_provider(
        settings,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "data": [{"index": 0, "embedding": [0.1] * dimension}],
                },
            )
        ),
    ) as provider:
        assert not (await provider.readiness("embedding")).ready


class ClosingTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.closed = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return success(request)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
async def test_context_closes_owned_transports(settings: ProviderSettings, outcome: str) -> None:
    transport, rank_transport = ClosingTransport(), ClosingTransport()
    try:
        async with create_qwen_provider(
            settings, transport=transport, rerank_transport=rank_transport
        ) as provider:
            await provider.chat("hi")
            if outcome == "failure":
                raise ValueError("调用者错误")
            if outcome == "cancel":
                raise asyncio.CancelledError
    except (ValueError, asyncio.CancelledError):
        assert outcome != "success"
    assert transport.closed and rank_transport.closed


async def test_factory_failure_closes_clients_and_redacts(
    settings: ProviderSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import langchain_openai

    def fail(*args: object, **kwargs: object) -> None:
        raise ValueError("chat-secret embedding-secret rerank-secret")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", fail)
    transport, rank_transport = ClosingTransport(), ClosingTransport()
    with pytest.raises(ProviderError, match=r"\[redacted\]") as caught:
        async with create_qwen_provider(
            settings, transport=transport, rerank_transport=rank_transport
        ):
            pytest.fail("构造失败后不应 yield")
    assert caught.value.__context__ is None
    assert transport.closed and rank_transport.closed


async def test_custom_parameters_reach_real_clients(
    settings: ProviderSettings, tmp_path: Path
) -> None:
    config = settings.model_dump(mode="json")
    for capability in ("chat", "embedding", "rerank"):
        config["llm"][capability]["timeout"] = 0.25
        config["llm"][capability]["retries"] = 0
    config["llm"]["chat"]["model"] = "custom-chat"
    config["llm"]["chat"]["temperature"] = 0.7
    config["llm"]["embedding"]["chunk_size"] = 3
    config["modelCapabilities"]["custom-chat"] = {"contextWindowTokens": 8192}
    (tmp_path / "project.json").write_text(json.dumps(config), encoding="utf-8")
    custom = load_provider_settings(tmp_path)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.extensions["timeout"] == dict.fromkeys(
            ("connect", "read", "write", "pool"), 0.25
        )
        return success(request)

    async with create_qwen_provider(
        custom,
        transport=httpx.MockTransport(handler),
        rerank_transport=httpx.MockTransport(handler),
    ) as provider:
        assert provider.chat_capability.contextWindowTokens == 8192
        await provider.chat("hi")
        await provider.embed([f"{i}:中文" for i in range(7)])
        await provider.rerank("hi", ["hi"])
    assert len(requests) == 5
    chat = json.loads(requests[0].content)
    assert chat["model"] == "custom-chat" and chat["temperature"] == 0.7
    assert [len(json.loads(r.content)["input"]) for r in requests[1:4]] == [3, 3, 1]
    failed_requests: list[httpx.Request] = []

    def fail(request: httpx.Request) -> httpx.Response:
        failed_requests.append(request)
        return httpx.Response(500)

    async with create_qwen_provider(
        custom, transport=httpx.MockTransport(fail), rerank_transport=httpx.MockTransport(fail)
    ) as provider:
        for capability in ("chat", "embedding", "rerank"):
            assert not (await provider.readiness(capability)).ready
    assert len(failed_requests) == 3


@pytest.mark.parametrize("invalid", ["count", "duplicate", "nan"])
async def test_rerank_rejects_incomplete_duplicate_or_nonfinite_results(
    settings: ProviderSettings, invalid: str
) -> None:
    results = [{"index": 0, "relevance_score": 0.9}]
    if invalid != "count":
        results.append(
            {
                "index": 0 if invalid == "duplicate" else 1,
                "relevance_score": float("nan") if invalid == "nan" else 0.5,
            }
        )
    body = json.dumps({"output": {"results": results}})
    async with create_qwen_provider(
        settings, rerank_transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    ) as provider:
        with pytest.raises(ProviderError):
            await provider.rerank("hi", ["one", "two"])


@pytest.mark.parametrize("invalid", ["count", "nan", "later-batch"])
async def test_embedding_never_returns_partial_or_invalid_vectors(
    settings: ProviderSettings, invalid: str
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if invalid == "later-batch" and calls == 1:
            return success(request)
        if invalid == "count" or invalid == "later-batch":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(
            200, content=json.dumps({"data": [{"index": 0, "embedding": [float("nan")] * 1024}]})
        )

    async with create_qwen_provider(settings, transport=httpx.MockTransport(handler)) as provider:
        with pytest.raises(ProviderError):
            await provider.embed(["hi"] * (11 if invalid == "later-batch" else 1))
    assert calls == (2 if invalid == "later-batch" else 1)


async def test_invalid_inputs_fail_without_transport(settings: ProviderSettings) -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("无效输入不应请求远端")

    async with create_qwen_provider(
        settings,
        transport=httpx.MockTransport(forbidden),
        rerank_transport=httpx.MockTransport(forbidden),
    ) as provider:
        with pytest.raises(ProviderError):
            await provider.chat(" ")
        with pytest.raises(ProviderError):
            await provider.chat("hi", max_tokens=0)
        with pytest.raises(ProviderError):
            await provider.embed(["hi", ""])
        for count in (0, -1, 2, True):
            with pytest.raises(ProviderError):
                await provider.rerank("hi", ["hi"], top_n=count)


async def test_readiness_redacts_metadata(settings: ProviderSettings, tmp_path: Path) -> None:
    config = settings.model_dump(mode="json")
    config["llm"]["chat"]["apiKey"] = "chat-secret"
    config["llm"]["chat"]["model"] = "chat-secret"
    config["llm"]["chat"]["baseUrl"] = "https://chat.test/chat-secret"
    config["modelCapabilities"]["chat-secret"] = {"contextWindowTokens": 1000}
    (tmp_path / "project.json").write_text(json.dumps(config), encoding="utf-8")
    custom = load_provider_settings(tmp_path)
    async with create_qwen_provider(custom, transport=httpx.MockTransport(success)) as provider:
        result = await provider.readiness("chat")
    assert result.ready
    assert "chat-secret" not in repr(result)
    assert result.model == "[redacted]" and "[redacted]" in result.baseUrl
