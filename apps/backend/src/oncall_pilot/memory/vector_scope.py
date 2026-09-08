"""未来 Milvus adapter 的纯 scope 合同；此模块不导入或连接 Milvus。"""

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypeVar

from pydantic import JsonValue

from oncall_pilot.memory.scope import InvalidOwnerScope, OwnerScope, require_scope_id

Hit = TypeVar("Hit")


def vector_ownership(*, owner_user_id: str) -> dict[str, str]:
    """同一投影分别写入向量标量和 metadata，保留两种语义字段。"""
    scope = OwnerScope(owner_user_id)
    return {"tenantId": scope.tenant_id, "ownerUserId": scope.owner_user_id}


def vector_metadata(
    metadata: Mapping[str, JsonValue], *, owner_user_id: str
) -> dict[str, JsonValue]:
    """附加 metadata 不得覆盖可信归属投影。"""
    ownership = vector_ownership(owner_user_id=owner_user_id)
    if any(key in metadata and metadata[key] != value for key, value in ownership.items()):
        raise InvalidOwnerScope("向量 metadata 不能覆盖归属。")
    return {**metadata, **ownership}


def search_filter(*, owner_user_id: str, allowed_knowledge_base_ids: Sequence[str]) -> str | None:
    """KB 必须先经 scoped Repository 授权；None 表示禁止召回并返回空结果。"""
    scope = OwnerScope(owner_user_id)
    if isinstance(allowed_knowledge_base_ids, (str, bytes)):
        raise InvalidOwnerScope("知识库范围必须是标识序列。")
    ids = list(dict.fromkeys(require_scope_id(item) for item in allowed_knowledge_base_ids))
    if not ids:
        return None
    return (
        f"tenantId == {json.dumps(scope.tenant_id, ensure_ascii=False)} and "
        f"knowledgeBaseId in {json.dumps(ids, ensure_ascii=False)}"
    )


def document_delete_filter(*, owner_user_id: str, knowledge_base_id: str, document_id: str) -> str:
    scope = OwnerScope(owner_user_id)
    fields = {
        "tenantId": scope.tenant_id,
        "knowledgeBaseId": require_scope_id(knowledge_base_id),
        "documentId": require_scope_id(document_id),
    }
    return " and ".join(
        f"{key} == {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()
    )


async def scoped_recall(
    *,
    owner_user_id: str,
    allowed_knowledge_base_ids: Sequence[str],
    recall: Callable[[str], Awaitable[list[Hit]]],
    post_filter: Callable[[Hit], bool] | None = None,
) -> list[Hit]:
    """recall 内才允许创建客户端；document/metadata 条件只在召回后执行。"""
    expression = search_filter(
        owner_user_id=owner_user_id, allowed_knowledge_base_ids=allowed_knowledge_base_ids
    )
    if expression is None:
        return []
    hits = await recall(expression)
    return hits if post_filter is None else [hit for hit in hits if post_filter(hit)]
