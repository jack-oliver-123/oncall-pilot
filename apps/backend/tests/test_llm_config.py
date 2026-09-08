from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import cast

import pytest

from oncall_pilot.llm.config import load_provider_settings, parse_provider_settings
from oncall_pilot.project_config import (
    JsonObject,
    JsonValue,
    ProjectConfigError,
    load_project_config,
)

TEMPLATE = Path(__file__).resolve().parents[3] / "config/project.template.json"


def template() -> JsonObject:
    return cast(JsonObject, json.loads(TEMPLATE.read_text(encoding="utf-8")))


def test_llm_is_validated_after_deep_merge(tmp_path: Path) -> None:
    (tmp_path / "project.json").write_text(json.dumps(template()), encoding="utf-8")
    (tmp_path / "user.project.json").write_text(
        json.dumps(
            {
                "llm": {
                    "chat": {"apiKey": "secret-chat", "model": "custom-chat", "temperature": 0.5}
                },
                "modelCapabilities": {"custom-chat": {"contextWindowTokens": 32000}},
            }
        ),
        encoding="utf-8",
    )
    settings = load_provider_settings(tmp_path)
    assert settings.llm.chat.model == "custom-chat"
    assert settings.llm.chat.temperature == 0.5
    assert settings.llm.chat.timeout == 120
    assert settings.llm.chat.retries == 2
    assert settings.llm.chat.apiKey.get_secret_value() == "secret-chat"
    assert settings.chat_capability.contextWindowTokens == 32000
    assert "secret-chat" not in repr(settings)
    assert "secret-chat" not in settings.model_dump_json()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("llm",), None),
        (("llm", "chat"), {}),
        (("llm", "chat", "apiKey"), None),
        (("llm", "chat", "baseUrl"), "https://user:secret@host/v1"),
        (("llm", "chat", "baseUrl"), "https://host/v1?apiKey=secret"),
        (("llm", "chat", "baseUrl"), "file:///secret"),
        (("llm", "chat", "baseUrl"), "https://host:invalid/v1"),
        (("llm", "chat", "timeout"), 0),
        (("llm", "chat", "timeout"), float("inf")),
        (("llm", "chat", "retries"), -1),
        (("llm", "chat", "retries"), True),
        (("llm", "chat", "temperature"), "secret"),
        (("llm", "chat", "model"), " "),
        (("llm", "embedding", "dimensions"), 512),
        (("llm", "embedding", "model"), "text-embedding-v3"),
        (("llm", "embedding", "check_embedding_ctx_length"), True),
        (("llm", "embedding", "chunk_size"), 11),
        (("llm", "embedding", "chunk_size"), 0),
        (("llm", "rerank", "model"), "unknown"),
        (("modelCapabilities",), {}),
        (("modelCapabilities", "qwen3.7-max", "contextWindowTokens"), 0),
        (("modelCapabilities", "qwen3.7-max", "contextWindowTokens"), True),
        (("llm", "secret-field"), "secret"),
    ],
)
def test_invalid_llm_config_is_safe(
    tmp_path: Path, path: tuple[str, ...], value: JsonValue
) -> None:
    config = template()
    parent = config
    for key in path[:-1]:
        parent = cast(JsonObject, parent[key])
    parent[path[-1]] = value
    (tmp_path / "project.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ProjectConfigError) as caught:
        load_project_config(tmp_path)
    rendered = "".join(traceback.format_exception(caught.value))
    assert "secret" not in rendered
    assert caught.value.__context__ is None
    assert "LLM" in str(caught.value) or "modelCapabilities" in str(caught.value)


@pytest.mark.parametrize("field", ["llm", "modelCapabilities"])
def test_missing_provider_section_fails(field: str) -> None:
    config = template()
    del config[field]
    with pytest.raises(ProjectConfigError, match=field):
        parse_provider_settings(config)


def test_templates_have_final_sections_and_empty_credentials() -> None:
    config = template()
    assert {
        "app",
        "backend",
        "frontend",
        "database",
        "llm",
        "modelCapabilities",
        "vectorStore",
        "mcp",
        "clsMcpServer",
        "prometheusAlerts",
        "clsLogUpload",
        "aiopsDemo",
    } <= config.keys()
    assert {
        "backendBaseUrl",
        "email",
        "displayName",
        "password",
        "pollIntervalSeconds",
        "indexWaitSeconds",
    } <= cast(JsonObject, config["aiopsDemo"]).keys()

    def check(value: JsonValue) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if any(part in key.lower() for part in ("password", "secret", "key", "token")):
                    if key != "contextWindowTokens":
                        assert item == "", key
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(config)
    check(
        cast(
            JsonValue,
            json.loads(
                TEMPLATE.with_name("user.project.template.json").read_text(encoding="utf-8")
            ),
        )
    )
    assert parse_provider_settings(config).llm.embedding.chunk_size == 10


@pytest.mark.parametrize("kind", ["missing", "json", "encoding", "directory", "root"])
def test_file_errors_do_not_chain_secret_content(tmp_path: Path, kind: str) -> None:
    target = tmp_path / "project.json"
    if kind == "json":
        target.write_text('{"apiKey": "secret-value", INVALID}', encoding="utf-8")
    elif kind == "encoding":
        target.write_bytes(b"secret-value\xff")
    elif kind == "directory":
        target.mkdir()
    elif kind == "root":
        target.write_text('"secret-value"', encoding="utf-8")
    with pytest.raises(ProjectConfigError) as caught:
        load_project_config(tmp_path)
    assert caught.value.__context__ is None
    assert "secret-value" not in "".join(traceback.format_exception(caught.value))
    assert str(tmp_path) not in str(caught.value)
    assert "project.json" in str(caught.value)
