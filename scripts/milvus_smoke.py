"""仅在 loopback 服务可用时执行，临时配置与独立 collection 的真实 smoke。"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4


def main() -> int:
    try:
        with socket.create_connection(("127.0.0.1", 19530), timeout=2):
            pass
    except OSError:
        print("SKIP: 本机 127.0.0.1:19530 不可用，真实 Milvus smoke 未运行。")
        return 0

    from pymilvus import MilvusClient

    from oncall_pilot.vector_store import MilvusVectorStore, VectorChunk

    collection = "p07_smoke_" + uuid4().hex
    uri = "http://127.0.0.1:19530"
    admin = MilvusClient(uri=uri, token="", db_name="default", timeout=10)
    assert not admin.has_collection(collection, timeout=10)
    try:
        with TemporaryDirectory(prefix="p07-milvus-") as directory:
            config_dir = Path(directory)
            (config_dir / "project.json").write_text(
                json.dumps(
                    {
                        "vectorStore": {
                            "uri": uri,
                            "database": "default",
                            "collection": collection,
                            "token": "",
                        }
                    }
                ),
                encoding="utf-8",
            )
            store = MilvusVectorStore(config_dir)
            assert store.health(), "真实服务 health 失败"
            store.initialize()
            store.initialize()
            MilvusVectorStore(config_dir).initialize()
            vector = [1.0] + [0.0] * 1023
            for owner in ('alice"\\中', "bob"):
                record = VectorChunk(
                    uuid4().hex,
                    'doc"\\中',
                    'kb"\\中',
                    "测试正文",
                    "smoke",
                    datetime.now(timezone.utc),
                    {"smoke": True},
                    vector,
                )
                store.insert([record], owner_user_id=owner)
            for owner in ('alice"\\中', "bob"):
                hits = store.search(
                    vector, owner_user_id=owner, allowed_knowledge_base_ids=['kb"\\中']
                )
                assert len(hits) == 1 and hits[0]["entity"]["tenantId"] == owner
            assert (
                store.delete_document(
                    owner_user_id='alice"\\中', knowledge_base_id='kb"\\中', document_id='doc"\\中'
                )
                == 1
            )
            assert (
                store.search(
                    vector, owner_user_id='alice"\\中', allowed_knowledge_base_ids=['kb"\\中']
                )
                == []
            )
            assert (
                len(
                    store.search(
                        vector, owner_user_id="bob", allowed_knowledge_base_ids=['kb"\\中']
                    )
                )
                == 1
            )
            assert store.search([], owner_user_id="bob", allowed_knowledge_base_ids=[]) == []
        print("PASS: 真实 Milvus health/schema/index/幂等初始化/双用户 search/delete。")
    finally:
        if admin.has_collection(collection, timeout=10):
            admin.drop_collection(collection, timeout=30)
        admin.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
