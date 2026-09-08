"""SQLite 的基础版本读取 adapter。"""

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.memory.contracts import SchemaNotInitialized, SchemaRevision


class SQLiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def schema_revision(self) -> SchemaRevision:
        try:
            result = await self._session.execute(text("SELECT version_num FROM alembic_version"))
        except OperationalError as exc:
            if "no such table: alembic_version" not in str(exc.orig):
                raise
            raise SchemaNotInitialized("请先显式执行 Alembic upgrade head") from None
        revisions = result.scalars().all()
        if len(revisions) != 1 or not isinstance(revisions[0], str) or not revisions[0]:
            raise SchemaNotInitialized("数据库必须有唯一 Alembic revision")
        return SchemaRevision(revision=revisions[0])
