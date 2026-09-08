from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI, Request
from tenant_probe import ProbeRepository, Resource
from test_protocol import validator
from test_tenant_repository import create_probe_tables

from oncall_pilot.app import create_app
from oncall_pilot.auth.api import current_user, protected_router, require_owned_resource
from oncall_pilot.generated_contracts import ApiSuccess
from oncall_pilot.memory.scope import CurrentUser
from oncall_pilot.memory.sqlite import Database
from oncall_pilot.protocol import success


def install_probe(app: FastAPI, database: Database) -> None:
    router = protected_router()

    async def parents(
        request: Request, user: Annotated[CurrentUser, Depends(current_user)]
    ) -> ApiSuccess:
        async with database.transaction() as session:
            resources = await ProbeRepository(session).list_parents(owner_user_id=user.user_id)
        return success([r.name for r in resources], request.state.request_id)

    async def parent(
        parent_id: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
    ) -> ApiSuccess:
        async with database.transaction() as session:
            repo = ProbeRepository(session)
            if request.method == "PATCH":
                result = await repo.update_parent(parent_id, "changed", owner_user_id=user.user_id)
            elif request.method == "DELETE":
                result = await repo.delete_parent(parent_id, owner_user_id=user.user_id)
            else:
                resource = require_owned_resource(
                    await repo.get_parent(parent_id, owner_user_id=user.user_id)
                )
                result = resource.name
        return success(require_owned_resource(result), request.state.request_id)

    async def children(
        parent_id: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
    ) -> ApiSuccess:
        async with database.transaction() as session:
            resources = require_owned_resource(
                await ProbeRepository(session).list_children(parent_id, owner_user_id=user.user_id)
            )
        return success([r.name for r in resources], request.state.request_id)

    async def child(
        parent_id: str,
        child_id: str,
        request: Request,
        user: Annotated[CurrentUser, Depends(current_user)],
    ) -> ApiSuccess:
        async with database.transaction() as session:
            repo = ProbeRepository(session)
            if request.method == "PATCH":
                result = await repo.update_child(
                    parent_id, child_id, "changed", owner_user_id=user.user_id
                )
            elif request.method == "DELETE":
                result = await repo.delete_child(parent_id, child_id, owner_user_id=user.user_id)
            else:
                resource = require_owned_resource(
                    await repo.get_child(parent_id, child_id, owner_user_id=user.user_id)
                )
                result = resource.name
        return success(require_owned_resource(result), request.state.request_id)

    async def context(
        request: Request, user: Annotated[CurrentUser, Depends(current_user)]
    ) -> ApiSuccess:
        await asyncio.sleep(0)
        return success(
            {
                "userId": user.user_id,
                "ownerUserId": user.owner_scope.owner_user_id,
                "tenantId": user.tenant_id,
            },
            request.state.request_id,
        )

    router.add_api_route("/scope/parents", parents, response_model=ApiSuccess)
    router.add_api_route(
        "/scope/parents/{parent_id}",
        parent,
        methods=["GET", "PATCH", "DELETE"],
        response_model=ApiSuccess,
    )
    router.add_api_route("/scope/parents/{parent_id}/children", children, response_model=ApiSuccess)
    router.add_api_route(
        "/scope/parents/{parent_id}/children/{child_id}",
        child,
        methods=["GET", "PATCH", "DELETE"],
        response_model=ApiSuccess,
    )
    router.add_api_route("/scope/context", context, response_model=ApiSuccess)
    app.include_router(router)


@pytest.fixture
async def scoped_client(
    migrated_config: Path, database: Database
) -> AsyncGenerator[httpx.AsyncClient]:
    await create_probe_tables(database)
    app = create_app(migrated_config)
    install_probe(app, database)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"X-Request-ID": "scope-test"},
        ) as client:
            yield client


async def create_user(client: httpx.AsyncClient, email: str) -> tuple[str, str]:
    credentials = {"email": email, "password": "scope-password"}
    response = await client.post("/auth/register", json=credentials)
    assert response.status_code == 200
    user_id: str = response.json()["data"]["id"]
    login = await client.post("/auth/login", json=credentials)
    assert login.status_code == 200
    token: str = login.json()["data"]["token"]
    return user_id, token


async def test_protected_router_guards_handlers_without_identity_parameter(
    migrated_config: Path,
) -> None:
    app = create_app(migrated_config)
    router = protected_router()
    calls: list[str] = []

    async def handler(request: Request) -> ApiSuccess:
        calls.append("resource-io")
        return success(None, request.state.request_id)

    router.add_api_route("/guard", handler, response_model=ApiSuccess)
    app.include_router(router)
    operation = app.openapi()["paths"]["/guard"]["get"]
    assert operation["security"] == [{"BearerAuth": []}]
    assert {"401", "403"} <= set(operation["responses"])
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for headers in [{}, {"Authorization": "Bearer invalid"}]:
                assert (await client.get("/guard", headers=headers)).status_code == 401
            assert calls == []
            _, token = await create_user(client, "guard@example.com")
            headers = {"Authorization": f"Bearer {token}"}
            assert (await client.get("/guard", headers=headers)).status_code == 200
            assert calls == ["resource-io"]
            await client.post("/auth/logout", headers=headers)
            assert (await client.get("/guard", headers=headers)).status_code == 401
            assert calls == ["resource-io"]


async def test_cross_tenant_http_contract_and_logout_persistence(
    scoped_client: httpx.AsyncClient,
    database: Database,
) -> None:
    client = scoped_client
    a, token_a = await create_user(client, "a@example.com")
    b, token_b = await create_user(client, "b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    async with database.transaction() as session:
        repo = ProbeRepository(session)
        for owner, label in [(a, "a"), (b, "b")]:
            await repo.create_parent(
                Resource(f"{label}-parent", f"{label}-secret"), owner_user_id=owner
            )
            await repo.create_parent(Resource(f"{label}-empty", "empty"), owner_user_id=owner)
            assert await repo.create_child(
                f"{label}-parent",
                Resource(f"{label}-child", f"{label}-child-secret"),
                owner_user_id=owner,
            )

    unauthenticated = await client.get("/scope/parents")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["WWW-Authenticate"] == "Bearer"
    validator("ApiFailure").validate(unauthenticated.json())

    # 并发认证派生上下文，URL/header 中的伪造 owner/tenant 均不起作用。
    responses = await asyncio.gather(
        *[
            client.get(
                f"/scope/context?owner_user_id={other}&tenantId={other}",
                headers={**headers, "X-Tenant-ID": other},
            )
            for headers, other in [(headers_a, b), (headers_b, a)]
        ]
    )
    for response, owner in zip(responses, [a, b], strict=True):
        assert response.status_code == 200
        assert response.json()["data"] == {"userId": owner, "ownerUserId": owner, "tenantId": owner}

    for headers, own, foreign in [(headers_b, "b", "a"), (headers_a, "a", "b")]:
        failures: list[dict[str, object]] = []
        for method in ["GET", "PATCH", "DELETE"]:
            for path in [
                f"/scope/parents/{foreign}-parent",
                "/scope/parents/missing",
                f"/scope/parents/{foreign}-parent/children/{foreign}-child",
                f"/scope/parents/{own}-parent/children/{foreign}-child",
                f"/scope/parents/{own}-empty/children/{own}-child",
                f"/scope/parents/missing/children/{own}-child",
                f"/scope/parents/{own}-parent/children/missing",
            ]:
                response = await client.request(method, path, headers=headers)
                assert response.status_code == 403, (method, path, response.text)
                validator("ApiFailure").validate(response.json())
                failures.append(response.json())
        for parent in [f"{foreign}-parent", "missing"]:
            response = await client.get(f"/scope/parents/{parent}/children", headers=headers)
            assert response.status_code == 403
            failures.append(response.json())
        assert all(failure == failures[0] for failure in failures)
        assert failures[0]["error"] == {
            "code": "AUTH_FORBIDDEN",
            "category": "AUTH",
            "httpStatus": 403,
            "message": "没有执行此操作的权限。",
        }
        assert (await client.get(f"/scope/parents/{own}-empty/children", headers=headers)).json()[
            "data"
        ] == []
        assert (
            await client.get(f"/scope/parents/{own}-parent/children/{own}-child", headers=headers)
        ).json()["data"] == f"{own}-child-secret"

    # 登出只撤销认证；两名用户的持久父子资源不受影响。
    assert (await client.post("/auth/logout", headers=headers_a)).status_code == 200
    assert (await client.get("/scope/parents/a-parent", headers=headers_a)).status_code == 401
    assert (await client.get("/scope/parents/b-parent", headers=headers_b)).json()[
        "data"
    ] == "b-secret"
    relogin = await client.post(
        "/auth/login", json={"email": "a@example.com", "password": "scope-password"}
    )
    headers_a = {"Authorization": f"Bearer {relogin.json()['data']['token']}"}
    assert (await client.get("/scope/parents/a-parent/children/a-child", headers=headers_a)).json()[
        "data"
    ] == "a-child-secret"
    assert (
        await client.patch("/scope/parents/a-parent/children/a-child", headers=headers_a)
    ).status_code == 200
    assert (await client.get("/scope/parents/a-parent/children/a-child", headers=headers_a)).json()[
        "data"
    ] == "changed"
    assert (
        await client.delete("/scope/parents/a-parent/children/a-child", headers=headers_a)
    ).status_code == 200
    assert (await client.patch("/scope/parents/a-parent", headers=headers_a)).status_code == 200
    assert (await client.delete("/scope/parents/a-parent", headers=headers_a)).status_code == 200
    assert (await client.get("/scope/parents/a-parent", headers=headers_a)).status_code == 403
    assert (await client.get("/scope/parents/b-parent/children/b-child", headers=headers_b)).json()[
        "data"
    ] == "b-child-secret"
