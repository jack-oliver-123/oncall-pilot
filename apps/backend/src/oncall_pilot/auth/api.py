"""HTTP 认证适配和可复用的当前身份 dependency。"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from oncall_pilot.auth.service import AuthService, Identity, public_user
from oncall_pilot.generated_contracts import (
    OPERATION_DOCS,
    ApiFailure,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RegisterRequest,
    UserResponse,
)
from oncall_pilot.protocol import ApiException, success


def auth_service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


async def current_identity(
    service: Annotated[AuthService, Depends(auth_service)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(auto_error=False, scheme_name="BearerAuth")),
    ],
) -> Identity:
    if credentials is None:
        raise ApiException("AUTH_UNAUTHENTICATED")
    return await service.authenticate(credentials.credentials)


async def register(
    body: RegisterRequest,
    request: Request,
    service: Annotated[AuthService, Depends(auth_service)],
) -> UserResponse:
    user = await service.register(body.email, body.password)
    return UserResponse.model_validate(
        success(user.model_dump(mode="json"), request.state.request_id).model_dump()
    )


async def login(
    body: LoginRequest,
    request: Request,
    service: Annotated[AuthService, Depends(auth_service)],
) -> LoginResponse:
    data = await service.login(body.email, body.password)
    return LoginResponse.model_validate(
        success(data.model_dump(mode="json"), request.state.request_id).model_dump()
    )


async def me(
    request: Request,
    identity: Annotated[Identity, Depends(current_identity)],
) -> UserResponse:
    return UserResponse.model_validate(
        success(
            public_user(identity.user).model_dump(mode="json"), request.state.request_id
        ).model_dump()
    )


async def logout(
    request: Request,
    identity: Annotated[Identity, Depends(current_identity)],
    service: Annotated[AuthService, Depends(auth_service)],
) -> LogoutResponse:
    await service.logout(identity)
    return LogoutResponse.model_validate(success(None, request.state.request_id).model_dump())


def install_auth(app: FastAPI) -> None:
    for path, method, endpoint, model, operation, status in (
        ("/auth/register", "POST", register, UserResponse, "registerUser", 409),
        ("/auth/login", "POST", login, LoginResponse, "loginUser", 401),
        ("/auth/logout", "POST", logout, LogoutResponse, "logoutUser", 401),
        ("/auth/me", "GET", me, UserResponse, "getCurrentUser", 401),
    ):
        app.add_api_route(
            path,
            endpoint,
            methods=[method],
            response_model=model,
            operation_id=operation,
            tags=["auth"],
            openapi_extra=OPERATION_DOCS[operation],
            responses={
                status: {"model": ApiFailure},
                422: {"model": ApiFailure},
                500: {"model": ApiFailure},
                "default": {"model": ApiFailure},
            },
        )
