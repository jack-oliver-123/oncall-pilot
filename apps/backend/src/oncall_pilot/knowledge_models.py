"""知识库文档 metadata；实际建表由 Alembic migration 完成。"""

import sqlalchemy as sa

from oncall_pilot.memory.sqlite.base import Base

knowledge_bases = sa.Table(
    "knowledge_bases",
    Base.metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("owner_user_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.String(40), nullable=False),
    sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
    sa.UniqueConstraint("owner_user_id", "id", name="uq_knowledge_bases_owner_user_id"),
)

documents = sa.Table(
    "knowledge_documents",
    Base.metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("owner_user_id", sa.String(36), nullable=False),
    sa.Column("knowledge_base_id", sa.String(36), nullable=False),
    sa.Column("filename", sa.String(255), nullable=False),
    sa.Column("size", sa.Integer(), nullable=False),
    sa.Column("mime_type", sa.String(100), nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("uploaded_at", sa.String(40), nullable=False),
    sa.Column("index_status", sa.String(20), nullable=False),
    sa.Column("chunking_config", sa.JSON(), nullable=False),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("deleted_at", sa.String(40)),
    sa.Column("vectors_cleaned", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.ForeignKeyConstraint(
        ["owner_user_id", "knowledge_base_id"],
        ["knowledge_bases.owner_user_id", "knowledge_bases.id"],
    ),
    sa.UniqueConstraint("owner_user_id", "id", name="uq_knowledge_documents_owner_user_id"),
    sa.CheckConstraint("size > 0 AND size <= 10485760", name="document_size"),
    sa.CheckConstraint("index_status IN ('pending','indexed','failed')", name="index_status"),
)
sa.Index("ix_knowledge_documents_scope", documents.c.owner_user_id, documents.c.knowledge_base_id)
sa.Index(
    "ix_knowledge_documents_hash",
    documents.c.owner_user_id,
    documents.c.knowledge_base_id,
    documents.c.sha256,
    unique=True,
    sqlite_where=sa.text("vectors_cleaned = 0"),
)
