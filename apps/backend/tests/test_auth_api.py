from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from pwdlib import PasswordHash
from pydantic import ValidationError
from sqlalchemy import text
from test_protocol import assert_openapi_matches, validator

from oncall_pilot.app import create_app
from oncall_pilot.auth.passwords import PasswordManager
from oncall_pilot.generated_contracts import LoginRequest, RegisterRequest
from oncall_pilot.memory.sqlite import Database


@pytest.fixture
async def auth_client(migrated_config: Path) -> AsyncGenerator[httpx.AsyncClient]:
    app = create_app(migrated_config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"X-Request-ID": "auth-test"},
        ) as client:
            yield client


async def test_register_login_restore_revoke_and_secret_storage(
    auth_client: httpx.AsyncClient,
    database: Database,
    migrated_config: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    credentials = {"email": " Person@Example.COM ", "password": "unique-secret-password"}
    registered = await auth_client.post("/auth/register", json=credentials)
    assert registered.status_code == 200
    validator("UserResponse").validate(registered.json())
    user = registered.json()["data"]
    assert user["email"] == "person@example.com"
    assert set(user) == {"id", "email", "createdAt"}
    duplicate = await auth_client.post(
        "/auth/register", json={**credentials, "email": "PERSON@example.com"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "BUSINESS_EMAIL_ALREADY_EXISTS"
    tokens: list[str] = []
    for _ in range(2):
        login = await auth_client.post("/auth/login", json=credentials)
        assert login.status_code == 200
        validator("LoginResponse").validate(login.json())
        token = login.json()["data"]["token"]
        assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
        assert login.json()["data"]["user"] == user
        tokens.append(token)
    assert tokens[0] != tokens[1]
    async with database.transaction() as session:
        rows = (await session.execute(text("SELECT * FROM users"))).mappings().all()
        assert len(rows) == 1
        password_hash = str(rows[0]["password_hash"])
        assert password_hash.startswith("$argon2id$")
        assert credentials["password"] not in password_hash
        assert PasswordManager().verify(credentials["password"], password_hash)
        sessions = (await session.execute(text("SELECT * FROM auth_sessions"))).mappings().all()
        assert {row["token_hash"] for row in sessions} == {
            hashlib.sha256(token.encode()).hexdigest() for token in tokens
        }
        assert all(row["created_at"] == row["last_seen_at"] for row in sessions)
        original_created = sessions[0]["created_at"]
        await session.execute(text("CREATE TABLE test_business_data (value TEXT)"))
        await session.execute(text("INSERT INTO test_business_data VALUES ('保留')"))
    auth_client.headers["Authorization"] = f"Bearer {tokens[0]}"
    me = await auth_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["data"] == user
    async with database.transaction() as session:
        row = (
            (
                await session.execute(
                    text("SELECT * FROM auth_sessions WHERE token_hash=:hash"),
                    {"hash": hashlib.sha256(tokens[0].encode()).hexdigest()},
                )
            )
            .mappings()
            .one()
        )
        assert row["created_at"] == original_created
        assert row["last_seen_at"] > original_created
    logout = await auth_client.post("/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["data"] is None
    assert (await auth_client.get("/auth/me")).status_code == 401
    assert (await auth_client.post("/auth/logout")).status_code == 401
    auth_client.headers["Authorization"] = f"Bearer {tokens[1]}"
    assert (await auth_client.get("/auth/me")).status_code == 200
    async with database.transaction() as session:
        assert await session.scalar(text("SELECT count(*) FROM users")) == 1
        assert (
            await session.scalar(
                text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL")
            )
            == 1
        )
        assert await session.scalar(text("SELECT value FROM test_business_data")) == "保留"
    for response in [registered, duplicate, me, logout]:
        assert response.headers["X-Request-ID"] == response.json()["meta"]["requestId"]
        assert response.headers["Cache-Control"] == "no-store"
    for secret in [credentials["password"], *tokens]:
        assert secret not in caplog.text
        for path in migrated_config.parent.rglob("*.db*"):
            assert secret.encode() not in path.read_bytes()


async def test_unknown_and_wrong_password_both_run_argon2(
    auth_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = {"email": "known@example.com", "password": "valid-password"}
    assert (await auth_client.post("/auth/register", json=credentials)).status_code == 200
    hashes: list[str] = []
    original = PasswordHash.verify

    def observe(self: PasswordHash, password: str | bytes, encoded: str | bytes) -> bool:
        hashes.append(encoded.decode() if isinstance(encoded, bytes) else encoded)
        return original(self, password, encoded)

    monkeypatch.setattr(PasswordHash, "verify", observe)
    responses = [
        await auth_client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        for email in ["known@example.com", "unknown@example.com"]
    ]
    assert len(hashes) == 2
    assert all(encoded.startswith("$argon2id$") for encoded in hashes)
    assert hashes[0] != hashes[1]
    assert hashes[0].split("$")[3] == hashes[1].split("$")[3]
    assert responses[0].json() == responses[1].json()
    assert all(response.status_code == 401 for response in responses)
    assert responses[0].json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.parametrize(
    "authorization", [None, "Basic abc", "Bearer", "Bearer bad", "Bearer " + "x" * 43]
)
async def test_missing_malformed_unknown_tokens_use_envelope(
    auth_client: httpx.AsyncClient,
    authorization: str | None,
) -> None:
    for path, method in [("/auth/me", "GET"), ("/auth/logout", "POST")]:
        response = await auth_client.request(
            method, path, headers={} if authorization is None else {"Authorization": authorization}
        )
        assert response.status_code == 401
        validator("ApiFailure").validate(response.json())
        assert response.json()["error"]["code"] == "AUTH_UNAUTHENTICATED"
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.headers["X-Request-ID"] == response.json()["meta"]["requestId"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "bad"},
        {"password": "short"},
        {"password": "x" * 129},
        {"ownerId": "someone-else"},
        {"email": "x" * 255 + "@example.com"},
    ],
)
async def test_validation_never_echoes_password(
    auth_client: httpx.AsyncClient,
    overrides: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = {"email": "valid@example.com", "password": "do-not-log-this", **overrides}
    for path in ["/auth/register", "/auth/login"]:
        response = await auth_client.post(path, json=body)
        assert response.status_code == 422
        validator("ApiFailure").validate(response.json())
        assert body["password"] not in response.text + caplog.text


async def test_cors_and_actual_auth_openapi(
    auth_client: httpx.AsyncClient, migrated_config: Path
) -> None:
    assert_openapi_matches(create_app(migrated_config))
    doc = create_app(migrated_config).openapi()
    assert doc["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    for path, method in [("/auth/me", "get"), ("/auth/logout", "post")]:
        assert doc["paths"][path][method]["security"] == [{"BearerAuth": []}]
    for origin, status in [("http://127.0.0.1:5173", 200), ("https://other.example", 400)]:
        response = await auth_client.options(
            "/auth/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
            },
        )
        assert response.status_code == status
        if status == 200:
            assert response.headers["Access-Control-Allow-Origin"] == origin
        else:
            assert "Access-Control-Allow-Origin" not in response.headers


async def test_old_session_has_no_implicit_expiry(
    auth_client: httpx.AsyncClient, database: Database
) -> None:
    credentials = {"email": "old@example.com", "password": "old-password"}
    await auth_client.post("/auth/register", json=credentials)
    token = (await auth_client.post("/auth/login", json=credentials)).json()["data"]["token"]
    async with database.transaction() as session:
        old = datetime.now(timezone.utc) - timedelta(days=730)
        await session.execute(
            text("UPDATE auth_sessions SET created_at=:old, last_seen_at=:old"),
            {
                "old": old.replace(tzinfo=None).isoformat(sep=" "),
            },
        )
    response = await auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "length,valid", [(4, False), (8, True), (65, True), (128, True), (129, False)]
)
def test_unicode_password_contract_length(length: int, valid: bool) -> None:
    for model in [RegisterRequest, LoginRequest]:
        data = {"email": "person@example.com", "password": "😀" * length}
        if valid:
            assert model.model_validate(data).password == data["password"]
        else:
            with pytest.raises(ValidationError):
                model.model_validate(data)


async def test_concurrent_registration_and_authenticated_requests(
    auth_client: httpx.AsyncClient,
) -> None:
    credentials = {"email": "race@example.com", "password": "race-password"}
    registrations = await asyncio.gather(
        *[auth_client.post("/auth/register", json=credentials) for _ in range(2)]
    )
    assert sorted(response.status_code for response in registrations) == [200, 409]
    login = await auth_client.post("/auth/login", json=credentials)
    token = login.json()["data"]["token"]
    responses = await asyncio.gather(
        *[
            auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            for _ in range(4)
        ]
    )
    assert all(response.status_code == 200 for response in responses)
