"""官方 SDK 的窄端口；Any 只用于 SDK 的动态 schema/entity 字典。"""

from typing import Any, Protocol

from oncall_pilot.vector_store.config import VectorStoreConfig
from oncall_pilot.vector_store.schema import OUTPUT_FIELDS, REQUEST_TIMEOUT


class VectorClient(Protocol):
    def has_collection(self, collection: str) -> bool: ...
    def describe_collection(self, collection: str) -> dict[str, Any]: ...
    def create_collection(self, collection: str, fields: list[dict[str, Any]]) -> None: ...
    def list_indexes(self, collection: str) -> list[str]: ...
    def describe_index(self, collection: str, name: str) -> dict[str, Any]: ...
    def create_index(self, collection: str, index: dict[str, Any]) -> None: ...
    def load_collection(self, collection: str) -> None: ...
    def insert(self, collection: str, rows: list[dict[str, Any]]) -> None: ...
    def search(
        self, collection: str, vector: list[float], expression: str, limit: int
    ) -> list[dict[str, Any]]: ...
    def delete(self, collection: str, expression: str) -> int: ...
    def health(self) -> bool: ...


class OfficialMilvusClient:
    def __init__(self, config: VectorStoreConfig) -> None:
        # 延迟导入：SDK 的文件读取和网络初始化不属于应用 module import。
        from pymilvus import MilvusClient  # pyright: ignore[reportMissingTypeStubs]

        self._client: Any = MilvusClient(
            uri=config.uri,
            token=config.token.get_secret_value(),
            db_name=config.database,
            timeout=REQUEST_TIMEOUT,
        )

    def has_collection(self, collection: str) -> bool:
        return bool(self._client.has_collection(collection, timeout=REQUEST_TIMEOUT))

    def describe_collection(self, collection: str) -> dict[str, Any]:
        return dict(self._client.describe_collection(collection, timeout=REQUEST_TIMEOUT))

    def create_collection(self, collection: str, fields: list[dict[str, Any]]) -> None:
        from pymilvus import DataType  # pyright: ignore[reportMissingTypeStubs]

        schema: Any = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        for field in fields:
            schema.add_field(
                field_name=field["name"],
                datatype=DataType(field["type"]),
                is_primary=field.get("is_primary", False),
                **field["params"],
            )
        self._client.create_collection(
            collection, schema=schema, timeout=REQUEST_TIMEOUT, consistency_level="Strong"
        )

    def list_indexes(self, collection: str) -> list[str]:
        return list(self._client.list_indexes(collection, timeout=REQUEST_TIMEOUT))

    def describe_index(self, collection: str, name: str) -> dict[str, Any]:
        return dict(self._client.describe_index(collection, name, timeout=REQUEST_TIMEOUT))

    def create_index(self, collection: str, index: dict[str, Any]) -> None:
        params: Any = self._client.prepare_index_params()
        params.add_index(**index)
        self._client.create_index(collection, params, timeout=REQUEST_TIMEOUT)

    def load_collection(self, collection: str) -> None:
        self._client.load_collection(collection, timeout=REQUEST_TIMEOUT)

    def insert(self, collection: str, rows: list[dict[str, Any]]) -> None:
        self._client.insert(collection, rows, timeout=REQUEST_TIMEOUT)

    def search(
        self, collection: str, vector: list[float], expression: str, limit: int
    ) -> list[dict[str, Any]]:
        results: Any = self._client.search(
            collection,
            data=[vector],
            anns_field="vector",
            filter=expression,
            limit=limit,
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            output_fields=list(OUTPUT_FIELDS),
            consistency_level="Strong",
            timeout=REQUEST_TIMEOUT,
        )
        return list(results[0])

    def delete(self, collection: str, expression: str) -> int:
        result: Any = self._client.delete(collection, filter=expression, timeout=REQUEST_TIMEOUT)
        return int(result["delete_count"])

    def health(self) -> bool:
        return bool(self._client.get_server_version(timeout=REQUEST_TIMEOUT))
