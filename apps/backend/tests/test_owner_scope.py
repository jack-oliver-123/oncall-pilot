from dataclasses import FrozenInstanceError
from typing import Any
from unittest.mock import AsyncMock

import pytest
from scope_contract import assert_owner_parameter_contract
from sqlalchemy.ext.asyncio import AsyncSession

from oncall_pilot.auth.records import AuthSession
from oncall_pilot.auth.repository import AuthRepository
from oncall_pilot.memory.scope import CurrentUser, InvalidOwnerScope, OwnerScope
from oncall_pilot.memory.values import utc_now
from oncall_pilot.memory.vector_scope import (
    document_delete_filter,
    scoped_recall,
    search_filter,
    vector_metadata,
    vector_ownership,
)


def test_immutable_context_and_derived_tenant() -> None:
    for user_id in ["user-a", "user-b"]:
        user = CurrentUser(user_id)
        assert user.tenant_id == user.user_id == user.owner_scope.owner_user_id
        assert user.owner_scope.tenant_id == user_id
        with pytest.raises(FrozenInstanceError):
            field = "user_id"
            setattr(user, field, "other")
        with pytest.raises(FrozenInstanceError):
            field = "owner_user_id"
            setattr(user.owner_scope, field, "other")
        with pytest.raises(InvalidOwnerScope):
            user.owner_scope.require_owner("other")


@pytest.mark.parametrize("invalid", [None, "", " ", "\n", 0, False, " bad", "a\x00b"])
def test_invalid_context_fails(invalid: Any) -> None:
    for context in [CurrentUser, OwnerScope]:
        with pytest.raises(InvalidOwnerScope):
            context(invalid)


async def test_auth_repository_parameters_fail_before_session_access() -> None:
    session = AsyncMock(spec=AsyncSession)
    repo = AuthRepository(session)
    now = utc_now()
    record = AuthSession("session", "user-a", "a" * 64, now, now, None)
    await assert_owner_parameter_contract(repo.get_user)
    await assert_owner_parameter_contract(repo.add_session, record=record)
    await assert_owner_parameter_contract(repo.get_session, session_id="session")
    await assert_owner_parameter_contract(repo.touch_session, session_id="session", now=now)
    await assert_owner_parameter_contract(repo.revoke_session, session_id="session", now=now)
    with pytest.raises(InvalidOwnerScope):
        await repo.add_session(record, owner_user_id="user-b")
    assert session.mock_calls == []


def test_vector_fields_and_exact_filters() -> None:
    assert vector_metadata({"title": "资料"}, owner_user_id="user-a") == {
        "title": "资料",
        "tenantId": "user-a",
        "ownerUserId": "user-a",
    }
    for key in ["tenantId", "ownerUserId"]:
        with pytest.raises(InvalidOwnerScope):
            vector_metadata({key: "user-b"}, owner_user_id="user-a")
    assert vector_ownership(owner_user_id="user-a") == {
        "tenantId": "user-a",
        "ownerUserId": "user-a",
    }
    assert search_filter(
        owner_user_id="user-a", allowed_knowledge_base_ids=["kb-1", "kb-2", "kb-1"]
    ) == ('tenantId == "user-a" and knowledgeBaseId in ["kb-1", "kb-2"]')
    assert document_delete_filter(
        owner_user_id="user-a", knowledge_base_id="kb-1", document_id="doc-1"
    ) == ('tenantId == "user-a" and knowledgeBaseId == "kb-1" and documentId == "doc-1"')
    # 用户输入只能成为转义后的字符串字面值，不能引入额外表达式。
    assert search_filter(owner_user_id='a" or true', allowed_knowledge_base_ids=['k\\"']) == (
        'tenantId == "a\\" or true" and knowledgeBaseId in ["k\\\\\\""]'
    )


@pytest.mark.parametrize("invalid", [None, "", " ", 0, False])
async def test_empty_vector_scopes_cannot_reach_adapter(invalid: Any) -> None:
    recall = AsyncMock()
    with pytest.raises(InvalidOwnerScope):
        await scoped_recall(owner_user_id=invalid, allowed_knowledge_base_ids=[], recall=recall)
    for field in ["owner_user_id", "knowledge_base_id", "document_id"]:
        arguments: dict[str, Any] = {
            "owner_user_id": "a",
            "knowledge_base_id": "kb",
            "document_id": "doc",
        }
        arguments[field] = invalid
        with pytest.raises(InvalidOwnerScope):
            document_delete_filter(**arguments)
    with pytest.raises(InvalidOwnerScope):
        await scoped_recall(owner_user_id="a", allowed_knowledge_base_ids=[invalid], recall=recall)
    recall.assert_not_called()


async def test_empty_kbs_short_circuit_and_post_filter_runs_after_recall() -> None:
    events: list[str] = []

    async def recall(expression: str) -> list[str]:
        events.append(expression)
        return ["doc-1", "doc-2"]

    def post_filter(hit: str) -> bool:
        assert len(events) >= 1
        events.append(hit)
        return hit == "doc-2"

    assert (
        await scoped_recall(
            owner_user_id="a", allowed_knowledge_base_ids=[], recall=recall, post_filter=post_filter
        )
        == []
    )
    assert events == []
    assert await scoped_recall(
        owner_user_id="a", allowed_knowledge_base_ids=["kb"], recall=recall, post_filter=post_filter
    ) == ["doc-2"]
    assert events == ['tenantId == "a" and knowledgeBaseId in ["kb"]', "doc-1", "doc-2"]
    assert await scoped_recall(
        owner_user_id="b", allowed_knowledge_base_ids=["kb"], recall=recall
    ) == ["doc-1", "doc-2"]
