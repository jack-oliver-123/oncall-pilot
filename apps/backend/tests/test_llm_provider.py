from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import cast

import httpx
import pytest
from llm_helpers import write_model_config

from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.llm.contracts import ProviderError
from oncall_pilot.llm.qwen import open_qwen_provider
from oncall_pilot.project_config import JsonObject, ProjectConfigError


def payload(request: httpx.Request) -> JsonObject:
    return cast(JsonObject, json.loads(request.content))


def chat_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chat-fake",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen3.7-max",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "收到"},
                    "finish_reason": "stop",
                }
            ],
        },
    )


async def test_chat_uses_json_parameters_and_injected_transport(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return chat_response()

    config = load_llm_config(write_model_config(tmp_path))
    async with open_qwen_provider(config, transport=httpx.MockTransport(respond)) as provider:
        assert requests == []
        assert provider.context_window_tokens == 1000000
        assert await provider.chat("你好") == "收到"
    assert len(requests) == 1
    assert str(requests[0].url) == "https://models.example/compatible-mode/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer fake-model-key"
    assert payload(requests[0])["model"] == "qwen3.7-max"
    assert payload(requests[0])["temperature"] == 0.2
    assert payload(requests[0])["messages"] == [{"role": "user", "content": "你好"}]
    assert requests[0].extensions["timeout"] == {
        "connect": 120,
        "read": 120,
        "write": 120,
        "pool": 120,
    }


async def test_embedding_batches_raw_strings_and_restores_index_order(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    texts = [f" 原始中文 {i}\n" for i in range(21)] + ["重复", "重复"]

    def respond(request: httpx.Request) -> httpx.Response:
        offset = sum(len(cast(list[str], payload(r)["input"])) for r in requests)
        requests.append(request)
        batch = cast(list[str], payload(request)["input"])
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-v4",
                "data": [
                    {"object": "embedding", "index": i, "embedding": [float(offset + i)] * 1024}
                    for i in reversed(range(len(batch)))
                ],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    config = load_llm_config(write_model_config(tmp_path))
    async with open_qwen_provider(config, transport=httpx.MockTransport(respond)) as provider:
        assert await provider.embed_documents([]) == []
        vectors = await provider.embed_documents(texts)
    assert [len(cast(list[str], payload(r)["input"])) for r in requests] == [10, 10, 3]
    assert [t for r in requests for t in cast(list[str], payload(r)["input"])] == texts
    assert [v[0] for v in vectors] == list(range(23))
    assert all(len(v) == 1024 for v in vectors)
    for request in requests:
        assert payload(request)["model"] == "text-embedding-v4"
        assert payload(request)["dimensions"] == 1024
        assert payload(request)["encoding_format"] == "float"


async def test_rerank_payload_and_real_scores(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output": {
                    "results": [
                        {"index": 1, "relevance_score": 0.91},
                        {"index": 0, "relevance_score": 0.12},
                    ]
                }
            },
        )

    config = load_llm_config(write_model_config(tmp_path))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as rerank:
        async with open_qwen_provider(config, rerank_client=rerank) as provider:
            assert await provider.rerank("告警", []) == []
            results = await provider.rerank("告警", ["文档甲", "文档乙"])
        assert not rerank.is_closed
    assert [(r.index, r.relevance_score) for r in results] == [(1, 0.91), (0, 0.12)]
    assert payload(requests[0]) == {
        "model": "qwen3-vl-rerank",
        "input": {"query": "告警", "documents": ["文档甲", "文档乙"]},
        "parameters": {"top_n": 2, "return_documents": False},
    }
    assert str(requests[0].url) == config.llm.rerank.base_url
    assert requests[0].headers["authorization"] == "Bearer fake-rerank-key"
    assert requests[0].extensions["timeout"]["read"] == 120


@pytest.mark.parametrize("status,expected", [(401, 1), (429, 3), (503, 3), (408, 3)])
async def test_rerank_retries_are_bounded(tmp_path: Path, status: int, expected: int) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"message": "fake-rerank-key"})

    config = load_llm_config(write_model_config(tmp_path))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as rerank:
        async with open_qwen_provider(config, rerank_client=rerank) as provider:
            with pytest.raises(ProviderError, match="redacted"):
                await provider.rerank("告警", ["文档"])
    assert len(requests) == expected


@pytest.mark.parametrize("kind", ["chat", "embedding"])
@pytest.mark.parametrize("status,expected", [(401, 1), (503, 3)])
async def test_sdk_retries_and_timeout_are_configured(
    tmp_path: Path,
    kind: str,
    status: int,
    expected: int,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status,
            headers={"retry-after-ms": "1"},
            json={
                "error": {"message": "fake-model-key", "type": "error"},
            },
        )

    config = load_llm_config(write_model_config(tmp_path))
    async with open_qwen_provider(config, transport=httpx.MockTransport(respond)) as provider:
        with pytest.raises(ProviderError) as caught:
            if kind == "chat":
                await provider.chat("好")
            else:
                await provider.embed_documents(["好"])
    assert "fake-model-key" not in "".join(traceback.format_exception(caught.value))
    assert len(requests) == expected
    assert all(r.extensions["timeout"]["read"] == 120 for r in requests)


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"output": {"results": [{"index": 0}]}},
        {"output": {"results": [{"index": 4, "relevance_score": 0.8}]}},
        {"output": {"results": [{"index": 0, "relevance_score": "NaN"}]}},
        {"output": {"results": [{"index": 0, "relevance_score": 0.8}] * 2}},
    ],
)
async def test_invalid_rerank_response_has_no_fallback(tmp_path: Path, result: JsonObject) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=result)

    config = load_llm_config(write_model_config(tmp_path))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as rerank:
        async with open_qwen_provider(config, rerank_client=rerank) as provider:
            with pytest.raises(ProviderError):
                await provider.rerank("好", ["好"], top_n=1)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"index": 0, "embedding": [0.1]}],
        [{"index": 1, "embedding": [0.1] * 1024}],
        [{"index": 0, "embedding": ["bad"] * 1024}],
    ],
)
async def test_invalid_embedding_response_has_no_partial_success(
    tmp_path: Path,
    data: list[JsonObject],
) -> None:
    config = load_llm_config(write_model_config(tmp_path))
    async with open_qwen_provider(
        config, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": data}))
    ) as provider:
        with pytest.raises(ProviderError):
            await provider.embed_documents(["好"])


async def test_factory_blocks_environment_routing_credentials_and_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "OPENAI_ORGANIZATION",
        "OPENAI_PROJECT_ID",
        "OPENAI_PROXY",
        "HTTPS_PROXY",
        "OPENAI_API_TYPE",
        "OPENAI_API_VERSION",
        "LC_OUTPUT_VERSION",
    ):
        monkeypatch.setenv(name, "environment-sentinel")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "X-Secret: environment-sentinel")
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("embeddings"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.2] * 1024}]})
        return chat_response()

    config = load_llm_config(write_model_config(tmp_path))
    async with open_qwen_provider(config, transport=httpx.MockTransport(respond)) as provider:
        await provider.chat("好")
        await provider.embed_documents(["好"])
    for request in requests:
        assert "environment-sentinel" not in str(request.url)
        assert "environment-sentinel" not in str(request.headers)
        assert b"environment-sentinel" not in request.content


async def test_factory_releases_owned_transport_even_when_caller_fails(tmp_path: Path) -> None:
    class Transport(httpx.AsyncBaseTransport):
        closed = False

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return chat_response()

        async def aclose(self) -> None:
            self.closed = True

    transport = Transport()
    config = load_llm_config(write_model_config(tmp_path))
    with pytest.raises(ValueError, match="caller"):
        async with open_qwen_provider(config, transport=transport) as provider:
            await provider.chat("好")
            raise ValueError("caller")
    assert transport.closed


async def test_factory_construction_error_is_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import langchain_openai

    def fail(**kwargs: object) -> None:
        raise ValueError("fake-model-key fake-rerank-key")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", fail)
    config = load_llm_config(write_model_config(tmp_path))
    with pytest.raises(ProviderError) as caught:
        async with open_qwen_provider(config):
            pytest.fail("不应进入 factory")
    assert "fake-model-key" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None


@pytest.mark.parametrize("kind", ["chat", "embedding", "rerank"])
async def test_empty_key_cannot_fall_back_to_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    write_model_config(tmp_path)
    (tmp_path / "user.project.json").write_text(
        json.dumps({"llm": {kind: {"apiKey": ""}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "environment-sentinel")
    config = load_llm_config(tmp_path)
    with pytest.raises(ProjectConfigError, match=f"llm.{kind}.apiKey"):
        async with open_qwen_provider(config):
            pytest.fail("空凭据应在创建 client 前失败")


@pytest.mark.parametrize("kind", ["chat", "embedding", "rerank"])
async def test_transport_timeout_is_safe_and_retries_configurable(
    tmp_path: Path, kind: str
) -> None:
    requests: list[httpx.Request] = []

    def fail(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("fake-model-key fake-rerank-key", request=request)

    write_model_config(tmp_path)
    (tmp_path / "user.project.json").write_text(
        json.dumps(
            {
                "llm": {kind: {"timeout": 0.02, "retries": 1}},
            }
        ),
        encoding="utf-8",
    )
    config = load_llm_config(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as rerank:
        async with open_qwen_provider(
            config,
            transport=httpx.MockTransport(fail),
            rerank_client=rerank,
        ) as provider:
            with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
                if kind == "chat":
                    await provider.chat("好")
                elif kind == "embedding":
                    await provider.embed_documents(["好"])
                else:
                    await provider.rerank("好", ["好"])
    assert len(requests) == 2
    assert all(r.extensions["timeout"]["read"] == 0.02 for r in requests)


async def test_readiness_accepts_successful_completion_exhausting_tiny_budget(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chat-fake",
                "object": "chat.completion",
                "created": 0,
                "model": "qwen3.7-max",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": ""},
                        "finish_reason": "length",
                    }
                ],
            },
        )

    config = load_llm_config(write_model_config(tmp_path))
    async with open_qwen_provider(config, transport=httpx.MockTransport(respond)) as provider:
        report = await provider.readiness()
    assert payload(requests[0]).get("max_completion_tokens") == 8
    assert report.ready


async def test_factory_cleanup_error_does_not_disclose_transport_secrets(tmp_path: Path) -> None:
    class FailingCloseTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return chat_response()

        async def aclose(self) -> None:
            raise RuntimeError("fake-model-key fake-rerank-key")

    config = load_llm_config(write_model_config(tmp_path))
    with pytest.raises(ProviderError) as caught:
        async with open_qwen_provider(config, transport=FailingCloseTransport()):
            pass
    assert "[redacted]" in str(caught.value)
    assert "fake-model-key" not in "".join(traceback.format_exception(caught.value))
    assert "fake-rerank-key" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None
