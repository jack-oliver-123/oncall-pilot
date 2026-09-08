"""认证工作单元；昂贵密码计算不持有 SQLite 事务。"""

import hashlib
import re
import secrets
from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

from oncall_pilot.auth.passwords import PasswordManager
from oncall_pilot.auth.records import AuthSession, AuthTransactions, DuplicateEmail, User
from oncall_pilot.generated_contracts import AuthUser, LoginData
from oncall_pilot.memory.values import new_id, utc_now
from oncall_pilot.protocol import ApiException


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+", normalized):
        raise ApiException("VALIDATION_REQUEST_INVALID")
    return normalized


def public_user(user: User) -> AuthUser:
    return AuthUser(id=user.id, email=user.email, createdAt=user.created_at.isoformat())


@dataclass(frozen=True)
class Identity:
    user: User
    session: AuthSession


class AuthService:
    def __init__(self, transactions: AuthTransactions, passwords: PasswordManager) -> None:
        self._transactions = transactions
        self._passwords = passwords

    async def register(self, email: str, password: str) -> AuthUser:
        normalized = normalize_email(email)
        encoded = await run_in_threadpool(self._passwords.hash, password)
        user = User(new_id(), normalized, encoded, utc_now())
        try:
            async with self._transactions() as repository:
                await repository.add_user(user)
        except DuplicateEmail:
            raise ApiException("BUSINESS_EMAIL_ALREADY_EXISTS") from None
        return public_user(user)

    async def login(self, email: str, password: str) -> LoginData:
        normalized = normalize_email(email)
        async with self._transactions() as repository:
            user = await repository.find_user_by_email(normalized)
        valid = await run_in_threadpool(
            self._passwords.verify, password, None if user is None else user.password_hash
        )
        if not valid or user is None:
            raise ApiException("AUTH_INVALID_CREDENTIALS")
        token = secrets.token_urlsafe(32)
        now = utc_now()
        record = AuthSession(
            new_id(), user.id, hashlib.sha256(token.encode()).hexdigest(), now, now, None
        )
        async with self._transactions() as repository:
            await repository.add_session(record, owner_user_id=user.id)
        return LoginData(user=public_user(user), token=token, tokenType="Bearer")

    async def authenticate(self, token: str) -> Identity:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise ApiException("AUTH_UNAUTHENTICATED")
        digest = hashlib.sha256(token.encode()).hexdigest()
        # 先以条件 UPDATE 获取写锁，再读取用户，避免并发读升级 SQLite 锁。
        async with self._transactions() as repository:
            record = await repository.resolve_token_hash(digest)
        if record is None:
            raise ApiException("AUTH_UNAUTHENTICATED")
        async with self._transactions() as repository:
            if not await repository.touch_session(
                record.id, utc_now(), owner_user_id=record.user_id
            ):
                raise ApiException("AUTH_UNAUTHENTICATED")
            user = await repository.get_user(owner_user_id=record.user_id)
            if user is None:
                raise ApiException("AUTH_UNAUTHENTICATED")
        return Identity(user, record)

    async def logout(self, identity: Identity) -> None:
        async with self._transactions() as repository:
            if not await repository.revoke_session(
                identity.session.id, utc_now(), owner_user_id=identity.user.id
            ):
                raise ApiException("AUTH_UNAUTHENTICATED")
