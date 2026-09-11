"""增加 owner-scoped 默认知识库和文档记录。"""

import sqlalchemy as sa
from alembic import op

revision = "0004_knowledge_documents"
down_revision = "0003_background_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_knowledge_bases_owner_user_id"),
    )
    op.create_table(
        "knowledge_documents",
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
    op.create_index(
        "ix_knowledge_documents_scope",
        "knowledge_documents",
        ["owner_user_id", "knowledge_base_id"],
    )
    op.create_index(
        "ix_knowledge_documents_hash",
        "knowledge_documents",
        ["owner_user_id", "knowledge_base_id", "sha256"],
        unique=True,
        sqlite_where=sa.text("vectors_cleaned = 0"),
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_hash", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_scope", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_bases")
