"""仅验证已加载的 JSON；不从环境变量补充模型配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from oncall_pilot.project_config import ProjectConfigError, load_project_config


class ConfigModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class ModelEndpoint(ConfigModel):
    model: str = Field(min_length=1)
    base_url: str = Field(alias="baseUrl")
    api_key: SecretStr = Field(alias="apiKey")
    timeout: float = Field(gt=0, allow_inf_nan=False)
    retries: int = Field(ge=0, le=10)

    @field_validator("base_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        parts = urlsplit(value)
        # 访问 port 会验证端口格式与范围，避免把非法 URL 留到首次请求。
        _ = parts.port
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or any(c.isspace() for c in value)
        ):
            raise ValueError("必须是无凭据、query、fragment 的 HTTP URL")
        return value

    @field_validator("model")
    @classmethod
    def nonblank_model(cls, value: str) -> str:
        if value.strip() != value or not value:
            raise ValueError("模型名不能为空或含首尾空白")
        return value


class ChatConfig(ModelEndpoint):
    temperature: float = Field(ge=0, le=2, allow_inf_nan=False)


class EmbeddingConfig(ModelEndpoint):
    dimensions: Literal[1024]
    check_embedding_ctx_length: Literal[False]
    chunk_size: int = Field(ge=1, le=10)

    @field_validator("model")
    @classmethod
    def supported_model(cls, value: str) -> str:
        if value != "text-embedding-v4":
            raise ValueError("当前只支持 text-embedding-v4")
        return value


class LlmConfig(ConfigModel):
    provider: Literal["qwen-openai"]
    chat: ChatConfig
    embedding: EmbeddingConfig
    rerank: ModelEndpoint


class ModelCapability(ConfigModel):
    context_window_tokens: int = Field(alias="contextWindowTokens", gt=0)


class ProviderConfig(ConfigModel):
    llm: LlmConfig
    model_capabilities: dict[str, ModelCapability] = Field(alias="modelCapabilities")

    @property
    def context_window_tokens(self) -> int:
        return self.model_capabilities[self.llm.chat.model].context_window_tokens

    def require_credentials(self) -> None:
        for name in ("chat", "embedding", "rerank"):
            endpoint: ModelEndpoint = getattr(self.llm, name)
            if not endpoint.api_key.get_secret_value().strip():
                raise ProjectConfigError(f"llm.{name}.apiKey: 请在 user.project.json 填写凭据")


def validate_llm_config(project: dict[str, object]) -> ProviderConfig:
    error: str | None = None
    config: ProviderConfig | None = None
    try:
        config = ProviderConfig.model_validate(
            {key: project[key] for key in ("llm", "modelCapabilities") if key in project}
        )
    except ValidationError as exc:
        # 只允许已知 schema 字段名，禁止把任意 dict key 或输入值放入诊断。
        allowed = {
            "llm",
            "modelCapabilities",
            "chat",
            "embedding",
            "rerank",
            "provider",
            "model",
            "baseUrl",
            "apiKey",
            "timeout",
            "retries",
            "temperature",
            "dimensions",
            "check_embedding_ctx_length",
            "chunk_size",
            "contextWindowTokens",
        }
        locations = [
            ".".join(str(p) if p in allowed else "[redacted]" for p in e["loc"])
            for e in exc.errors(include_input=False, include_context=False)
        ]
        error = "模型配置缺失或无效: " + ", ".join(locations)
    if error is not None:
        raise ProjectConfigError(error)
    assert config is not None
    if config.llm.chat.model not in config.model_capabilities:
        raise ProjectConfigError("modelCapabilities: 缺少所选 chat 模型的 contextWindowTokens")
    return config


def load_llm_config(config_dir: Path) -> ProviderConfig:
    return validate_llm_config(dict(load_project_config(config_dir)))
