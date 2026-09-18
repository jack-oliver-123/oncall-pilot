"""持久索引领域任务与文档五态。"""

import sqlalchemy as sa
from alembic import op

revision = "0005_document_index_tasks"
down_revision = "0004_knowledge_documents"
branch_labels = None
depends_on = None


def document_table(*, current: bool) -> sa.Table:
    metadata = sa.MetaData()
    columns = [
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
    ]
    table = sa.Table("knowledge_documents", metadata, *columns)
    table.append_constraint(
        sa.ForeignKeyConstraint(
            ["owner_user_id", "knowledge_base_id"],
            ["knowledge_bases.owner_user_id", "knowledge_bases.id"],
            name="fk_knowledge_documents_owner_user_id_knowledge_bases",
        )
    )
    table.append_constraint(
        sa.UniqueConstraint("owner_user_id", "id", name="uq_knowledge_documents_owner_user_id")
    )
    table.append_constraint(
        sa.CheckConstraint(
            "size > 0 AND size <= 10485760", name="ck_knowledge_documents_document_size"
        )
    )
    states = (
        "'pending','running','succeeded','failed','cancelled'"
        if current
        else "'pending','indexed','failed'"
    )
    table.append_constraint(
        sa.CheckConstraint(
            f"index_status IN ({states})", name="ck_knowledge_documents_index_status"
        )
    )
    if current:
        table.append_constraint(
            sa.UniqueConstraint(
                "owner_user_id", "knowledge_base_id", "id", name="uq_document_parent"
            )
        )
    sa.Index("ix_knowledge_documents_scope", table.c.owner_user_id, table.c.knowledge_base_id)
    sa.Index(
        "ix_knowledge_documents_hash",
        table.c.owner_user_id,
        table.c.knowledge_base_id,
        table.c.sha256,
        unique=True,
        sqlite_where=sa.text("vectors_cleaned = 0"),
    )
    return table


def upgrade() -> None:
    # 先放宽 CHECK，转换数据，再收紧；copy_from 同时支持离线 SQL。
    with op.batch_alter_table(
        "knowledge_documents", copy_from=document_table(current=False)
    ) as batch:
        batch.drop_constraint(op.f("ck_knowledge_documents_index_status"), type_="check")
        batch.create_unique_constraint(
            "uq_document_parent", ["owner_user_id", "knowledge_base_id", "id"]
        )
    op.execute(
        "UPDATE knowledge_documents SET index_status='succeeded' WHERE index_status='indexed'"
    )
    snapshot = document_table(current=True)
    for constraint in list(snapshot.constraints):
        if constraint.name == "ck_knowledge_documents_index_status":
            snapshot.constraints.remove(constraint)
    with op.batch_alter_table("knowledge_documents", copy_from=snapshot) as batch:
        batch.create_check_constraint(
            "index_status", "index_status IN ('pending','running','succeeded','failed','cancelled')"
        )
    op.create_table(
        "document_index_tasks",
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
    op.create_index(
        "ix_document_index_tasks_active",
        "document_index_tasks",
        ["owner_user_id", "knowledge_base_id", "document_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending','running')"),
    )
    op.create_index(
        "ix_document_index_tasks_scope",
        "document_index_tasks",
        ["owner_user_id", "knowledge_base_id", "document_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("document_index_tasks")
    with op.batch_alter_table(
        "knowledge_documents", copy_from=document_table(current=True)
    ) as batch:
        batch.drop_constraint(op.f("ck_knowledge_documents_index_status"), type_="check")
        batch.drop_constraint("uq_document_parent", type_="unique")
    op.execute(
        "UPDATE knowledge_documents SET index_status=CASE "
        "WHEN index_status='succeeded' THEN 'indexed' "
        "WHEN index_status IN ('running','cancelled') THEN 'pending' ELSE index_status END"
    )
    snapshot = document_table(current=False)
    for constraint in list(snapshot.constraints):
        if constraint.name == "ck_knowledge_documents_index_status":
            snapshot.constraints.remove(constraint)
    with op.batch_alter_table("knowledge_documents", copy_from=snapshot) as batch:
        batch.create_check_constraint(
            "index_status", "index_status IN ('pending','indexed','failed')"
        )
