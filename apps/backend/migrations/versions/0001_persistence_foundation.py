"""建立持久化基础版本链；业务表由后续 Change 逐一引入。"""

revision: str = "0001_persistence_foundation"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """基础版本不创建领域业务表。"""


def downgrade() -> None:
    """基础版本没有业务 DDL 可撤销。"""
