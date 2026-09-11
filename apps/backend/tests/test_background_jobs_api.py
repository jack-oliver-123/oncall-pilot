"""真实认证、临时 SQLite 和后台任务 HTTP/lifespan 合同。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import httpx
import pytest
from test_protocol import assert_openapi_matches, validator

from oncall_pilot.app import create_app
from oncall_pilot.background_jobs import BackgroundJobRepository
from oncall_pilot.background_runtime import BackgroundWorker, HandlerRegistry, JobContext
from oncall_pilot.memory.sqlite import Database


async def login(client: httpx.AsyncClient, name: str) -> tuple[str, dict[str, str]]:
    body = {"email": name + "@example.com", "password": "password-12345"}
    user = (await client.post("/auth/register", json=body)).json()["data"]["id"]
    token = (await client.post("/auth/login", json=body)).json()["data"]["token"]
    return user, {"Authorization": "Bearer " + token}


async def test_jobs_api_owner_contract_and_lifespan(migrated_config: Path) -> None:
    app = create_app(migrated_config)
    assert_openapi_matches(app)
    async with app.router.lifespan_context(app):
        worker = cast(BackgroundWorker, app.state.background_worker)
        db = cast(Database, app.state.background_database)
        assert len(worker.tasks) == 2
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"X-Request-ID": "job-test"},
        ) as client:
            owner, auth = await login(client, "first")
            _, other = await login(client, "second")
            async with db.transaction() as session:
                job = await BackgroundJobRepository(session).create(
                    owner_user_id=owner, kind="future", payload={"value": "持久化"}
                )
            for suffix, method in [("", "GET"), (":cancel", "POST"), (":retry", "POST")]:
                url = "/background-jobs/" + job.id + suffix
                assert (await client.request(method, url)).status_code == 401
                denied = await client.request(method, url, headers=other)
                missing = await client.request(
                    method, "/background-jobs/missing" + suffix, headers=auth
                )
                assert denied.status_code == missing.status_code == 403
                assert denied.json() == missing.json()
            listed = await client.get("/background-jobs", headers=auth)
            validator("BackgroundJobListResponse").validate(listed.json())
            assert len(listed.json()["data"]) == 1
            assert (await client.get("/background-jobs", headers=other)).json()["data"] == []
            detail = await client.get("/background-jobs/" + job.id, headers=auth)
            validator("BackgroundJobResponse").validate(detail.json())
            assert detail.json()["data"]["payload"] == {"value": "持久化"}
            assert (
                await client.post("/background-jobs/" + job.id + ":retry", headers=auth)
            ).status_code == 409
            cancelled = await client.post("/background-jobs/" + job.id + ":cancel", headers=auth)
            assert cancelled.json()["data"]["status"] == "cancelled"
            retry = await client.post("/background-jobs/" + job.id + ":retry", headers=auth)
            validator("BackgroundJobResponse").validate(retry.json())
            assert retry.json()["data"]["retryOfJobId"] == job.id
            assert retry.json()["data"]["id"] != job.id
            await client.post("/auth/logout", headers=auth)
            assert (await client.get("/background-jobs", headers=auth)).status_code == 401
            async with db.transaction() as session:
                assert len(await BackgroundJobRepository(session).list(owner_user_id=owner)) == 2
    assert worker.tasks == []
    assert not hasattr(app.state, "background_database")
    with pytest.raises(RuntimeError, match="关闭"):
        async with db.transaction():
            pass


async def test_app_lifespan_cleans_running_handler(migrated_config: Path) -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def handler(ctx: JobContext) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    registry = HandlerRegistry()
    registry.register("fake", handler)
    app = create_app(migrated_config, job_handlers=registry)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            owner, _ = await login(client, "lifespan")
        db = cast(Database, app.state.background_database)
        async with db.transaction() as session:
            await BackgroundJobRepository(session).create(
                owner_user_id=owner, kind="fake", payload={}
            )
        await asyncio.wait_for(started.wait(), 5)
    assert cleaned.is_set()
