from __future__ import annotations

import asyncio
import traceback
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest
from llm_helpers import write_model_config

from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.llm.contracts import LlmProvider, ModelKind, ProviderError
from oncall_pilot.llm.qwen import QwenOpenAIProvider
from oncall_pilot.llm.smoke import run_smoke


class FakeChat:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.error = error

    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        self.calls.append((prompt, max_tokens))
        if self.error is not None:
            raise self.error
        return "好"


class FakeEmbedding:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.error = error

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.error is not None:
            raise self.error
        return [[0.25] * 1024 for _ in texts]


@pytest.mark.parametrize("kind", ["chat", "embedding", "rerank"])
async def test_readiness_is_minimal_and_reports_metadata(tmp_path: Path, kind: ModelKind) -> None:
    chat, embedding = FakeChat(), FakeEmbedding()
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output": {
                    "results": [
                        {"index": 0, "relevance_score": 0.9},
                    ]
                }
            },
        )

    config = load_llm_config(write_model_config(tmp_path))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider: LlmProvider = QwenOpenAIProvider(
            config,
            chat_client=chat,
            embedding_client=embedding,
            rerank_client=client,
        )
        report = await provider.readiness(kind)
    assert report.ready and report.error is None
    assert report.provider == "qwen-openai"
    assert report.model == getattr(config.llm, kind).model
    assert report.baseUrl == getattr(config.llm, kind).base_url
    assert report.latency >= 0
    assert len(chat.calls) == (1 if kind == "chat" else 0)
    assert len(embedding.calls) == (1 if kind == "embedding" else 0)
    assert len(requests) == (1 if kind == "rerank" else 0)
    if chat.calls:
        assert chat.calls == [("请回复好", 8)]
    if embedding.calls:
        assert embedding.calls == [["好"]]


@pytest.mark.parametrize("kind", ["chat", "embedding", "rerank"])
async def test_all_provider_errors_and_readiness_hide_keys(tmp_path: Path, kind: ModelKind) -> None:
    secret_message = "fake-model-key fake-rerank-key Authorization: Bearer unexpected-key"

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(secret_message, request=request)

    config = load_llm_config(write_model_config(tmp_path))
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        provider = QwenOpenAIProvider(
            config,
            chat_client=FakeChat(RuntimeError(secret_message)),
            embedding_client=FakeEmbedding(RuntimeError(secret_message)),
            rerank_client=client,
        )
        report = await provider.readiness(kind)
        assert not report.ready
        assert report.error is not None and "[redacted]" in report.error
        assert "fake-model-key" not in str(asdict(report))
        assert "fake-rerank-key" not in str(asdict(report))
        with pytest.raises(ProviderError) as caught:
            if kind == "chat":
                await provider.chat("好")
            elif kind == "embedding":
                await provider.embed_documents(["好"])
            else:
                await provider.rerank("好", ["好"])
        formatted = "".join(traceback.format_exception(caught.value))
        assert "fake-model-key" not in formatted
        assert "fake-rerank-key" not in formatted
        assert "unexpected-key" not in formatted
        assert caught.value.__context__ is None


async def test_cancellation_is_not_converted_to_readiness_failure(tmp_path: Path) -> None:
    class CancelledChat(FakeChat):
        async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
            raise asyncio.CancelledError

    async with httpx.AsyncClient() as client:
        provider = QwenOpenAIProvider(
            load_llm_config(write_model_config(tmp_path)),
            chat_client=CancelledChat(),
            embedding_client=FakeEmbedding(),
            rerank_client=client,
        )
        with pytest.raises(asyncio.CancelledError):
            await provider.readiness()


async def test_smoke_without_credentials_reports_failure_without_network(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    write_model_config(tmp_path)
    (tmp_path / "user.project.json").write_text(
        json.dumps({"llm": {"chat": {"apiKey": ""}}}),
        encoding="utf-8",
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("缺少 key 时不能创建 HTTP client")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    assert await run_smoke(tmp_path) == 1
    result = capsys.readouterr().out
    assert '"ready": false' in result
    assert "llm.chat.apiKey" in result
    assert "Traceback" not in result


async def test_rerank_enforces_deadline_on_injected_transport(tmp_path: Path) -> None:
    import json

    attempts = 0

    async def stall(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        await asyncio.Event().wait()
        return httpx.Response(200)

    write_model_config(tmp_path)
    (tmp_path / "user.project.json").write_text(
        json.dumps(
            {
                "llm": {"rerank": {"timeout": 0.01, "retries": 1}},
            }
        ),
        encoding="utf-8",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(stall)) as client:
        provider = QwenOpenAIProvider(
            load_llm_config(tmp_path),
            chat_client=FakeChat(),
            embedding_client=FakeEmbedding(),
            rerank_client=client,
        )
        with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
            await asyncio.wait_for(provider.rerank("好", ["好"]), timeout=2)
    assert attempts == 2
