from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError
from starlette.routing import Route

from oncall_pilot import generated_contracts
from oncall_pilot.app import create_app
from oncall_pilot.generated_contracts import ERROR_CATALOG, ApiError, SseEvent
from oncall_pilot.protocol import ApiException, api_error, serialize_sse, success

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "packages/api-contracts"
DOCUMENT: dict[str, Any] = json.loads(
    (CONTRACTS / "openapi/foundation.openapi.json").read_text(encoding="utf-8")
)
FIXTURES: dict[str, list[dict[str, Any]]] = json.loads(
    (CONTRACTS / "fixtures/protocol.json").read_text(encoding="utf-8")
)


class JsonValidator(Protocol):
    def validate(self, instance: Any) -> None: ...

    def is_valid(self, instance: Any) -> bool: ...


def validator(name: str) -> JsonValidator:
    return cast(
        JsonValidator,
        Draft202012Validator(
            {"$ref": f"#/components/schemas/{name}", "components": DOCUMENT["components"]},
            format_checker=FormatChecker(),
        ),
    )


def normalize(value: Any, definitions: dict[str, Any]) -> Any:
    """忽略文档注解，展开引用，保留实际字段、约束和联合语义。"""
    if isinstance(value, list):
        return [normalize(item, definitions) for item in cast(list[Any], value)]
    if not isinstance(value, dict):
        if isinstance(value, str) and value.startswith(("#/$defs/", "#/components/schemas/")):
            return normalize(definitions[value.rsplit("/", 1)[1]], definitions)
        return value
    mapping = cast(dict[str, Any], value)
    if "$ref" in mapping:
        name = mapping["$ref"].rsplit("/", 1)[1]
        return {} if name == "JsonValue" else normalize(definitions[name], definitions)
    result: dict[str, Any] = {
        key: normalize(child, definitions)
        for key, child in mapping.items()
        if key not in {"$defs", "title", "description", "default"}
    }
    if "const" in result or "enum" in result:
        result.pop("type", None)
    if result.get("additionalProperties") == {}:
        result["additionalProperties"] = True
    return result


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    (tmp_path / "project.json").write_text("{}", encoding="utf-8")
    return create_app(tmp_path)


@pytest.mark.parametrize("name", DOCUMENT["components"]["schemas"])
def test_every_pydantic_schema_matches_canonical_contract(name: str) -> None:
    generated = TypeAdapter[Any](getattr(generated_contracts, name)).json_schema()
    assert normalize(generated, generated.get("$defs", {})) == normalize(
        DOCUMENT["components"]["schemas"][name], DOCUMENT["components"]["schemas"]
    )


@pytest.mark.parametrize(
    "group,name", [("successes", "ApiSuccess"), ("failures", "ApiFailure"), ("events", "SseEvent")]
)
def test_shared_fixtures_and_invalid_mutations(group: str, name: str) -> None:
    adapter = TypeAdapter[Any](getattr(generated_contracts, name))
    for sample in FIXTURES[group]:
        validator(name).validate(sample)
        model = adapter.validate_json(json.dumps(sample))
        assert model.model_dump(mode="json", exclude_unset=True) == sample
        invalid = deepcopy(sample)
        invalid["privatePayload"] = True
        assert not validator(name).is_valid(invalid)
        with pytest.raises(ValidationError):
            adapter.validate_json(json.dumps(invalid))
        for field in sample:
            missing = {key: value for key, value in sample.items() if key != field}
            assert not validator(name).is_valid(missing)
            with pytest.raises(ValidationError):
                adapter.validate_json(json.dumps(missing))


def test_error_catalog_and_success_preserve_values() -> None:
    assert {str(item["category"]) for item in ERROR_CATALOG.values()} == {
        "AUTH",
        "BUSINESS",
        "VALIDATION",
        "SYSTEM",
    }
    for sample in FIXTURES["successes"]:
        assert success(sample["data"], sample["meta"]["requestId"]).model_dump() == sample
    for code, entry in ERROR_CATALOG.items():
        assert api_error(code).model_dump(mode="json", exclude_unset=True) == entry
        details: dict[str, JsonValue] = {"resourceId": "safe-id"}
        error = api_error(code, details)
        validator("ApiError").validate(error.model_dump(mode="json", exclude_unset=True))
        invalid = {**entry, "category": "PRIVATE"}
        with pytest.raises(ValidationError):
            TypeAdapter[ApiError](ApiError).validate_python(invalid)


@pytest.mark.parametrize("event", FIXTURES["events"])
def test_all_sse_events_serialize_with_shared_errors(event: dict[str, Any]) -> None:
    parsed = TypeAdapter[SseEvent](SseEvent).validate_json(json.dumps(event))
    frame = serialize_sse(parsed).decode()
    assert frame.startswith(f"id: {event['id']}\nevent: {event['type']}\ndata: ")
    assert frame.endswith("\n\n")
    data = json.loads(frame.split("data: ", 1)[1])
    assert data == event
    validator("SseEvent").validate(data)
    if "error" in event:
        validator("ApiError").validate(event["error"])


def test_invalid_literal_types_and_tool_payloads_are_rejected() -> None:
    sample = FIXTURES["successes"][0]
    with pytest.raises(ValidationError):
        generated_contracts.ApiSuccess.model_validate({**sample, "ok": 1})
    for sample in FIXTURES["events"]:
        if sample["type"] == "tool.call":
            invalid = {**sample, "status": "completed"}
            invalid.pop("output", None)
            with pytest.raises(ValidationError):
                TypeAdapter[SseEvent](SseEvent).validate_json(json.dumps(invalid))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_json_numbers_are_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        success({"nested": [value]}, "request-1")


@pytest.mark.parametrize("request_id", [None, "upstream-42:abc", "", " ", "x" * 129, "bad\nvalue"])
@pytest.mark.parametrize("path,status", [("/health", 200), ("/missing", 404)])
async def test_request_id_on_success_and_error(
    app: FastAPI,
    request_id: str | None,
    path: str,
    status: int,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get(
            path, headers={} if request_id is None else {"X-Request-ID": request_id}
        )
    assert response.status_code == status
    body = response.json()
    validator("ApiEnvelope").validate(body)
    assert body["meta"]["requestId"] == response.headers["X-Request-ID"]
    if request_id == "upstream-42:abc":
        assert body["meta"]["requestId"] == request_id
    else:
        assert body["meta"]["requestId"] != request_id


class Item(BaseModel):
    count: int


class InputBody(BaseModel):
    items: list[Item]


async def test_validation_field_paths_and_safe_details(app: FastAPI) -> None:
    async def validate_body(body: InputBody, limit: int) -> None:
        pass

    app.add_api_route("/test-validation", validate_body, methods=["POST"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/test-validation?limit=bad", json={"items": [{"count": "secret-input"}]}
        )
    assert response.status_code == 422
    body = response.json()
    validator("ApiFailure").validate(body)
    paths = [item["path"] for item in body["error"]["details"]["issues"]]
    assert ["body", "items", 0, "count"] in paths
    assert ["query", "limit"] in paths
    assert "secret-input" not in response.text
    assert all(
        set(item) == {"path", "type", "message"} for item in body["error"]["details"]["issues"]
    )


@pytest.mark.parametrize("code", list(ERROR_CATALOG))
async def test_all_catalog_exceptions_return_matching_http_status(
    app: FastAPI, code: generated_contracts.ErrorCode
) -> None:
    async def raise_error() -> None:
        raise ApiException(code)

    app.add_api_route("/test-error", raise_error)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get("/test-error", headers={"X-Request-ID": "error-42"})
    assert response.status_code == ERROR_CATALOG[code]["httpStatus"]
    assert response.json() == {
        "ok": False,
        "error": ERROR_CATALOG[code],
        "meta": {"requestId": "error-42"},
    }


async def test_framework_and_unknown_exceptions_are_safe(app: FastAPI) -> None:
    async def raise_http() -> None:
        raise HTTPException(401, "secret-http-detail", headers={"WWW-Authenticate": "Bearer"})

    async def raise_unknown() -> None:
        raise RuntimeError("secret-internal-detail")

    app.add_api_route("/test-http", raise_http)
    app.add_api_route("/test-unknown", raise_unknown)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        for path, expected in [("/test-http", 401), ("/test-unknown", 500)]:
            response = await client.get(path, headers={"X-Request-ID": "error-42"})
            assert response.status_code == expected
            validator("ApiFailure").validate(response.json())
            assert "secret" not in response.text
            assert response.json()["meta"]["requestId"] == response.headers["X-Request-ID"]
        assert (await client.get("/test-http")).headers["WWW-Authenticate"] == "Bearer"
        method_error = await client.post("/health")
        assert method_error.status_code == 405
        assert method_error.headers["Allow"] == "GET"


def assert_openapi_matches(app: FastAPI) -> None:
    framework = {
        (app.openapi_url, "openapi"),
        (app.docs_url, "swagger_ui_html"),
        (app.swagger_ui_oauth2_redirect_url, "swagger_ui_redirect"),
        (app.redoc_url, "redoc_html"),
    }
    routes: list[tuple[str, str]] = []
    for route in app.routes:
        if (
            isinstance(route, Route)
            and not isinstance(route, APIRoute)
            and (route.path, route.name) in framework
            and route.endpoint.__module__ == "fastapi.applications"
        ):
            continue
        assert isinstance(route, APIRoute), "未登记的 HTTP route/mount"
        assert route.methods is not None
        for method in route.methods:
            routes.append((route.path, method.lower()))
            contract = DOCUMENT["paths"].get(route.path, {}).get(method.lower())
            assert contract is not None, "真实路由未登记到合同"
            model_schema = TypeAdapter[Any](route.response_model).json_schema()
            assert normalize(model_schema, model_schema.get("$defs", {})) == normalize(
                contract["responses"]["200"]["content"]["application/json"]["schema"],
                DOCUMENT["components"]["schemas"],
            )
    assert len(routes) == len(set(routes)), "重复 path/method 会产生路由与文档分歧"
    assert set(routes) == {
        (path, method) for path, methods in DOCUMENT["paths"].items() for method in methods
    }
    actual = app.openapi()
    assert set(actual["paths"]) == set(DOCUMENT["paths"])
    for path, methods in DOCUMENT["paths"].items():
        assert set(actual["paths"][path]) == set(methods)
        for method, operation in methods.items():
            observed = actual["paths"][path][method]
            assert observed["operationId"] == operation["operationId"]
            assert normalize(observed["parameters"], actual["components"]["schemas"]) == normalize(
                operation["parameters"], DOCUMENT["components"]["schemas"]
            )
            assert set(observed["responses"]) == set(operation["responses"])
            for status, response in operation["responses"].items():
                assert normalize(
                    observed["responses"][status]["headers"], actual["components"]["schemas"]
                ) == normalize(response["headers"], DOCUMENT["components"]["schemas"])
                expected_schema = response["content"]["application/json"]["schema"]
                actual_schema = observed["responses"][status]["content"]["application/json"][
                    "schema"
                ]
                assert normalize(actual_schema, actual["components"]["schemas"]) == normalize(
                    expected_schema, DOCUMENT["components"]["schemas"]
                )


def test_actual_openapi_paths_and_responses_match_contract(app: FastAPI) -> None:
    assert_openapi_matches(app)


@pytest.mark.parametrize("hidden", [False, True])
def test_unregistered_endpoint_cannot_pass_contract_gate(app: FastAPI, hidden: bool) -> None:
    async def private() -> dict[str, str]:
        return {"private": "payload"}

    app.add_api_route("/private", private, include_in_schema=not hidden)
    with pytest.raises(AssertionError):
        assert_openapi_matches(app)


def test_duplicate_endpoint_cannot_pass_contract_gate(app: FastAPI) -> None:
    original = next(route for route in app.routes if isinstance(route, APIRoute))
    app.add_api_route("/health", original.endpoint, response_model=original.response_model)
    with pytest.raises(AssertionError, match="重复"):
        assert_openapi_matches(app)
