"""所有模型测试仅使用临时配置和 HTTP fake。"""

from __future__ import annotations

import json
from pathlib import Path

from oncall_pilot.project_config import JsonObject


def model_project() -> JsonObject:
    endpoint: JsonObject = {
        "baseUrl": "https://models.example/compatible-mode/v1",
        "apiKey": "fake-model-key",
        "timeout": 120,
        "retries": 2,
    }
    return {
        "llm": {
            "provider": "qwen-openai",
            "chat": {**endpoint, "model": "qwen3.7-max", "temperature": 0.2},
            "embedding": {
                **endpoint,
                "model": "text-embedding-v4",
                "dimensions": 1024,
                "check_embedding_ctx_length": False,
                "chunk_size": 10,
            },
            "rerank": {
                **endpoint,
                "model": "qwen3-vl-rerank",
                "baseUrl": "https://rerank.example/api/v1/services/rerank/text-rerank/text-rerank",
                "apiKey": "fake-rerank-key",
            },
        },
        "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 1000000}},
    }


def write_model_config(path: Path, project: JsonObject | None = None) -> Path:
    (path / "project.json").write_text(
        json.dumps(model_project() if project is None else project), encoding="utf-8"
    )
    return path
