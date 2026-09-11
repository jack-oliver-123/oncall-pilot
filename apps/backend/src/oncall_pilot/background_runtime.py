"""lifespan 拥有的持久队列 worker；内存 task 仅执行已持久化的租约。"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast
from uuid import uuid4

from sqlalchemy import text

from oncall_pilot.background_jobs import (
    BackgroundJobRepository,
    Job,
    JobEvent,
    LeaseLost,
    Outcome,
)
from oncall_pilot.memory.scope import OwnerScope
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.project_config import JsonValue

logger = logging.getLogger(__name__)


class JobContext:
    def __init__(self, database: Database, job: Job) -> None:
        self.database = database
        self.job = job
        self.scope = OwnerScope(job.owner_user_id)
        self.cancelled = asyncio.Event()

    async def emit(self, event_type: str, payload: JsonValue) -> None:
        assert self.job.lease_owner is not None

        async def write() -> None:
            async with self.database.transaction() as session:
                await BackgroundJobRepository(session).append_event(
                    self.job.id,
                    owner_user_id=self.scope.owner_user_id,
                    lease_owner=cast(str, self.job.lease_owner),
                    event_type=event_type,
                    payload=payload,
                )

        writing = asyncio.create_task(write())
        try:
            await asyncio.shield(writing)
        except asyncio.CancelledError:
            await writing
            raise


Handler = Callable[[JobContext], Awaitable[None]]


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, kind: str, handler: Handler) -> None:
        if not kind.strip() or len(kind) > 100 or kind in self._handlers:
            raise ValueError("任务类型无效或重复注册")
        self._handlers[kind] = handler

    def kinds(self) -> tuple[str, ...]:
        return tuple(self._handlers)

    def get(self, kind: str) -> Handler:
        return self._handlers[kind]


class BackgroundWorker:
    def __init__(
        self,
        database: Database,
        registry: HandlerRegistry,
        *,
        concurrency: int = 2,
        lease_seconds: float = 30,
        poll_seconds: float = 0.2,
    ) -> None:
        if (
            type(concurrency) is not int
            or concurrency < 1
            or any(not math.isfinite(v) or v <= 0 for v in (lease_seconds, poll_seconds))
        ):
            raise ValueError("worker 参数无效")
        self.database = database
        self.registry = registry
        self.concurrency = concurrency
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self.worker_id = str(uuid4())
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task[None]] = []
        self._owner_cursor = 0

    async def _owners(self) -> tuple[str, ...]:
        # 调度器专用目录：仅发现持久任务的 owner 标识，不读取业务内容或提供 HTTP 入口。
        # 每个后续事务都重新使用显式 owner scope。
        async with self.database.transaction() as session:
            rows = (
                await session.execute(
                    text("""
                SELECT DISTINCT owner_user_id FROM background_jobs
                WHERE status IN ('queued','running') ORDER BY owner_user_id
            """)
                )
            ).scalars()
            return tuple(cast(str, value) for value in rows)

    async def _next(self) -> Job | None:
        owners = await self._owners()
        if owners:
            offset = self._owner_cursor % len(owners)
            owners = owners[offset:] + owners[:offset]
            self._owner_cursor += 1
        for owner in owners:
            async with self.database.transaction() as session:
                repo = BackgroundJobRepository(session)
                await repo.recover_expired(owner_user_id=owner)
                job = await repo.claim(
                    owner_user_id=owner,
                    worker_id=self.worker_id,
                    kinds=self.registry.kinds(),
                    lease_seconds=self.lease_seconds,
                )
            if job:
                return job
        return None

    async def _heartbeat(self, context: JobContext, finished: asyncio.Event) -> None:
        job = context.job
        assert job.lease_owner is not None
        while not finished.is_set():
            async with self.database.transaction() as session:
                latest = await BackgroundJobRepository(session).heartbeat(
                    job.id,
                    owner_user_id=job.owner_user_id,
                    lease_owner=job.lease_owner,
                    lease_seconds=self.lease_seconds,
                )
            if latest.cancel_requested_at:
                context.cancelled.set()
            await asyncio.sleep(min(self.lease_seconds / 3, self.poll_seconds))

    async def _execute(self, job: Job) -> None:
        context = JobContext(self.database, job)

        async def invoke() -> None:
            await self.registry.get(job.kind)(context)

        handler = asyncio.create_task(invoke())
        finished = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(context, finished))
        stopping = asyncio.create_task(self.stop_event.wait())
        outcome: Outcome = "success"
        try:
            done, _ = await asyncio.wait(
                (handler, heartbeat, stopping),
                timeout=job.timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stopping in done:
                outcome = "shutdown"
            elif not done:
                outcome = "timeout"
            elif heartbeat in done:
                await heartbeat  # 失租或数据库故障，先取消 handler，再由租约恢复。
                raise LeaseLost()
            else:
                await handler
        except asyncio.CancelledError:
            # handler 自行取消不能杀死轮询槽；lifespan 关闭仍向上传播。
            outcome = "shutdown" if self.stop_event.is_set() else "failure"
        except LeaseLost:
            return
        except Exception:
            outcome = "failure"
            # 不输出 payload、kind 或自由格式异常，避免敏感日志泄漏。
            logger.warning("后台任务执行失败")
        finally:
            context.cancelled.set()
            handler.cancel()
            finished.set()
            stopping.cancel()
            # 不取消 SQLite I/O 中的 heartbeat，等其事务与连接正常关闭。
            await asyncio.gather(handler, heartbeat, stopping, return_exceptions=True)
        assert job.lease_owner is not None
        try:
            async with self.database.transaction() as session:
                await BackgroundJobRepository(session).finish(
                    job.id,
                    owner_user_id=job.owner_user_id,
                    lease_owner=job.lease_owner,
                    outcome=outcome,
                )
        except LeaseLost:
            pass
        if self.stop_event.is_set():
            raise asyncio.CancelledError()

    async def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                job = await self._next()
                if job:
                    await self._execute(job)
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                # 单槽故障不结束 worker；未能写回的任务按有限租约回收。
                logger.warning("后台任务轮询暂时失败")
            await asyncio.sleep(self.poll_seconds)

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None]:
        if self.tasks:
            raise RuntimeError("worker 已启动")
        self.stop_event.clear()
        self.tasks = [asyncio.create_task(self._loop()) for _ in range(self.concurrency)]
        try:
            yield
        finally:
            self.stop_event.set()
            # 轮询事务自然结束；执行槽通过 stop_event 终止 handler。
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()


async def replay_events(
    database: Database,
    job_id: str,
    *,
    owner_user_id: str,
    after_sequence: int = 0,
) -> AsyncGenerator[JobEvent]:
    """持久事件快照重放；关闭迭代器不修改任务，不虚构 HTTP 重连协议。"""
    OwnerScope(owner_user_id)
    async with database.transaction() as session:
        events = await BackgroundJobRepository(session).list_events(
            job_id,
            owner_user_id=owner_user_id,
            after_sequence=after_sequence,
        )
    for event in events:
        yield event
