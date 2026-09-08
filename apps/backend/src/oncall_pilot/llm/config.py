"""只验证显式传入的本地 JSON，不读取环境变量。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from oncall_pilot.project_config import JsonObject, ProjectConfigError, load_project_config


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class EndpointConfig(ConfigModel):
    baseUrl: str
    apiKey: SecretStr
    timeout: float = Field(default=120, gt=0, allow_inf_nan=False)
    retries: int = Field(default=2, ge=0, le=10)

    @field_validator("baseUrl")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(char.isspace() or ord(char) < 32 for char in value)
        ):
            raise ValueError("必须是无凭据、查询参数或片段的 HTTP(S) URL")
        _ = parsed.port
        return value


class ChatConfig(EndpointConfig):
    model: str = Field(default="qwen3.7-max", min_length=1, pattern=r"^\S+$")
    temperature: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)


class EmbeddingConfig(EndpointConfig):
    model: Literal["text-embedding-v4"] = "text-embedding-v4"
    dimensions: Literal[1024] = 1024
    check_embedding_ctx_length: Literal[False] = False
    chunk_size: int = Field(default=10, ge=1, le=10)


class RerankConfig(EndpointConfig):
    model: Literal["qwen3-vl-rerank"] = "qwen3-vl-rerank"


class LlmConfig(ConfigModel):
    provider: Literal["qwen-openai"] = "qwen-openai"
    chat: ChatConfig
    embedding: EmbeddingConfig
    rerank: RerankConfig


class ModelCapability(ConfigModel):
    contextWindowTokens: int = Field(gt=0)


class ProviderSettings(ConfigModel):
    llm: LlmConfig
    modelCapabilities: dict[str, ModelCapability]

    @property
    def chat_capability(self) -> ModelCapability:
        return self.modelCapabilities[self.llm.chat.model]

    def require_credentials(self) -> None:
        for name in ("chat", "embedding", "rerank"):
            endpoint: EndpointConfig = getattr(self.llm, name)
            if not endpoint.apiKey.get_secret_value().strip():
                raise ProjectConfigError(f"llm.{name}.apiKey 为空，请填写本地 user.project.json")


def parse_provider_settings(project: JsonObject) -> ProviderSettings:
    """只选 LLM 相关 section；错误不携带用户输入和原始 ValidationError。"""
    failure: str | None = None
    settings: ProviderSettings | None = None
    try:
        settings = ProviderSettings.model_validate(
            {key: project[key] for key in ("llm", "modelCapabilities") if key in project}
        )
    except ValidationError as exc:
        safe_fields = {
            "llm",
            "modelCapabilities",
            "provider",
            "chat",
            "embedding",
            "rerank",
            "apiKey",
            "baseUrl",
            "model",
            "timeout",
            "retries",
            "temperature",
            "dimensions",
            "check_embedding_ctx_length",
            "chunk_size",
            "contextWindowTokens",
        }
        locations = [
            ".".join(str(part) if part in safe_fields else "<field>" for part in error["loc"])
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        failure = "LLM 配置缺失或无效: " + ", ".join(locations)
    if failure is not None:
        raise ProjectConfigError(failure)
    assert settings is not None
    if settings.llm.chat.model not in settings.modelCapabilities:
        raise ProjectConfigError("modelCapabilities 缺少当前 chat 模型的 contextWindowTokens")
    return settings


def load_provider_settings(config_dir: Path) -> ProviderSettings:
    return parse_provider_settings(load_project_config(config_dir))
