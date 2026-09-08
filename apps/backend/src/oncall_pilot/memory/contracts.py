"""不依赖 ORM 或数据库驱动的基础 Repository 契约。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SchemaRevision:
    """显式迁移后数据库的唯一版本。"""

    revision: str


class SchemaNotInitialized(RuntimeError):
    """数据库没有唯一迁移版本，需要调用方显式执行迁移。"""


class Repository(Protocol):
    """基础设施版本读取边界；后续领域按用例定义自己的 Protocol。"""

    async def schema_revision(self) -> SchemaRevision:
        """读取唯一 revision；未迁移时抛出 SchemaNotInitialized。"""
        ...
