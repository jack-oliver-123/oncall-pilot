"""增加持久后台任务与有序事件，复合外键保护 owner 和父关系。"""

import sqlalchemy as sa
from alembic import op

revision = "0003_background_jobs"
down_revision = "0002_user_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("available_at", sa.String(40), nullable=False),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_expires_at", sa.String(40)),
        sa.Column("cancel_requested_at", sa.String(40)),
        sa.Column("retry_of_job_id", sa.String(36)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("started_at", sa.String(40)),
        sa.Column("completed_at", sa.String(40)),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.UniqueConstraint("owner_user_id", "id"),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "retry_of_job_id"],
            ["background_jobs.owner_user_id", "background_jobs.id"],
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="status"
        ),
        sa.CheckConstraint(
            "attempt >= 0 AND max_attempts BETWEEN 1 AND 100 AND attempt <= max_attempts",
            name="attempts",
        ),
        sa.CheckConstraint("timeout_seconds > 0", name="timeout"),
        sa.CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status != 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="lease",
        ),
    )
    op.create_table(
        "background_job_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"], ["background_jobs.owner_user_id", "background_jobs.id"]
        ),
        sa.UniqueConstraint("job_id", "sequence"),
        sa.CheckConstraint("sequence > 0", name="sequence"),
    )
    op.create_index(
        "ix_background_jobs_queue", "background_jobs", ["owner_user_id", "status", "available_at"]
    )
    op.create_index("ix_background_jobs_lease", "background_jobs", ["status", "lease_expires_at"])


def downgrade() -> None:
    op.drop_table("background_job_events")
    op.drop_index("ix_background_jobs_lease", table_name="background_jobs")
    op.drop_index("ix_background_jobs_queue", table_name="background_jobs")
    op.drop_table("background_jobs")
