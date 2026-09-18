"""旧文档数据的升级、降级与约束验证。"""
from pathlib import Path

from migration_helpers import migrate, write_database_config
from sqlalchemy import text

from oncall_pilot.memory.sqlite import open_database


async def test_existing_indexed_document_roundtrip(tmp_path: Path) -> None:
    config = write_database_config(tmp_path)
    migrate(config, "upgrade", "0004_knowledge_documents")
    async with open_database(config) as database:
        async with database.transaction() as session:
            await session.execute(text(
                "INSERT INTO users(id,email,password_hash,created_at) "
                "VALUES ('owner','owner@example.com','hash','2026-09-15')"
            ))
            await session.execute(text(
                "INSERT INTO knowledge_bases(id,owner_user_id,created_at) "
                "VALUES ('kb','owner','2026-09-15')"
            ))
            await session.execute(text("""
                INSERT INTO knowledge_documents
                (id,owner_user_id,knowledge_base_id,filename,size,mime_type,sha256,
                 uploaded_at,index_status,chunking_config,body,vectors_cleaned)
                VALUES ('doc','owner','kb','a.md',1,'text/plain','hash','2026-09-15',
                 'indexed','{"strategy":"paragraph"}','original',0)
            """))
    for revision, expected in [("head", "succeeded"), ("0004_knowledge_documents", "indexed"),
                               ("head", "succeeded")]:
        migrate(config, "downgrade" if revision != "head" else "upgrade", revision)
        async with open_database(config) as database:
            async with database.transaction() as session:
                row = (await session.execute(text(
                    "SELECT index_status,body FROM knowledge_documents "
                    "WHERE owner_user_id='owner' AND knowledge_base_id='kb' AND id='doc'"
                ))).one()
                assert tuple(row) == (expected, "original")
                assert (await session.execute(text("PRAGMA foreign_key_check"))).all() == []
