"""认证持久化边界的不可变记录；秘密不进入 repr。"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, TypeAlias


@dataclass(frozen=True)
class User:
    id: str
    email: str
    password_hash: str = field(repr=False)
    created_at: datetime


@dataclass(frozen=True)
class AuthSession:
    id: str
    user_id: str
    token_hash: str = field(repr=False)
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None


class DuplicateEmail(Exception):
    """规范化邮箱已存在，不包含 SQL 或凭据。"""


class AuthRepositoryPort(Protocol):
    async def add_user(self, user: User) -> None: ...
    async def find_user_by_email(self, email: str) -> User | None: ...
    async def get_user(self, user_id: str) -> User | None: ...
    async def add_session(self, record: AuthSession) -> None: ...
    async def resolve_token_hash(self, token_hash: str) -> AuthSession | None: ...
    async def get_session(self, owner_id: str, session_id: str) -> AuthSession | None: ...
    async def touch_session(self, owner_id: str, session_id: str, now: datetime) -> bool: ...
    async def revoke_session(self, owner_id: str, session_id: str, now: datetime) -> bool: ...


AuthTransactions: TypeAlias = Callable[[], AbstractAsyncContextManager[AuthRepositoryPort]]
