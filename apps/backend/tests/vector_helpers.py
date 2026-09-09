"""内存 client 实现：独立解析表达式并实际执行租户隔离，不回显预设结果。"""

import ast
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oncall_pilot.vector_store import MilvusVectorStore, VectorChunk
from oncall_pilot.vector_store.config import VectorStoreConfig


def matches(row: dict[str, Any], expression: str) -> bool:
    tree = ast.parse(expression, mode="eval").body
    assert isinstance(tree, ast.BoolOp) and isinstance(tree.op, ast.And)
    for condition in tree.values:
        assert isinstance(condition, ast.Compare)
        assert isinstance(condition.left, ast.Name) and len(condition.ops) == 1
        name = condition.left.id
        assert name in {"tenantId", "knowledgeBaseId", "documentId"}
        right = ast.literal_eval(condition.comparators[0])
        value = row[name]
        if isinstance(condition.ops[0], ast.Eq):
            if value != right:
                return False
        else:
            assert isinstance(condition.ops[0], ast.In)
            if value not in right:
                return False
    return True


class FakeVectorClient:
    def __init__(self) -> None:
        self.description: dict[str, Any] | None = None
        self.indexes: dict[str, dict[str, Any]] = {}
        self.rows: list[dict[str, Any]] = []
        self.calls: list[str] = []
        self.expressions: list[str] = []
        self.fail_load = False
        self.fail_health = False

    def has_collection(self, collection: str) -> bool:
        self.calls.append("has")
        return self.description is not None

    def describe_collection(self, collection: str) -> dict[str, Any]:
        assert self.description is not None
        return copy.deepcopy(self.description)

    def create_collection(self, collection: str, fields: list[dict[str, Any]]) -> None:
        self.calls.append("create")
        assert self.description is None
        self.description = {
            "auto_id": False,
            "enable_dynamic_field": False,
            "fields": copy.deepcopy(fields),
        }

    def list_indexes(self, collection: str) -> list[str]:
        return list(self.indexes)

    def describe_index(self, collection: str, name: str) -> dict[str, Any]:
        return copy.deepcopy(self.indexes[name])

    def create_index(self, collection: str, index: dict[str, Any]) -> None:
        self.calls.append("index")
        self.indexes[index["index_name"]] = copy.deepcopy(index)

    def load_collection(self, collection: str) -> None:
        self.calls.append("load")
        if self.fail_load:
            raise RuntimeError("load failed")

    def insert(self, collection: str, rows: list[dict[str, Any]]) -> None:
        self.calls.append("insert")
        self.rows.extend(copy.deepcopy(rows))

    def search(
        self, collection: str, vector: list[float], expression: str, limit: int
    ) -> list[dict[str, Any]]:
        self.expressions.append(expression)
        return [
            {"id": row["chunkId"], "distance": 1.0, "entity": row}
            for row in self.rows
            if matches(row, expression)
        ][:limit]

    def delete(self, collection: str, expression: str) -> int:
        self.expressions.append(expression)
        before = len(self.rows)
        self.rows = [row for row in self.rows if not matches(row, expression)]
        return before - len(self.rows)

    def health(self) -> bool:
        self.calls.append("health")
        if self.fail_health:
            raise RuntimeError("token must not escape")
        return True


def chunk(chunk_id: str = "chunk", *, kb: str = "kb", document: str = "doc") -> VectorChunk:
    return VectorChunk(
        chunk_id,
        document,
        kb,
        "中文正文",
        "本地文件",
        datetime(2026, 9, 9, tzinfo=timezone.utc),
        {"tag": "test"},
        [1.0] + [0.0] * 1023,
    )


def setup_store(
    tmp_path: Path, fake: FakeVectorClient | None = None
) -> tuple[MilvusVectorStore, FakeVectorClient, list[VectorStoreConfig]]:
    (tmp_path / "project.json").write_text(
        json.dumps(
            {
                "vectorStore": {
                    "uri": "http://127.0.0.1:19530",
                    "database": "default",
                    "collection": "test_vectors",
                    "token": "",
                }
            }
        ),
        encoding="utf-8",
    )
    client = fake if fake is not None else FakeVectorClient()
    configs: list[VectorStoreConfig] = []

    def factory(config: VectorStoreConfig) -> FakeVectorClient:
        configs.append(config)
        return client

    return MilvusVectorStore(tmp_path, client_factory=factory), client, configs
