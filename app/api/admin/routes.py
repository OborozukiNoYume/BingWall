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
from app.repositories.admin_content_repository import AdminContentRepository
from app.schemas.admin_auth import AdminLoginData
from app.schemas.admin_auth import AdminLoginRequest
from app.schemas.admin_auth import AdminLogoutData
from app.schemas.admin_auth import AdminSessionContext
from app.schemas.admin_content import AdminAuditLogListData
from app.schemas.admin_content import AdminAuditLogListQuery
from app.schemas.admin_content import AdminWallpaperDetailData
from app.schemas.admin_content import AdminWallpaperListData
from app.schemas.admin_content import AdminWallpaperListQuery
from app.schemas.admin_content import AdminWallpaperStatusUpdateData
from app.schemas.admin_content import AdminWallpaperStatusUpdateRequest
from app.schemas.common import ErrorEnvelope
from app.schemas.common import SuccessEnvelope
from app.services.admin_auth import AdminAuthService
from app.services.admin_content import AdminContentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
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


def get_admin_content_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[AdminContentRepository]:
    repository = AdminContentRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


def get_admin_content_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[AdminContentRepository, Depends(get_admin_content_repository)],
) -> AdminContentService:
    return AdminContentService(
        repository,
        session_secret=settings.security_session_secret.get_secret_value(),
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
    "/auth/login",
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
    "/auth/logout",
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


@router.get(
    "/wallpapers",
    response_model=SuccessEnvelope[AdminWallpaperListData],
    responses=ERROR_RESPONSES,
)
def list_admin_wallpapers(
    request: Request,
    query: Annotated[AdminWallpaperListQuery, Depends()],
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data, pagination = service.list_wallpapers(query=query)
    logger.info(
        "Admin wallpaper list served: content_status=%s image_status=%s market=%s page=%s",
        query.content_status,
        query.image_status,
        query.market_code,
        query.page,
    )
    return build_success_response(
        request=request,
        data=data.model_dump(),
        pagination=pagination.model_dump(),
    )


@router.get(
    "/wallpapers/{wallpaper_id}",
    response_model=SuccessEnvelope[AdminWallpaperDetailData],
    responses=ERROR_RESPONSES,
)
def get_admin_wallpaper_detail(
    wallpaper_id: int,
    request: Request,
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data = service.get_wallpaper_detail(wallpaper_id=wallpaper_id)
    logger.info("Admin wallpaper detail served: wallpaper_id=%s", wallpaper_id)
    return build_success_response(request=request, data=data.model_dump())


@router.post(
    "/wallpapers/{wallpaper_id}/status",
    response_model=SuccessEnvelope[AdminWallpaperStatusUpdateData],
    responses=ERROR_RESPONSES,
)
def update_admin_wallpaper_status(
    wallpaper_id: int,
    payload: AdminWallpaperStatusUpdateRequest,
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data = service.update_wallpaper_status(
        wallpaper_id=wallpaper_id,
        payload=payload,
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info(
        "Admin wallpaper status updated: wallpaper_id=%s previous_status=%s target_status=%s",
        wallpaper_id,
        data.previous_status,
        data.target_status,
    )
    return build_success_response(request=request, data=data.model_dump())


@router.get(
    "/audit-logs",
    response_model=SuccessEnvelope[AdminAuditLogListData],
    responses=ERROR_RESPONSES,
)
def list_admin_audit_logs(
    request: Request,
    query: Annotated[AdminAuditLogListQuery, Depends()],
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data, pagination = service.list_audit_logs(query=query)
    logger.info(
        "Admin audit logs served: admin_user_id=%s target_type=%s target_id=%s page=%s",
        query.admin_user_id,
        query.target_type,
        query.target_id,
        query.page,
    )
    return build_success_response(
        request=request,
        data=data.model_dump(),
        pagination=pagination.model_dump(),
    )
