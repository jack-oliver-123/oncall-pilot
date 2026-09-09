"""向量存储的固定 schema 与索引契约；不依赖 SDK。"""

from typing import Any

DIMENSIONS = 1024
REQUEST_TIMEOUT = 30.0
SCALAR_FIELDS = ("documentId", "knowledgeBaseId", "ownerUserId", "tenantId", "source", "createdAt")
OUTPUT_FIELDS = ("chunkId", *SCALAR_FIELDS, "content", "metadata")


class IncompatibleCollection(ValueError):
    """现有 collection 必须显式迁移，不能自动删除数据。"""


def collection_fields() -> list[dict[str, Any]]:
    # DataType 的 wire 值：VARCHAR=21、JSON=23、FLOAT_VECTOR=101。
    return [
        {"name": "chunkId", "type": 21, "is_primary": True, "params": {"max_length": 512}},
        *[{"name": name, "type": 21, "params": {"max_length": 2048}} for name in SCALAR_FIELDS],
        {"name": "content", "type": 21, "params": {"max_length": 65535}},
        {"name": "metadata", "type": 23, "params": {}},
        {"name": "vector", "type": 101, "params": {"dim": DIMENSIONS}},
    ]


def collection_indexes() -> list[dict[str, Any]]:
    return [
        {
            "field_name": "vector",
            "index_name": "vector",
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        },
        *[
            {"field_name": name, "index_name": name, "index_type": "INVERTED"}
            for name in SCALAR_FIELDS
        ],
    ]


def validate_collection(description: dict[str, Any]) -> None:
    if description.get("auto_id") or description.get("enable_dynamic_field"):
        raise IncompatibleCollection("collection 必须关闭 auto_id 和 dynamic field")
    fields = {field["name"]: field for field in description["fields"]}
    if fields.keys() != {field["name"] for field in collection_fields()}:
        raise IncompatibleCollection("collection 字段不兼容，需要显式迁移")
    for expected in collection_fields():
        actual = fields[expected["name"]]
        if (
            actual["type"] != expected["type"]
            or bool(actual.get("is_primary")) != bool(expected.get("is_primary"))
            or actual.get("nullable", False)
        ):
            raise IncompatibleCollection("collection 字段类型或主键不兼容")
        for key, value in expected["params"].items():
            if str(actual.get("params", {}).get(key)) != str(value):
                raise IncompatibleCollection("collection 维度或字段长度不兼容")


def validate_index(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in ("field_name", "index_type", "metric_type"):
        if key in expected and actual.get(key) != expected[key]:
            raise IncompatibleCollection("collection 索引不兼容，需要显式迁移")
    for key, value in expected.get("params", {}).items():
        if str(actual.get(key, actual.get("params", {}).get(key))) != str(value):
            raise IncompatibleCollection("collection 索引参数不兼容")
