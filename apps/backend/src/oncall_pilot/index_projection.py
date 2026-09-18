"""同一 SQLite 事务中的索引状态投影，不执行外部 I/O。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.memory.scope import OwnerScope


async def project_index_job(session: AsyncSession, job_id: str, *, owner_user_id: str) -> None:
    OwnerScope(owner_user_id)
    row = (
        (
            await session.execute(
                text("""
        SELECT j.*, t.document_id, t.knowledge_base_id FROM background_jobs j
        JOIN document_index_tasks t ON t.id=j.resource_id AND t.owner_user_id=j.owner_user_id
        JOIN knowledge_documents d ON d.id=t.document_id AND d.owner_user_id=t.owner_user_id
          AND d.knowledge_base_id=t.knowledge_base_id
        WHERE j.id=:i AND j.owner_user_id=:o AND j.resource_type='document_index_task'
          AND j.kind='document_index'
    """),
                {"i": job_id, "o": owner_user_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return
    params = {
        "o": owner_user_id,
        "i": row["resource_id"],
        "d": row["document_id"],
        "kb": row["knowledge_base_id"],
        "s": "pending" if row["status"] == "queued" else row["status"],
        "e": row["error_message"],
        "u": row["updated_at"],
        "st": row["started_at"],
        "c": row["completed_at"],
        "cr": row["cancel_requested_at"],
    }
    await session.execute(
        text("""
        UPDATE document_index_tasks SET status=:s,failure_reason=:e,updated_at=:u,
          started_at=:st,completed_at=:c,cancel_requested_at=:cr
        WHERE id=:i AND owner_user_id=:o AND document_id=:d AND knowledge_base_id=:kb
    """),
        params,
    )
    await session.execute(
        text("""
        UPDATE knowledge_documents SET index_status=:s
        WHERE id=:d AND owner_user_id=:o AND knowledge_base_id=:kb AND deleted_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM document_index_tasks WHERE owner_user_id=:o
            AND knowledge_base_id=:kb AND document_id=:d AND retry_of_task_id=:i)
    """),
        params,
    )
