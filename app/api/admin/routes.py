from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Header
from fastapi import Request

from app.api.errors import ApiError
from app.api.errors import build_success_response
from app.core.config import Settings
from app.core.config import get_settings
from app.repositories.admin_auth_repository import AdminAuthRepository
from app.schemas.admin_auth import AdminLoginData
from app.schemas.admin_auth import AdminLoginRequest
from app.schemas.admin_auth import AdminLogoutData
from app.schemas.admin_auth import AdminSessionContext
from app.schemas.common import ErrorEnvelope
from app.schemas.common import SuccessEnvelope
from app.services.admin_auth import AdminAuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}


def get_admin_auth_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[AdminAuthRepository]:
    repository = AdminAuthRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


def get_admin_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[AdminAuthRepository, Depends(get_admin_auth_repository)],
) -> AdminAuthService:
    return AdminAuthService(
        repository,
        session_secret=settings.security_session_secret.get_secret_value(),
        session_ttl_hours=settings.security_session_ttl_hours,
    )


def require_admin_session(
    service: Annotated[AdminAuthService, Depends(get_admin_auth_service)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AdminSessionContext:
    if authorization is None:
        raise ApiError(
            status_code=401,
            error_code="ADMIN_AUTH_UNAUTHORIZED",
            message="未登录或会话无效",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(
            status_code=401,
            error_code="ADMIN_AUTH_UNAUTHORIZED",
            message="未登录或会话无效",
        )
    return service.authenticate_session(session_token=token.strip())


@router.post(
    "/login",
    response_model=SuccessEnvelope[AdminLoginData],
    responses=ERROR_RESPONSES,
)
def login_admin(
    payload: AdminLoginRequest,
    request: Request,
    service: Annotated[AdminAuthService, Depends(get_admin_auth_service)],
) -> dict[str, object]:
    data = service.login(
        username=payload.username,
        password=payload.password,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("Admin login response served for username=%s", payload.username)
    return build_success_response(request=request, data=data.model_dump())


@router.post(
    "/logout",
    response_model=SuccessEnvelope[AdminLogoutData],
    responses=ERROR_RESPONSES,
)
def logout_admin(
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminAuthService, Depends(get_admin_auth_service)],
) -> dict[str, object]:
    service.logout(
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("Admin logout response served for username=%s", session.username)
    return build_success_response(request=request, data=AdminLogoutData().model_dump())
