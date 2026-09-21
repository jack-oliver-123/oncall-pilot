"""Agent 组合层的检索 tool factory。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from oncall_pilot.knowledge_retrieval import create_milvus_knowledge_retrieval_tool
from oncall_pilot.memory.scope import CurrentUser, OwnerScope


def knowledge_retrieval_tool_factory(
    *, config_dir: Path, provider_factory: Callable[[], Any] | None = None,
    store: Any | None = None,
) -> Callable[[CurrentUser | OwnerScope], Any]:
    """返回按当前认证用户固定 scope 的 tool 创建器。"""

    def create(current: CurrentUser | OwnerScope) -> Any:
        scope = current.owner_scope if isinstance(current, CurrentUser) else current
        return create_milvus_knowledge_retrieval_tool(
            owner_scope=scope,
            config_dir=config_dir,
            provider_factory=provider_factory,
            store=store,
        )

    return create
