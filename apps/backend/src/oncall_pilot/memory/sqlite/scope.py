"""将 owner 条件直接写入 SQL；额外资源与父关系条件通过 where 叠加。"""

from typing import TypeVar

from sqlalchemy import SQLColumnExpression, delete, select, update
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import Delete, Select, Update
from sqlalchemy.sql.elements import ColumnElement

from oncall_pilot.memory.scope import require_scope_id

Row = TypeVar("Row", bound=DeclarativeBase)


def owner_predicate(
    owner_column: SQLColumnExpression[str], *, owner_user_id: str
) -> ColumnElement[bool]:
    """SQLAlchemy 绑定值，不拼接 SQL，不依赖 identity map 中的对象。"""
    return owner_column == require_scope_id(owner_user_id)


def scoped_select(
    model: type[Row], owner_column: SQLColumnExpression[str], *, owner_user_id: str
) -> Select[tuple[Row]]:
    return select(model).where(owner_predicate(owner_column, owner_user_id=owner_user_id))


def scoped_update(
    model: type[Row], owner_column: SQLColumnExpression[str], *, owner_user_id: str
) -> Update:
    return update(model).where(owner_predicate(owner_column, owner_user_id=owner_user_id))


def scoped_delete(
    model: type[Row], owner_column: SQLColumnExpression[str], *, owner_user_id: str
) -> Delete:
    return delete(model).where(owner_predicate(owner_column, owner_user_id=owner_user_id))
