import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from vector_helpers import chunk, setup_store

from oncall_pilot.memory.scope import InvalidOwnerScope
from oncall_pilot.memory.vector_scope import scoped_recall
from oncall_pilot.project_config import ProjectConfigError
from oncall_pilot.vector_store import MilvusVectorStore
from oncall_pilot.vector_store.schema import IncompatibleCollection


def test_construction_and_empty_search_are_lazy(tmp_path: Path) -> None:
    store = MilvusVectorStore(tmp_path / "missing")
    assert store.search([], owner_user_id="alice", allowed_knowledge_base_ids=[]) == []
    assert not hasattr(store, "close")


def test_connect_uses_only_merged_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, fake, configs = setup_store(tmp_path)
    (tmp_path / "user.project.json").write_text(
        json.dumps({"vectorStore": {"token": "private-token", "collection": "user_collection"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MILVUS_URI", "https://wrong.invalid")
    monkeypatch.setenv("MILVUS_TOKEN", "wrong")
    assert not configs and not fake.calls
    store.connect()
    store.connect()
    assert len(configs) == 1 and fake.calls == []
    config = configs[0]
    assert config.uri == "http://127.0.0.1:19530" and config.database == "default"
    assert config.collection == "user_collection"
    assert config.token.get_secret_value() == "private-token"
    assert "private-token" not in repr(config)


def test_initialize_schema_indexes_idempotency_and_concurrency(tmp_path: Path) -> None:
    store, fake, configs = setup_store(tmp_path)

    def initialize(_: int) -> None:
        store.initialize()

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(initialize, range(8)))
    assert len(configs) == 1 and fake.calls.count("create") == 1
    assert fake.calls.count("load") == 1
    assert fake.description is not None
    fields = {f["name"]: f for f in fake.description["fields"]}
    assert set(fields) == {
        "chunkId",
        "documentId",
        "knowledgeBaseId",
        "ownerUserId",
        "tenantId",
        "content",
        "source",
        "createdAt",
        "metadata",
        "vector",
    }
    assert fields["chunkId"]["is_primary"] and fields["chunkId"]["type"] == 21
    assert fields["vector"]["type"] == 101 and fields["vector"]["params"]["dim"] == 1024
    assert fields["metadata"]["type"] == 23
    assert fake.indexes["vector"] == {
        "field_name": "vector",
        "index_name": "vector",
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 200},
    }
    for name in ("documentId", "knowledgeBaseId", "ownerUserId", "tenantId", "source", "createdAt"):
        assert fake.indexes[name]["index_type"] == "INVERTED"
    other, _, _ = setup_store(tmp_path, fake)
    other.initialize()
    assert fake.calls.count("create") == 1 and fake.calls.count("index") == 7


def test_initialize_retries_after_failure(tmp_path: Path) -> None:
    store, fake, _ = setup_store(tmp_path)
    fake.fail_load = True
    with pytest.raises(RuntimeError):
        store.initialize()
    fake.fail_load = False
    store.initialize()
    assert fake.calls.count("create") == 1 and fake.calls.count("load") == 2


@pytest.mark.parametrize("drift", ["dimension", "primary", "dynamic", "index", "metric", "ef"])
def test_existing_incompatible_collection_is_not_overwritten(tmp_path: Path, drift: str) -> None:
    store, fake, _ = setup_store(tmp_path)
    store.initialize()
    assert fake.description is not None
    if drift == "dimension":
        fake.description["fields"][-1]["params"]["dim"] = 8
    elif drift == "primary":
        fake.description["fields"][0]["is_primary"] = False
    elif drift == "dynamic":
        fake.description["enable_dynamic_field"] = True
    elif drift == "index":
        fake.indexes["vector"]["index_type"] = "FLAT"
    elif drift == "metric":
        fake.indexes["vector"]["metric_type"] = "L2"
    else:
        fake.indexes["vector"]["params"]["efConstruction"] = 100
    other, _, _ = setup_store(tmp_path, fake)
    with pytest.raises(IncompatibleCollection):
        other.initialize()
    assert fake.calls.count("create") == 1 and fake.calls.count("load") == 1


def test_missing_index_is_repaired(tmp_path: Path) -> None:
    store, fake, _ = setup_store(tmp_path)
    store.initialize()
    del fake.indexes["tenantId"]
    other, _, _ = setup_store(tmp_path, fake)
    other.initialize()
    assert fake.calls.count("create") == 1 and "tenantId" in fake.indexes


@pytest.mark.parametrize("bad", ["", " ", " alice", "alice\n"])
def test_invalid_owner_fails_before_io_even_empty_kbs(tmp_path: Path, bad: str) -> None:
    store = MilvusVectorStore(tmp_path / "missing")
    with pytest.raises(InvalidOwnerScope):
        store.search([], owner_user_id=bad, allowed_knowledge_base_ids=[])
    with pytest.raises(InvalidOwnerScope):
        store.insert([], owner_user_id=bad)
    with pytest.raises(InvalidOwnerScope):
        store.delete_document(owner_user_id=bad, knowledge_base_id="kb", document_id="doc")


@pytest.mark.parametrize("kb,document", [("", "doc"), ("kb", ""), (" ", "doc"), ("kb", "\n")])
def test_delete_scope_rejected_before_io(tmp_path: Path, kb: str, document: str) -> None:
    store = MilvusVectorStore(tmp_path / "missing")
    with pytest.raises(InvalidOwnerScope):
        store.delete_document(owner_user_id="alice", knowledge_base_id=kb, document_id=document)


def test_insert_and_cross_user_search_delete_with_escaping(tmp_path: Path) -> None:
    store, fake, _ = setup_store(tmp_path)
    alice = 'alice" or tenantId != "x\\中文'
    kb = 'kb\\" and documentId == "injected'
    doc = 'doc"\\中'
    store.insert(
        [
            chunk("a", kb=kb, document=doc),
            chunk("a2", kb="other", document=doc),
            chunk("a3", kb=kb, document="other"),
        ],
        owner_user_id=alice,
    )
    store.insert([chunk("b", kb=kb, document=doc)], owner_user_id="bob")
    hits = store.search(chunk().vector, owner_user_id=alice, allowed_knowledge_base_ids=[kb, kb])
    assert {hit["id"] for hit in hits} == {"a", "a3"}
    for hit in hits:
        row = hit["entity"]
        assert row["tenantId"] == row["ownerUserId"] == alice
        assert row["metadata"]["tenantId"] == row["metadata"]["ownerUserId"] == alice
    assert "ownerUserId" not in fake.expressions[-1] and "metadata" not in fake.expressions[-1]
    assert store.delete_document(owner_user_id=alice, knowledge_base_id=kb, document_id=doc) == 1
    assert {row["chunkId"] for row in fake.rows} == {"a2", "a3", "b"}
    assert (
        store.search(chunk().vector, owner_user_id="bob", allowed_knowledge_base_ids=[kb])[0]["id"]
        == "b"
    )


async def test_document_metadata_post_filter_remains_at_retrieval_layer(tmp_path: Path) -> None:
    store, fake, _ = setup_store(tmp_path)
    store.insert([chunk("a"), chunk("b", document="other")], owner_user_id="alice")

    async def recall(expression: str):
        return store.search(
            chunk().vector, owner_user_id="alice", allowed_knowledge_base_ids=["kb"]
        )

    hits = await scoped_recall(
        owner_user_id="alice",
        allowed_knowledge_base_ids=["kb"],
        recall=recall,
        post_filter=lambda hit: hit["entity"]["documentId"] == "doc",
    )
    assert [hit["id"] for hit in hits] == ["a"]
    assert fake.expressions[-1] == 'tenantId == "alice" and knowledgeBaseId in ["kb"]'


@pytest.mark.parametrize("bad_vector", [[1.0], [float("nan")] * 1024, [float("inf")] * 1024])
def test_invalid_vectors_fail_before_io(tmp_path: Path, bad_vector: list[float]) -> None:
    store = MilvusVectorStore(tmp_path / "missing")
    with pytest.raises(ValueError):
        store.insert([replace(chunk(), vector=bad_vector)], owner_user_id="alice")
    with pytest.raises(ValueError):
        store.search(bad_vector, owner_user_id="alice", allowed_knowledge_base_ids=["kb"])


def test_invalid_metadata_and_time_fail_before_io(tmp_path: Path) -> None:
    store = MilvusVectorStore(tmp_path / "missing")
    for metadata in ({"tenantId": "bob"}, {"ownerUserId": "bob"}):
        with pytest.raises(InvalidOwnerScope):
            store.insert([replace(chunk(), metadata=metadata)], owner_user_id="alice")
    with pytest.raises(ValueError):
        store.insert([replace(chunk(), created_at=datetime(2026, 9, 9))], owner_user_id="alice")


@pytest.mark.parametrize(
    "metadata",
    [
        {1: "bad"},
        {"nested": {1: "bad"}},
        {"tuple": (1, 2)},
        {"object": object()},
        {"nan": float("nan")},
    ],
)
def test_non_json_metadata_rejects_entire_batch_before_io(tmp_path: Path, metadata: Any) -> None:
    store, fake, configs = setup_store(tmp_path)
    with pytest.raises(ValueError):
        store.insert(
            [chunk("valid"), replace(chunk("bad"), metadata=metadata)], owner_user_id="alice"
        )
    assert not configs and not fake.calls and not fake.rows


def test_owner_parameter_contract_for_sync_adapter(tmp_path: Path) -> None:
    store, fake, configs = setup_store(tmp_path)
    operations: list[tuple[Any, dict[str, Any]]] = [
        (store.insert, {"chunks": []}),
        (store.search, {"vector": [], "allowed_knowledge_base_ids": []}),
        (store.delete_document, {"knowledge_base_id": "kb", "document_id": "doc"}),
    ]
    for operation, arguments in operations:
        parameter = inspect.signature(operation).parameters["owner_user_id"]
        assert parameter.default is inspect.Parameter.empty
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        with pytest.raises(TypeError):
            operation(**arguments)
        invalid_values: list[Any] = [None, "", " ", "\t", " padded", 0, False, [], {}]
        for invalid in invalid_values:
            with pytest.raises(InvalidOwnerScope):
                operation(**arguments, owner_user_id=invalid)
    assert not configs and not fake.calls


def test_health_checks_server_without_creating_collection(tmp_path: Path) -> None:
    store, fake, _ = setup_store(tmp_path)
    assert store.health()
    assert fake.calls == ["health"] and fake.description is None
    fake.fail_health = True
    assert not store.health()
    fake.fail_health = False
    assert store.health()
    assert not MilvusVectorStore(tmp_path / "missing").health()


@pytest.mark.parametrize(
    "field,value",
    [
        ("uri", "file:///tmp/milvus.db"),
        ("uri", "https://secret:token@localhost"),
        ("collection", ""),
        ("database", "bad name"),
    ],
)
def test_bad_config_does_not_create_client(tmp_path: Path, field: str, value: str) -> None:
    store, _, configs = setup_store(tmp_path)
    (tmp_path / "user.project.json").write_text(json.dumps({"vectorStore": {field: value}}))
    with pytest.raises(ProjectConfigError) as exc:
        store.connect()
    assert not configs and "secret" not in str(exc.value)
