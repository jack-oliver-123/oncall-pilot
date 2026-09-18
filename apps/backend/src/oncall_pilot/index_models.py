"""文档索引领域表；生命周期由持久 job 驱动。"""

import sqlalchemy as sa

from oncall_pilot.memory.sqlite.base import Base

index_tasks = sa.Table(
    "document_index_tasks",
    Base.metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("owner_user_id", sa.String(36), nullable=False),
    sa.Column("knowledge_base_id", sa.String(36), nullable=False),
    sa.Column("document_id", sa.String(36), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("failure_reason", sa.Text()),
    sa.Column("retry_of_task_id", sa.String(36)),
    sa.Column("created_at", sa.String(40), nullable=False),
    sa.Column("updated_at", sa.String(40), nullable=False),
    sa.Column("started_at", sa.String(40)),
    sa.Column("completed_at", sa.String(40)),
    sa.Column("cancel_requested_at", sa.String(40)),
    sa.UniqueConstraint("owner_user_id", "knowledge_base_id", "document_id", "id"),
    sa.ForeignKeyConstraint(
        ["owner_user_id", "knowledge_base_id", "document_id"],
        [
            "knowledge_documents.owner_user_id",
            "knowledge_documents.knowledge_base_id",
            "knowledge_documents.id",
        ],
    ),
    sa.ForeignKeyConstraint(
        ["owner_user_id", "knowledge_base_id", "document_id", "retry_of_task_id"],
        [
            "document_index_tasks.owner_user_id",
            "document_index_tasks.knowledge_base_id",
            "document_index_tasks.document_id",
            "document_index_tasks.id",
        ],
    ),
    sa.CheckConstraint(
        "status IN ('pending','running','succeeded','failed','cancelled')", name="status"
    ),
)
sa.Index(
    "ix_document_index_tasks_active",
    index_tasks.c.owner_user_id,
    index_tasks.c.knowledge_base_id,
    index_tasks.c.document_id,
    unique=True,
    sqlite_where=sa.text("status IN ('pending','running')"),
)
sa.Index(
    "ix_document_index_tasks_scope",
    index_tasks.c.owner_user_id,
    index_tasks.c.knowledge_base_id,
    index_tasks.c.document_id,
    index_tasks.c.created_at,
)
