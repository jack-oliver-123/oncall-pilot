"""仅测试使用的父子 Repository 示例；不进入生产 metadata 或真实业务 API。"""

from dataclasses import dataclass

from sqlalchemy import ForeignKeyConstraint, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from oncall_pilot.memory.scope import OwnerScope
from oncall_pilot.memory.sqlite.scope import scoped_delete, scoped_select, scoped_update


class ProbeBase(DeclarativeBase):
    pass


class ParentRow(ProbeBase):
    __tablename__ = "test_scope_parents"
    owner_user_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]


class ChildRow(ProbeBase):
    __tablename__ = "test_scope_children"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "parent_id"],
            ["test_scope_parents.owner_user_id", "test_scope_parents.id"],
            ondelete="CASCADE",
        ),
    )
    owner_user_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    parent_id: Mapped[str]
    name: Mapped[str]


@dataclass(frozen=True)
class Resource:
    id: str
    name: str


class ProbeRepository:
    """实际 SQL 合同示例，领域结果不返回 ORM 对象。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_parent(self, resource: Resource, *, owner_user_id: str) -> None:
        scope = OwnerScope(owner_user_id)
        self._session.add(
            ParentRow(
                id=resource.id,
                name=resource.name,
                owner_user_id=scope.owner_user_id,
            )
        )
        await self._session.flush()

    async def get_parent(self, resource_id: str, *, owner_user_id: str) -> Resource | None:
        row = await self._session.scalar(
            scoped_select(ParentRow, ParentRow.owner_user_id, owner_user_id=owner_user_id).where(
                ParentRow.id == resource_id
            )
        )
        return None if row is None else Resource(row.id, row.name)

    async def list_parents(self, *, owner_user_id: str) -> list[Resource]:
        rows = await self._session.scalars(
            scoped_select(ParentRow, ParentRow.owner_user_id, owner_user_id=owner_user_id).order_by(
                ParentRow.id
            )
        )
        return [Resource(row.id, row.name) for row in rows]

    async def update_parent(self, resource_id: str, name: str, *, owner_user_id: str) -> str | None:
        return await self._session.scalar(
            scoped_update(ParentRow, ParentRow.owner_user_id, owner_user_id=owner_user_id)
            .where(ParentRow.id == resource_id)
            .values(name=name)
            .returning(ParentRow.id)
        )

    async def delete_parent(self, resource_id: str, *, owner_user_id: str) -> str | None:
        return await self._session.scalar(
            scoped_delete(ParentRow, ParentRow.owner_user_id, owner_user_id=owner_user_id)
            .where(ParentRow.id == resource_id)
            .returning(ParentRow.id)
        )

    async def create_child(
        self, parent_id: str, resource: Resource, *, owner_user_id: str
    ) -> str | None:
        # INSERT ... SELECT 同时校验父归属，空结果不执行无父写入。
        parent = (
            scoped_select(ParentRow, ParentRow.owner_user_id, owner_user_id=owner_user_id)
            .where(ParentRow.id == parent_id)
            .subquery()
        )
        return await self._session.scalar(
            insert(ChildRow)
            .from_select(
                ["owner_user_id", "parent_id", "id", "name"],
                select(
                    parent.c.owner_user_id,
                    parent.c.id,
                    literal(resource.id),
                    literal(resource.name),
                ),
            )
            .returning(ChildRow.id)
        )

    async def list_children(self, parent_id: str, *, owner_user_id: str) -> list[Resource] | None:
        if await self.get_parent(parent_id, owner_user_id=owner_user_id) is None:
            return None
        rows = await self._session.scalars(
            scoped_select(ChildRow, ChildRow.owner_user_id, owner_user_id=owner_user_id)
            .where(ChildRow.parent_id == parent_id)
            .order_by(ChildRow.id)
        )
        return [Resource(row.id, row.name) for row in rows]

    async def get_child(
        self, parent_id: str, resource_id: str, *, owner_user_id: str
    ) -> Resource | None:
        row = await self._session.scalar(
            scoped_select(ChildRow, ChildRow.owner_user_id, owner_user_id=owner_user_id).where(
                ChildRow.parent_id == parent_id, ChildRow.id == resource_id
            )
        )
        return None if row is None else Resource(row.id, row.name)

    async def update_child(
        self, parent_id: str, resource_id: str, name: str, *, owner_user_id: str
    ) -> str | None:
        return await self._session.scalar(
            scoped_update(ChildRow, ChildRow.owner_user_id, owner_user_id=owner_user_id)
            .where(ChildRow.parent_id == parent_id, ChildRow.id == resource_id)
            .values(name=name)
            .returning(ChildRow.id)
        )

    async def delete_child(
        self, parent_id: str, resource_id: str, *, owner_user_id: str
    ) -> str | None:
        return await self._session.scalar(
            scoped_delete(ChildRow, ChildRow.owner_user_id, owner_user_id=owner_user_id)
            .where(ChildRow.parent_id == parent_id, ChildRow.id == resource_id)
            .returning(ChildRow.id)
        )
