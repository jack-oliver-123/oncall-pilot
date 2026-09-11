"""SQLite 持久任务；owner 与租约共同限制所有业务写入。"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.memory.scope import OwnerScope
from oncall_pilot.memory.values import deserialize_json, serialize_json
from oncall_pilot.project_config import JsonValue

Status = Literal["queued", "running", "succeeded", "failed", "cancelled"]
Outcome = Literal["success", "failure", "timeout", "shutdown"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def retry_delay(attempt: int) -> float:
    return float(min(2 ** min(max(attempt, 0), 5), 30))


class Job(BaseModel):
    """不可变 record；JSON 文本防止嵌套数据被原地修改。"""

    model_config = ConfigDict(frozen=True)
    id: str
    owner_user_id: str
    kind: str
    resource_type: str | None
    resource_id: str | None
    status: Status
    payload: str
    attempt: int
    max_attempts: int
    timeout_seconds: float
    available_at: str
    lease_owner: str | None
    lease_expires_at: str | None
    cancel_requested_at: str | None
    retry_of_job_id: str | None
    error_message: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None

    def payload_value(self) -> JsonValue:
        return deserialize_json(self.payload)


class JobEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    job_id: str
    owner_user_id: str
    sequence: int
    event_type: str
    payload: str
    created_at: str


class JobNotFound(Exception):
    """缺失与越权使用相同异常。"""


class InvalidJobState(Exception):
    """已授权任务的状态冲突。"""


class LeaseLost(Exception):
    """执行已经失去写入授权。"""


class BackgroundJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _lock(self, owner_user_id: str) -> None:
        OwnerScope(owner_user_id)
        # 首条写语句取得 SQLite writer lock，防止 deferred read->write 升级死锁。
        await self.session.execute(
            text("UPDATE background_jobs SET id=id WHERE owner_user_id=:o AND 0"),
            {"o": owner_user_id},
        )

    async def create(
        self,
        *,
        owner_user_id: str,
        kind: str,
        payload: JsonValue,
        max_attempts: int = 3,
        timeout_seconds: float = 300,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> Job:
        OwnerScope(owner_user_id)
        if not kind.strip() or len(kind) > 100:
            raise ValueError("任务类型无效")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
            raise ValueError("尝试次数必须为 1–100")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("超时必须为正有限数")
        encoded = serialize_json(payload)
        await self._lock(owner_user_id)
        now = _stamp(_utc_now())
        job_id = str(uuid4())
        await self.session.execute(
            text("""
            INSERT INTO background_jobs
            (id,owner_user_id,kind,resource_type,resource_id,status,payload,attempt,
             max_attempts,timeout_seconds,available_at,created_at,updated_at)
            VALUES (:i,:o,:k,:rt,:ri,'queued',:p,0,:m,:t,:n,:n,:n)
        """),
            {
                "i": job_id,
                "o": owner_user_id,
                "k": kind,
                "rt": resource_type,
                "ri": resource_id,
                "p": encoded,
                "m": max_attempts,
                "t": timeout_seconds,
                "n": now,
            },
        )
        await self._event(job_id, owner_user_id, "queued")
        return await self._require_job(job_id, owner_user_id=owner_user_id)

    async def get(self, job_id: str, *, owner_user_id: str) -> Job | None:
        OwnerScope(owner_user_id)
        row = (
            (
                await self.session.execute(
                    text("SELECT * FROM background_jobs WHERE id=:i AND owner_user_id=:o"),
                    {"i": job_id, "o": owner_user_id},
                )
            )
            .mappings()
            .first()
        )
        return None if row is None else Job.model_validate(dict(row))

    async def _require_job(self, job_id: str, *, owner_user_id: str) -> Job:
        job = await self.get(job_id, owner_user_id=owner_user_id)
        if job is None:
            raise JobNotFound()
        return job

    async def list(self, *, owner_user_id: str) -> tuple[Job, ...]:
        OwnerScope(owner_user_id)
        rows = (
            await self.session.execute(
                text("SELECT * FROM background_jobs WHERE owner_user_id=:o ORDER BY created_at,id"),
                {"o": owner_user_id},
            )
        ).mappings()
        return tuple(Job.model_validate(dict(row)) for row in rows)

    async def _event(
        self,
        job_id: str,
        owner_user_id: str,
        event_type: str,
        payload: str = "{}",
    ) -> None:
        # 同一 writer 事务内 MAX+1 与状态更新一起提交。
        await self.session.execute(
            text("""
            INSERT INTO background_job_events
            (id,job_id,owner_user_id,sequence,event_type,payload,created_at)
            SELECT :id,:i,:o,COALESCE(MAX(sequence),0)+1,:t,:p,:n
            FROM background_job_events WHERE job_id=:i AND owner_user_id=:o
        """),
            {
                "id": str(uuid4()),
                "i": job_id,
                "o": owner_user_id,
                "t": event_type,
                "p": payload,
                "n": _stamp(_utc_now()),
            },
        )

    async def append_event(
        self,
        job_id: str,
        *,
        owner_user_id: str,
        lease_owner: str,
        event_type: str,
        payload: JsonValue,
    ) -> None:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        job = await self._require_job(job_id, owner_user_id=owner_user_id)
        self._require_lease(job, lease_owner)
        if not event_type.strip() or len(event_type) > 100:
            raise ValueError("事件类型无效")
        await self._event(job_id, owner_user_id, event_type, serialize_json(payload))

    async def list_events(
        self,
        job_id: str,
        *,
        owner_user_id: str,
        after_sequence: int = 0,
    ) -> tuple[JobEvent, ...]:
        OwnerScope(owner_user_id)
        await self._require_job(job_id, owner_user_id=owner_user_id)
        if after_sequence < 0:
            raise ValueError("sequence 必须非负")
        rows = (
            await self.session.execute(
                text("""
            SELECT * FROM background_job_events WHERE job_id=:i AND owner_user_id=:o
            AND sequence>:s ORDER BY sequence
        """),
                {"i": job_id, "o": owner_user_id, "s": after_sequence},
            )
        ).mappings()
        return tuple(JobEvent.model_validate(dict(row)) for row in rows)

    @staticmethod
    def _require_lease(job: Job, lease_owner: str) -> None:
        if (
            job.status != "running"
            or job.lease_owner != lease_owner
            or job.lease_expires_at is None
            or job.lease_expires_at <= _stamp(_utc_now())
        ):
            raise LeaseLost()

    async def claim(
        self,
        *,
        owner_user_id: str,
        worker_id: str,
        kinds: tuple[str, ...],
        lease_seconds: float = 30,
    ) -> Job | None:
        OwnerScope(owner_user_id)
        if not kinds:
            return None
        if not worker_id or not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError("租约参数无效")
        await self._lock(owner_user_id)
        placeholders = ",".join(f":k{i}" for i in range(len(kinds)))
        params: dict[str, object] = {f"k{i}": kind for i, kind in enumerate(kinds)}
        params.update(o=owner_user_id, n=_stamp(_utc_now()))
        row = (
            await self.session.execute(
                text(f"""
            SELECT id FROM background_jobs WHERE owner_user_id=:o AND status='queued'
            AND available_at<=:n AND attempt<max_attempts AND kind IN ({placeholders})
            ORDER BY available_at,created_at,id LIMIT 1
        """),
                params,
            )
        ).first()
        if row is None:
            return None
        job_id = cast(str, row[0])
        token = f"{worker_id}:{uuid4()}"
        await self.session.execute(
            text("""
            UPDATE background_jobs SET status='running',attempt=attempt+1,
            started_at=COALESCE(started_at,:n),updated_at=:n,lease_owner=:w,
            lease_expires_at=:e WHERE id=:i AND owner_user_id=:o AND status='queued'
        """),
            {
                "n": _stamp(_utc_now()),
                "w": token,
                "i": job_id,
                "o": owner_user_id,
                "e": _stamp(_utc_now() + timedelta(seconds=lease_seconds)),
            },
        )
        await self._event(job_id, owner_user_id, "running")
        return await self._require_job(job_id, owner_user_id=owner_user_id)

    async def heartbeat(
        self,
        job_id: str,
        *,
        owner_user_id: str,
        lease_owner: str,
        lease_seconds: float = 30,
    ) -> Job:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        job = await self._require_job(job_id, owner_user_id=owner_user_id)
        self._require_lease(job, lease_owner)
        await self.session.execute(
            text("""
            UPDATE background_jobs SET lease_expires_at=:e,updated_at=:n
            WHERE id=:i AND owner_user_id=:o AND lease_owner=:w
        """),
            {
                "e": _stamp(_utc_now() + timedelta(seconds=lease_seconds)),
                "n": _stamp(_utc_now()),
                "i": job_id,
                "o": owner_user_id,
                "w": lease_owner,
            },
        )
        return await self._require_job(job_id, owner_user_id=owner_user_id)

    async def _transition(self, job: Job, status: Status, error: str | None = None) -> Job:
        now = _utc_now()
        await self.session.execute(
            text("""
            UPDATE background_jobs SET status=:s,error_message=:err,updated_at=:n,
            available_at=:a,completed_at=:c,lease_owner=NULL,lease_expires_at=NULL
            WHERE id=:i AND owner_user_id=:o
        """),
            {
                "s": status,
                "err": error,
                "n": _stamp(now),
                "a": _stamp(now + timedelta(seconds=retry_delay(job.attempt)))
                if status == "queued"
                else job.available_at,
                "c": None if status == "queued" else _stamp(now),
                "i": job.id,
                "o": job.owner_user_id,
            },
        )
        await self._event(job.id, job.owner_user_id, status)
        return await self._require_job(job.id, owner_user_id=job.owner_user_id)

    async def finish(
        self,
        job_id: str,
        *,
        owner_user_id: str,
        lease_owner: str,
        outcome: Outcome,
    ) -> Job:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        job = await self._require_job(job_id, owner_user_id=owner_user_id)
        self._require_lease(job, lease_owner)
        status: Status = "succeeded"
        errors = {
            "failure": "任务执行失败。",
            "timeout": "任务执行超时。",
            "shutdown": "任务执行中断，等待恢复。",
        }
        if job.cancel_requested_at is not None:
            status = "cancelled"
        elif outcome != "success":
            status = "queued" if job.attempt < job.max_attempts else "failed"
        return await self._transition(job, status, errors.get(outcome))

    async def recover_expired(self, *, owner_user_id: str) -> int:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        rows = (
            (
                await self.session.execute(
                    text("""
            SELECT * FROM background_jobs WHERE owner_user_id=:o AND status='running'
            AND lease_expires_at<=:n
        """),
                    {"o": owner_user_id, "n": _stamp(_utc_now())},
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            job = Job.model_validate(dict(row))
            status: Status = (
                "cancelled"
                if job.cancel_requested_at
                else ("queued" if job.attempt < job.max_attempts else "failed")
            )
            await self._transition(job, status, "任务租约到期，执行已中断。")
        return len(rows)

    async def cancel(self, job_id: str, *, owner_user_id: str) -> Job:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        job = await self._require_job(job_id, owner_user_id=owner_user_id)
        if job.status == "cancelled" or job.cancel_requested_at:
            return job
        if job.status not in ("queued", "running"):
            raise InvalidJobState()
        await self.session.execute(
            text("""
            UPDATE background_jobs SET cancel_requested_at=:n,updated_at=:n
            WHERE id=:i AND owner_user_id=:o
        """),
            {"n": _stamp(_utc_now()), "i": job_id, "o": owner_user_id},
        )
        await self._event(job_id, owner_user_id, "cancel_requested")
        if job.status == "queued":
            return await self._transition(job, "cancelled")
        return await self._require_job(job_id, owner_user_id=owner_user_id)

    async def retry(self, job_id: str, *, owner_user_id: str) -> Job:
        OwnerScope(owner_user_id)
        await self._lock(owner_user_id)
        job = await self._require_job(job_id, owner_user_id=owner_user_id)
        if job.status not in ("failed", "cancelled"):
            raise InvalidJobState()
        new_job = await self.create(
            owner_user_id=owner_user_id,
            kind=job.kind,
            payload=job.payload_value(),
            max_attempts=job.max_attempts,
            timeout_seconds=job.timeout_seconds,
            resource_type=job.resource_type,
            resource_id=job.resource_id,
        )
        await self.session.execute(
            text("""
            UPDATE background_jobs SET retry_of_job_id=:r WHERE id=:i AND owner_user_id=:o
        """),
            {"r": job.id, "i": new_job.id, "o": owner_user_id},
        )
        await self._event(job_id, owner_user_id, "retried")
        return await self._require_job(new_job.id, owner_user_id=owner_user_id)
