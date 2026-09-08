"""SQLite 认证 adapter；调用方拥有事务，修改始终带 owner 条件。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.auth.models import AuthSessionRow, UserRow
from oncall_pilot.auth.records import AuthRepositoryPort, AuthSession, DuplicateEmail, User
from oncall_pilot.memory.sqlite import Database


@asynccontextmanager
async def auth_transaction(database: Database) -> AsyncGenerator[AuthRepositoryPort]:
    """组合层 adapter；领域调用方仅获得 Repository Protocol。"""
    async with database.transaction() as session:
        yield AuthRepository(session)


def _user(row: UserRow) -> User:
    return User(row.id, row.email, row.password_hash, row.created_at)


def _session(row: AuthSessionRow) -> AuthSession:
    return AuthSession(
        row.id, row.user_id, row.token_hash, row.created_at, row.last_seen_at, row.revoked_at
    )


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_user(self, user: User) -> None:
        self._session.add(
            UserRow(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                created_at=user.created_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if "UNIQUE constraint failed: users.email" in str(exc.orig):
                raise DuplicateEmail("该邮箱已注册。") from None
            raise

    async def find_user_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.email == email))
        return None if row is None else _user(row)

    async def get_user(self, user_id: str) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return None if row is None else _user(row)

    async def add_session(self, record: AuthSession) -> None:
        self._session.add(
            AuthSessionRow(
                id=record.id,
                user_id=record.user_id,
                token_hash=record.token_hash,
                created_at=record.created_at,
                last_seen_at=record.last_seen_at,
                revoked_at=record.revoked_at,
            )
        )
        await self._session.flush()

    async def resolve_token_hash(self, token_hash: str) -> AuthSession | None:
        """仅用于认证引导；调用方只能提供摘要，不能按客户端 owner 猜测。"""
        row = await self._session.scalar(
            select(AuthSessionRow).where(
                AuthSessionRow.token_hash == token_hash, AuthSessionRow.revoked_at.is_(None)
            )
        )
        return None if row is None else _session(row)

    async def get_session(self, owner_id: str, session_id: str) -> AuthSession | None:
        row = await self._session.scalar(
            select(AuthSessionRow).where(
                AuthSessionRow.id == session_id, AuthSessionRow.user_id == owner_id
            )
        )
        return None if row is None else _session(row)

    async def touch_session(self, owner_id: str, session_id: str, now: datetime) -> bool:
        result = await self._session.scalar(
            update(AuthSessionRow)
            .where(
                AuthSessionRow.id == session_id,
                AuthSessionRow.user_id == owner_id,
                AuthSessionRow.revoked_at.is_(None),
            )
            .values(last_seen_at=now)
            .returning(AuthSessionRow.id)
        )
        return result is not None

    async def revoke_session(self, owner_id: str, session_id: str, now: datetime) -> bool:
        result = await self._session.scalar(
            update(AuthSessionRow)
            .where(
                AuthSessionRow.id == session_id,
                AuthSessionRow.user_id == owner_id,
                AuthSessionRow.revoked_at.is_(None),
            )
            .values(revoked_at=now)
            .returning(AuthSessionRow.id)
        )
        return result is not None
