"""临时 SQLite 与 fake handler 的持久任务验收。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from scope_contract import assert_owner_parameter_contract
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot import background_jobs as jobs
from oncall_pilot.background_jobs import BackgroundJobRepository as Repo
from oncall_pilot.background_jobs import InvalidJobState, Job, JobNotFound, LeaseLost
from oncall_pilot.background_runtime import (
    BackgroundWorker,
    HandlerRegistry,
    JobContext,
    replay_events,
)
from oncall_pilot.memory.sqlite import Database


@pytest.fixture
async def owners(database: Database) -> tuple[str, str]:
    async with database.transaction() as session:
        for owner in ("a", "b"):
            await session.execute(
                text("""
                INSERT INTO users(id,email,password_hash,created_at) VALUES (:i,:e,'hash',:n)
            """),
                {"i": owner, "e": owner + "@example.com", "n": "2026-09-10"},
            )
    return "a", "b"


async def enqueue(
    database: Database,
    owner: str = "a",
    *,
    attempts: int = 3,
    timeout: float = 10,
    kind: str = "fake",
) -> Job:
    async with database.transaction() as session:
        return await Repo(session).create(
            owner_user_id=owner,
            kind=kind,
            payload={"secret": "sentinel"},
            max_attempts=attempts,
            timeout_seconds=timeout,
        )


async def read(database: Database, job: Job) -> Job:
    async with database.transaction() as session:
        result = await Repo(session).get(job.id, owner_user_id=job.owner_user_id)
        assert result is not None
        return result


async def claim(database: Database, *, lease: float = 30) -> Job | None:
    async with database.transaction() as session:
        return await Repo(session).claim(
            owner_user_id="a", worker_id="test", kinds=("fake",), lease_seconds=lease
        )


async def wait_status(database: Database, job: Job, status: str) -> Job:
    async def wait() -> Job:
        while True:
            current = await read(database, job)
            if current.status == status:
                return current
            await asyncio.sleep(0.01)

    return await asyncio.wait_for(wait(), 8)


async def test_owner_parameter_contract_before_io() -> None:
    session = MagicMock(spec=AsyncSession)
    repo = Repo(session)
    await assert_owner_parameter_contract(repo.create, kind="fake", payload={})
    await assert_owner_parameter_contract(repo.list)
    await assert_owner_parameter_contract(repo.get, job_id="x")
    await assert_owner_parameter_contract(repo.cancel, job_id="x")
    await assert_owner_parameter_contract(repo.retry, job_id="x")
    await assert_owner_parameter_contract(repo.list_events, job_id="x")
    await assert_owner_parameter_contract(
        repo.append_event, job_id="x", lease_owner="x", event_type="progress", payload={}
    )
    await assert_owner_parameter_contract(repo.claim, worker_id="x", kinds=("fake",))
    await assert_owner_parameter_contract(repo.heartbeat, job_id="x", lease_owner="x")
    await assert_owner_parameter_contract(
        repo.finish, job_id="x", lease_owner="x", outcome="success"
    )
    await assert_owner_parameter_contract(repo.recover_expired)
    assert not session.mock_calls


@pytest.mark.usefixtures("owners")
async def test_atomic_claim_and_ordered_events(database: Database) -> None:
    job = await enqueue(database)
    claims = await asyncio.gather(*(claim(database) for _ in range(6)))
    winners = [result for result in claims if result]
    assert len(winners) == 1
    winner = winners[0]
    assert winner.attempt == 1
    assert winner.lease_owner

    async def emit(number: int) -> None:
        async with database.transaction() as session:
            await Repo(session).append_event(
                job.id,
                owner_user_id="a",
                lease_owner=cast(str, winner.lease_owner),
                event_type="progress",
                payload=number,
            )

    await asyncio.gather(*(emit(i) for i in range(6)))
    async with database.transaction() as session:
        events = await Repo(session).list_events(job.id, owner_user_id="a")
        assert [e.sequence for e in events] == list(range(1, 9))
        assert [e.event_type for e in events[:2]] == ["queued", "running"]
        assert (
            len(await Repo(session).list_events(job.id, owner_user_id="a", after_sequence=5)) == 3
        )


@pytest.mark.usefixtures("owners")
async def test_owner_isolation_and_parent_fk(database: Database) -> None:
    job = await enqueue(database)
    async with database.transaction() as session:
        repo = Repo(session)
        assert await repo.list(owner_user_id="b") == ()
        assert await repo.get(job.id, owner_user_id="b") is None
        for method in (repo.cancel, repo.retry, repo.list_events):
            with pytest.raises(JobNotFound):
                await method(job.id, owner_user_id="b")
        with pytest.raises(JobNotFound):
            await repo.append_event(
                job.id, owner_user_id="b", lease_owner="x", event_type="progress", payload={}
            )
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            await session.execute(
                text("""
                INSERT INTO background_job_events
                (id,job_id,owner_user_id,sequence,event_type,payload,created_at)
                VALUES ('bad',:i,'b',1,'progress','{}','2026-09-10')
            """),
                {"i": job.id},
            )


@pytest.mark.usefixtures("owners")
async def test_heartbeat_expiry_fencing_and_max_attempts(
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, "_utc_now", lambda: now)
    job = await enqueue(database, attempts=2)
    first = await claim(database)
    assert first and first.lease_owner
    now += timedelta(seconds=20)
    async with database.transaction() as session:
        renewed = await Repo(session).heartbeat(
            job.id, owner_user_id="a", lease_owner=first.lease_owner
        )
        assert renewed.lease_expires_at is not None
        assert renewed.lease_expires_at > cast(str, first.lease_expires_at)
    now += timedelta(seconds=20)
    async with database.transaction() as session:
        assert await Repo(session).recover_expired(owner_user_id="a") == 0
    now += timedelta(seconds=20)
    async with database.transaction() as session:
        repo = Repo(session)
        assert await repo.recover_expired(owner_user_id="a") == 1
        with pytest.raises(LeaseLost):
            await repo.finish(
                job.id, owner_user_id="a", lease_owner=first.lease_owner, outcome="success"
            )
    assert await claim(database) is None  # 回收同样应用退避。
    now += timedelta(seconds=3)
    second = await claim(database)
    assert second and second.lease_owner != first.lease_owner and second.attempt == 2
    async with database.transaction() as session:
        with pytest.raises(LeaseLost):
            await Repo(session).append_event(
                job.id,
                owner_user_id="a",
                lease_owner=first.lease_owner,
                event_type="stale",
                payload={},
            )
    now += timedelta(seconds=31)
    async with database.transaction() as session:
        assert await Repo(session).recover_expired(owner_user_id="a") == 1
    assert (await read(database, job)).status == "failed"
    assert await claim(database) is None


@pytest.mark.usefixtures("owners")
async def test_retry_backoff_and_manual_retry(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, "_utc_now", lambda: now)
    job = await enqueue(database, attempts=2)
    assert [jobs.retry_delay(i) for i in (1, 2, 3, 4, 5, 10000)] == [2, 4, 8, 16, 30, 30]
    for expected in ("queued", "failed"):
        leased = await claim(database)
        assert leased and leased.lease_owner
        async with database.transaction() as session:
            result = await Repo(session).finish(
                job.id, owner_user_id="a", lease_owner=leased.lease_owner, outcome="failure"
            )
            assert result.status == expected
        assert await claim(database) is None
        now += timedelta(seconds=3)
    async with database.transaction() as session:
        repo = Repo(session)
        retried = await repo.retry(job.id, owner_user_id="a")
        assert retried.id != job.id and retried.retry_of_job_id == job.id
        assert retried.attempt == 0 and retried.started_at is None
        original = await repo.get(job.id, owner_user_id="a")
        assert original is not None and original.status == "failed"
        with pytest.raises(InvalidJobState):
            await repo.retry(retried.id, owner_user_id="a")


@pytest.mark.usefixtures("owners")
async def test_worker_timeout_cleanup_and_redacted_failure(
    database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    stopped = asyncio.Event()

    async def slow(ctx: JobContext) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    registry = HandlerRegistry()
    registry.register("fake", slow)
    job = await enqueue(database, attempts=1, timeout=0.15)
    worker = BackgroundWorker(database, registry, lease_seconds=1, poll_seconds=0.02)
    async with worker.lifespan():
        failed = await wait_status(database, job, "failed")
        assert stopped.is_set() and failed.lease_owner is None
        assert failed.error_message == "任务执行超时。"
    assert worker.tasks == []

    async def bad(ctx: JobContext) -> None:
        raise RuntimeError("password=sentinel token=secret")

    registry2 = HandlerRegistry()
    registry2.register("fake", bad)
    job2 = await enqueue(database, attempts=1)
    async with BackgroundWorker(database, registry2).lifespan():
        failed2 = await wait_status(database, job2, "failed")
        assert failed2.error_message == "任务执行失败。"
    assert "sentinel" not in caplog.text and "token=secret" not in caplog.text


@pytest.mark.usefixtures("owners")
async def test_cooperative_cancel_and_queued_cancel(database: Database) -> None:
    queued = await enqueue(database)
    async with database.transaction() as session:
        cancelled = await Repo(session).cancel(queued.id, owner_user_id="a")
        assert cancelled.status == "cancelled" and cancelled.attempt == 0
    running = await enqueue(database)
    started = asyncio.Event()
    observed = asyncio.Event()

    async def handler(ctx: JobContext) -> None:
        started.set()
        await ctx.cancelled.wait()
        observed.set()

    registry = HandlerRegistry()
    registry.register("fake", handler)
    async with BackgroundWorker(database, registry, poll_seconds=0.02).lifespan():
        await asyncio.wait_for(started.wait(), 5)
        async with database.transaction() as session:
            requested = await Repo(session).cancel(running.id, owner_user_id="a")
            assert requested.status == "running" and requested.cancel_requested_at
        final = await wait_status(database, running, "cancelled")
        assert observed.is_set() and final.lease_owner is None


@pytest.mark.usefixtures("owners")
async def test_worker_heartbeat_concurrency_disconnect_replay(database: Database) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum = 0

    async def handler(ctx: JobContext) -> None:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await ctx.emit("progress", {"message": "正在处理"})
        if active == 2:
            started.set()
        try:
            await release.wait()
        finally:
            active -= 1

    registry = HandlerRegistry()
    registry.register("fake", handler)
    targets = [await enqueue(database, owner) for owner in ("a", "b", "a")]
    worker = BackgroundWorker(database, registry, lease_seconds=2.4, poll_seconds=0.1)
    async with worker.lifespan():
        await asyncio.wait_for(started.wait(), 5)
        stream = replay_events(database, targets[0].id, owner_user_id="a")
        await anext(stream)
        await stream.aclose()  # 模拟 SSE consumer 断开。
        await asyncio.sleep(2.8)
        current = await read(database, targets[0])
        assert current.status == "running" and current.cancel_requested_at is None
        assert current.attempt == 1
        release.set()
        for target in targets:
            await wait_status(database, target, "succeeded")
        replay = [
            event async for event in replay_events(database, targets[0].id, owner_user_id="a")
        ]
        assert [event.event_type for event in replay] == [
            "queued",
            "running",
            "progress",
            "succeeded",
        ]
        assert maximum == 2


@pytest.mark.usefixtures("owners")
async def test_shutdown_restart_and_unknown_kind(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def blocked(ctx: JobContext) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    registry = HandlerRegistry()
    registry.register("fake", blocked)
    target = await enqueue(database)
    unknown = await enqueue(database, kind="future")
    worker = BackgroundWorker(database, registry)
    async with worker.lifespan():
        await asyncio.wait_for(started.wait(), 5)
    assert cleaned.is_set() and not worker.tasks
    stopped = await read(database, target)
    assert stopped.status == "queued" and stopped.lease_owner is None
    assert (await read(database, unknown)).attempt == 0
    now = datetime.now(timezone.utc) + timedelta(seconds=3)
    monkeypatch.setattr(jobs, "_utc_now", lambda: now)

    async def resumed(ctx: JobContext) -> None:
        await ctx.emit("resumed", {})

    registry2 = HandlerRegistry()
    registry2.register("fake", resumed)
    async with BackgroundWorker(database, registry2).lifespan():
        final = await wait_status(database, target, "succeeded")
        assert final.attempt == 2


@pytest.mark.usefixtures("owners")
async def test_worker_recovers_after_poll_crash(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def handler(ctx: JobContext) -> None:
        return None

    registry = HandlerRegistry()
    registry.register("fake", handler)
    worker = BackgroundWorker(database, registry, concurrency=1, poll_seconds=0.01)
    original = worker._next  # pyright: ignore[reportPrivateUsage]
    count = 0

    async def flaky() -> Job | None:
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("secret-token")
        return await original()

    monkeypatch.setattr(worker, "_next", flaky)
    target = await enqueue(database)
    async with worker.lifespan():
        await wait_status(database, target, "succeeded")
    assert count >= 2


@pytest.mark.usefixtures("owners")
async def test_independent_process_exit_and_restart(
    database: Database, migrated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """新进程领取后退出，另一个 engine/runtime 恢复同一磁盘记录。"""
    import sys

    from oncall_pilot.memory.sqlite import open_database

    target = await enqueue(database)
    script = """
import asyncio,sys
from pathlib import Path
from oncall_pilot.memory.sqlite import open_database
from oncall_pilot.background_jobs import BackgroundJobRepository
async def run():
    async with open_database(Path(sys.argv[1])) as db:
        async with db.transaction() as s:
            job=await BackgroundJobRepository(s).claim(
                owner_user_id='a',worker_id='exited-process',kinds=('fake',),lease_seconds=.1)
            assert job is not None
asyncio.run(run())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script, str(migrated_config)
    )
    assert await asyncio.wait_for(process.wait(), 10) == 0
    now = datetime.now(timezone.utc) + timedelta(seconds=1)
    monkeypatch.setattr(jobs, "_utc_now", lambda: now)
    async with open_database(migrated_config) as reopened:
        async with reopened.transaction() as session:
            assert await Repo(session).recover_expired(owner_user_id="a") == 1
        now += timedelta(seconds=3)

        async def handler(ctx: JobContext) -> None:
            await ctx.emit("restarted", {})

        registry = HandlerRegistry()
        registry.register("fake", handler)
        async with BackgroundWorker(reopened, registry).lifespan():
            final = await wait_status(reopened, target, "succeeded")
            assert final.attempt == 2
        events = [e async for e in replay_events(reopened, target.id, owner_user_id="a")]
        assert [e.event_type for e in events] == [
            "queued",
            "running",
            "queued",
            "running",
            "restarted",
            "succeeded",
        ]
