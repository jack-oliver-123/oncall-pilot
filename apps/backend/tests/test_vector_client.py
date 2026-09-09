"""使用真实 SDK schema/index builder 的端口合同，不连接服务。"""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from oncall_pilot.vector_store.client import OfficialMilvusClient
from oncall_pilot.vector_store.config import VectorStoreConfig
from oncall_pilot.vector_store.schema import (
    OUTPUT_FIELDS,
    collection_fields,
    collection_indexes,
    validate_collection,
)


def test_official_sdk_schema_and_operation_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    import pymilvus  # pyright: ignore[reportMissingTypeStubs]

    sdk_type: Any = pymilvus.MilvusClient
    sdk = MagicMock()
    sdk.create_schema.side_effect = sdk_type.create_schema
    sdk.prepare_index_params.side_effect = sdk_type.prepare_index_params
    factory = MagicMock(return_value=sdk)
    monkeypatch.setattr(pymilvus, "MilvusClient", factory)
    config = VectorStoreConfig(
        uri="http://127.0.0.1:19530",
        database="default",
        collection="test",
        token=SecretStr("local-test"),
    )
    client = OfficialMilvusClient(config)
    factory.assert_called_once_with(
        uri=config.uri, token="local-test", db_name="default", timeout=30
    )
    client.create_collection("test", collection_fields())
    schema = sdk.create_collection.call_args.kwargs["schema"]
    schema.verify()
    validate_collection(schema.to_dict())
    assert schema.to_dict()["auto_id"] is False
    for index in collection_indexes():
        client.create_index("test", index)
        params = sdk.create_index.call_args.args[1]
        assert len(list(params)) == 1
        assert list(params)[0].field_name == index["field_name"]
    sdk.search.return_value = [[{"id": "chunk", "distance": 0.9, "entity": {"tenantId": "alice"}}]]
    expression = 'tenantId == "alice" and knowledgeBaseId in ["kb"]'
    hits = client.search("test", [0.1] * 1024, expression, 10)
    assert hits[0]["entity"]["tenantId"] == "alice"
    kwargs = sdk.search.call_args.kwargs
    assert kwargs["filter"] == expression and kwargs["anns_field"] == "vector"
    assert kwargs["search_params"] == {"metric_type": "COSINE", "params": {"ef": 64}}
    assert kwargs["output_fields"] == list(OUTPUT_FIELDS)
    assert kwargs["consistency_level"] == "Strong" and kwargs["timeout"] == 30
    client.insert("test", [{"chunkId": "chunk"}])
    sdk.insert.assert_called_once_with("test", [{"chunkId": "chunk"}], timeout=30)
    sdk.delete.return_value = {"delete_count": 2}
    assert client.delete("test", expression) == 2
    sdk.delete.assert_called_once_with("test", filter=expression, timeout=30)
    sdk.get_server_version.return_value = "test-server"
    assert client.health()
    sdk.get_server_version.assert_called_once_with(timeout=30)
