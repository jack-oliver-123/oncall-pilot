"""只在显式连接时加载本地向量配置。"""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator

from oncall_pilot.project_config import ProjectConfigError, load_project_config


class VectorStoreConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    uri: str
    database: str
    collection: str
    token: SecretStr

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        parts = urlsplit(value)
        _ = parts.port
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or parts.path not in {"", "/"}
            or any(c.isspace() for c in value)
        ):
            raise ValueError("必须使用无凭据和路径的 Milvus HTTP URL")
        return value

    @field_validator("database", "collection")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if (
            not value
            or len(value) > 255
            or not value.isascii()
            or not (value[0].isalpha() or value[0] == "_")
            or not value.replace("_", "a").isalnum()
        ):
            raise ValueError("必须使用有效的 Milvus 标识")
        return value


def load_vector_store_config(config_dir: Path) -> VectorStoreConfig:
    raw = load_project_config(config_dir).get("vectorStore")
    try:
        return VectorStoreConfig.model_validate(raw)
    except ValidationError:
        pass
    raise ProjectConfigError("vectorStore 配置缺失或无效，请检查 uri/database/collection/token")
