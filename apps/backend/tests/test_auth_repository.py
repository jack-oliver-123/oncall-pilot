from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from oncall_pilot.auth.records import AuthSession, User
from oncall_pilot.auth.repository import AuthRepository, DuplicateEmail
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.memory.values import new_id, utc_now


async def test_records_owner_safety_and_revocation(database: Database) -> None:
    now = utc_now()
    user = User(new_id(), "one@example.com", "$argon2id$test", now)
    other = User(new_id(), "two@example.com", "$argon2id$test", now)
    record = AuthSession(new_id(), user.id, "a" * 64, now, now, None)
    async with database.transaction() as transaction:
        repo = AuthRepository(transaction)
        await repo.add_user(user)
        await repo.add_user(other)
        await repo.add_session(record, owner_user_id=user.id)
    async with database.transaction() as transaction:
        repo = AuthRepository(transaction)
        assert await repo.find_user_by_email(user.email) == user
        assert await repo.resolve_token_hash(record.token_hash) == record
        assert await repo.get_session(record.id, owner_user_id=other.id) is None
        assert not await repo.touch_session(
            record.id, now + timedelta(seconds=1), owner_user_id=other.id
        )
        assert not await repo.revoke_session(
            record.id, now + timedelta(seconds=1), owner_user_id=other.id
        )
        assert await repo.get_session(record.id, owner_user_id=user.id) == record
        assert await repo.touch_session(
            record.id, now + timedelta(seconds=2), owner_user_id=user.id
        )
    async with database.transaction() as transaction:
        repo = AuthRepository(transaction)
        assert await repo.get_session(record.id, owner_user_id=user.id) == replace(
            record, last_seen_at=now + timedelta(seconds=2)
        )
        assert await repo.revoke_session(
            record.id, now + timedelta(seconds=3), owner_user_id=user.id
        )
        assert not await repo.touch_session(
            record.id, now + timedelta(seconds=4), owner_user_id=user.id
        )
        assert await repo.resolve_token_hash(record.token_hash) is None
        assert await repo.find_user_by_email(user.email) == user
    with pytest.raises(FrozenInstanceError):
        field_name = "email"
        setattr(user, field_name, "changed")
    assert user.password_hash not in repr(user)
    assert record.token_hash not in repr(record)


async def test_constraints_and_rollback(database: Database) -> None:
    now = utc_now()
    user = User(new_id(), "one@example.com", "$argon2id$test", now)
    record = AuthSession(new_id(), user.id, "a" * 64, now, now, None)
    async with database.transaction() as transaction:
        await AuthRepository(transaction).add_user(user)
    with pytest.raises(DuplicateEmail):
        async with database.transaction() as transaction:
            await AuthRepository(transaction).add_user(replace(user, id=new_id()))
    for invalid in [replace(record, user_id=new_id()), replace(record, token_hash="raw-token")]:
        with pytest.raises(IntegrityError):
            async with database.transaction() as transaction:
                await AuthRepository(transaction).add_session(
                    invalid, owner_user_id=invalid.user_id
                )
    with pytest.raises(RuntimeError):
        async with database.transaction() as transaction:
            await AuthRepository(transaction).add_session(record, owner_user_id=user.id)
            raise RuntimeError("取消工作单元")
    async with database.transaction() as transaction:
        assert await AuthRepository(transaction).resolve_token_hash(record.token_hash) is None
        await AuthRepository(transaction).add_session(record, owner_user_id=user.id)
    with pytest.raises(IntegrityError):
        async with database.transaction() as transaction:
            await AuthRepository(transaction).add_session(
                replace(record, id=new_id()), owner_user_id=user.id
            )
