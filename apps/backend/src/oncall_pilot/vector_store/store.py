"""显式配置与生命周期，先验证归属，再执行存储 I/O。"""

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, cast

from pydantic import JsonValue

from oncall_pilot.memory.scope import OwnerScope, require_scope_id
from oncall_pilot.memory.values import serialize_json
from oncall_pilot.memory.vector_scope import (
    document_delete_filter,
    search_filter,
    vector_metadata,
    vector_ownership,
)
from oncall_pilot.vector_store.client import OfficialMilvusClient, VectorClient
from oncall_pilot.vector_store.config import VectorStoreConfig, load_vector_store_config
from oncall_pilot.vector_store.schema import (
    DIMENSIONS,
    collection_fields,
    collection_indexes,
    validate_collection,
    validate_index,
)


def _vector(values: Sequence[float]) -> list[float]:
    if len(values) != DIMENSIONS or any(
        isinstance(value, bool)
        or not isinstance(cast(object, value), (float, int))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("vector 必须为 1024 维有限数值")
    return list(values)


@dataclass(frozen=True, slots=True)
class VectorChunk:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    content: str
    source: str
    created_at: datetime
    metadata: Mapping[str, JsonValue]
    vector: Sequence[float]

    def row(self, *, owner_user_id: str) -> dict[str, Any]:
        ownership = vector_ownership(owner_user_id=owner_user_id)
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("createdAt 必须包含时区")
        row: dict[str, Any] = {
            "chunkId": require_scope_id(self.chunk_id),
            "documentId": require_scope_id(self.document_id),
            "knowledgeBaseId": require_scope_id(self.knowledge_base_id),
            **ownership,
            "content": self.content,
            "source": self.source,
            "createdAt": self.created_at.astimezone(timezone.utc).isoformat(),
            "metadata": vector_metadata(self.metadata, owner_user_id=owner_user_id),
            "vector": _vector(self.vector),
        }
        for field in collection_fields():
            if field["type"] == 21:
                value = row[field["name"]]
                if (
                    not isinstance(value, str)
                    or len(value.encode()) > field["params"]["max_length"]
                ):
                    raise ValueError("向量记录文本类型或 UTF-8 长度无效")
        # 同时复制嵌套 metadata，避免调用方在 I/O 期间修改原始归属数据。
        return json.loads(serialize_json(row))


class MilvusVectorStore:
    def __init__(
        self,
        config_dir: Path,
        *,
        client_factory: Callable[[VectorStoreConfig], VectorClient] = OfficialMilvusClient,
    ) -> None:
        self._config_dir = config_dir
        self._factory = client_factory
        self._client: VectorClient | None = None
        self._config: VectorStoreConfig | None = None
        self._ready = False
        self._lock = RLock()

    def connect(self) -> None:
        with self._lock:
            if self._client is None:
                config = load_vector_store_config(self._config_dir)
                client = self._factory(config)
                self._config, self._client = config, client

    def _connection(self) -> tuple[VectorClient, str]:
        self.connect()
        assert self._client is not None and self._config is not None
        return self._client, self._config.collection

    def initialize(self) -> None:
        with self._lock:
            if self._ready:
                return
            client, collection = self._connection()
            if not client.has_collection(collection):
                client.create_collection(collection, collection_fields())
            validate_collection(client.describe_collection(collection))
            existing = client.list_indexes(collection)
            for index in collection_indexes():
                if index["index_name"] in existing:
                    validate_index(client.describe_index(collection, index["index_name"]), index)
                else:
                    client.create_index(collection, index)
            client.load_collection(collection)
            self._ready = True

    def health(self) -> bool:
        try:
            client, _ = self._connection()
            return client.health()
        except Exception:
            # 显式探针只返回可用性，底层异常可能带有地址或凭据，不向调用方泄露。
            return False

    def insert(self, chunks: Sequence[VectorChunk], *, owner_user_id: str) -> None:
        OwnerScope(owner_user_id)
        rows = [chunk.row(owner_user_id=owner_user_id) for chunk in chunks]
        if not rows:
            return
        self.initialize()
        client, collection = self._connection()
        client.insert(collection, rows)

    def search(
        self,
        vector: Sequence[float],
        *,
        owner_user_id: str,
        allowed_knowledge_base_ids: Sequence[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        expression = search_filter(
            owner_user_id=owner_user_id, allowed_knowledge_base_ids=allowed_knowledge_base_ids
        )
        if expression is None:
            return []
        query = _vector(vector)
        if (
            isinstance(limit, bool)
            or not isinstance(cast(object, limit), int)
            or not 1 <= limit <= 64
        ):
            raise ValueError("limit 必须为 1 到 64 的整数")
        self.initialize()
        client, collection = self._connection()
        return client.search(collection, query, expression, limit)

    def delete_document(
        self, *, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> int:
        expression = document_delete_filter(
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        self.initialize()
        client, collection = self._connection()
        return client.delete(collection, expression)
