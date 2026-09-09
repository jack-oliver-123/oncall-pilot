from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import cast

import pytest
from llm_helpers import model_project, write_model_config

from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.project_config import JsonObject, ProjectConfigError, load_project_config


def test_llm_config_validates_after_deep_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    write_model_config(tmp_path)
    (tmp_path / "user.project.json").write_text(
        json.dumps({"llm": {"chat": {"temperature": 0.7, "apiKey": "user-key"}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    config = load_llm_config(tmp_path)
    assert config.llm.chat.temperature == 0.7
    assert config.llm.chat.timeout == 120
    assert config.llm.chat.api_key.get_secret_value() == "user-key"
    assert config.context_window_tokens == 1000000
    assert "user-key" not in repr(config)


@pytest.mark.parametrize(
    "override",
    [
        {"llm": None},
        {"llm": {"chat": None}},
        {"llm": {"chat": {"timeout": 0}}},
        {"llm": {"chat": {"retries": -1}}},
        {"llm": {"chat": {"temperature": 3}}},
        {"llm": {"embedding": {"dimensions": 1536}}},
        {"llm": {"embedding": {"chunk_size": 11}}},
        {"llm": {"embedding": {"check_embedding_ctx_length": True}}},
        {"llm": {"chat": {"baseUrl": "https://user:secret@host/v1"}}},
        {"llm": {"chat": {"baseUrl": "https://host/v1?apiKey=secret"}}},
        {"llm": {"chat": {"baseUrl": "https://host:invalid/v1"}}},
        {"llm": {"chat": {"model": "unknown-model"}}},
        {"modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 0}}},
    ],
)
def test_invalid_llm_overrides_fail_safely(tmp_path: Path, override: JsonObject) -> None:
    write_model_config(tmp_path)
    (tmp_path / "user.project.json").write_text(json.dumps(override), encoding="utf-8")
    with pytest.raises(ProjectConfigError) as caught:
        load_project_config(tmp_path)
    assert "fake-model-key" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None


@pytest.mark.parametrize("missing", ["llm", "modelCapabilities"])
def test_llm_consumer_requires_sections(tmp_path: Path, missing: str) -> None:
    project = model_project()
    del project[missing]
    write_model_config(tmp_path, project)
    with pytest.raises(ProjectConfigError):
        load_llm_config(tmp_path)


def test_missing_model_field_does_not_take_sdk_defaults(tmp_path: Path) -> None:
    write_model_config(tmp_path, {"llm": {"provider": "qwen-openai"}})
    with pytest.raises(ProjectConfigError, match="llm.chat"):
        load_llm_config(tmp_path)


@pytest.mark.parametrize("kind", ["chat", "embedding", "rerank"])
@pytest.mark.parametrize("field", ["model", "baseUrl", "apiKey", "timeout", "retries"])
def test_endpoint_required_fields(tmp_path: Path, kind: str, field: str) -> None:
    project = model_project()
    endpoint = cast(JsonObject, cast(JsonObject, project["llm"])[kind])
    del endpoint[field]
    write_model_config(tmp_path, project)
    with pytest.raises(ProjectConfigError, match=f"llm.{kind}.{field}"):
        load_llm_config(tmp_path)


def test_template_is_valid_without_real_credentials(tmp_path: Path) -> None:
    template = Path(__file__).resolve().parents[3] / "config/project.template.json"
    (tmp_path / "project.json").write_bytes(template.read_bytes())
    config = load_llm_config(tmp_path)
    assert config.context_window_tokens == 1000000
    with pytest.raises(ProjectConfigError, match="apiKey"):
        config.require_credentials()
