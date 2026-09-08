"""百炼 text-rerank HTTP adapter；不自行创建 client。"""

from __future__ import annotations

import asyncio
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field

from oncall_pilot.llm.config import RerankConfig
from oncall_pilot.llm.provider import RerankResult


class _Result(BaseModel):
    model_config = ConfigDict(strict=True)
    index: int
    relevance_score: Annotated[float, Field(allow_inf_nan=False)]


class _Output(BaseModel):
    results: list[_Result]


class _Response(BaseModel):
    output: _Output


class QwenRerankClient:
    def __init__(self, config: RerankConfig, client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = client

    async def rerank(self, query: str, documents: list[str], *, top_n: int) -> list[RerankResult]:
        for attempt in range(self._config.retries + 1):
            try:
                response = await self._client.post(
                    self._config.baseUrl,
                    headers={"Authorization": f"Bearer {self._config.apiKey.get_secret_value()}"},
                    json={
                        "model": self._config.model,
                        "input": {"query": query, "documents": documents},
                        "parameters": {"top_n": top_n, "return_documents": False},
                    },
                    timeout=self._config.timeout,
                )
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == self._config.retries:
                    raise
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if attempt == self._config.retries or not (
                    status in (408, 429) or 500 <= status < 600
                ):
                    raise
            else:
                payload = _Response.model_validate_json(response.content)
                return [
                    RerankResult(index=item.index, relevanceScore=item.relevance_score)
                    for item in payload.output.results
                ]
            await asyncio.sleep(min(0.25 * 2**attempt, 2))
        raise RuntimeError("排序重试结束")
