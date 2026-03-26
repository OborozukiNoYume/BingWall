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
from app.repositories.admin_collection_repository import AdminCollectionRepository
from app.repositories.admin_content_repository import AdminContentRepository
from app.repositories.download_repository import DownloadRepository
from app.schemas.admin_collection import AdminCollectionLogListData
from app.schemas.admin_collection import AdminCollectionLogListQuery
from app.schemas.admin_collection import AdminCollectionTaskCreateData
from app.schemas.admin_collection import AdminCollectionTaskCreateRequest
from app.schemas.admin_collection import AdminCollectionTaskDetailData
from app.schemas.admin_collection import AdminCollectionTaskListData
from app.schemas.admin_collection import AdminCollectionTaskListQuery
from app.schemas.admin_collection import AdminCollectionTaskRetryData
from app.schemas.admin_auth import AdminLoginData
from app.schemas.admin_auth import AdminLoginRequest
from app.schemas.admin_auth import AdminLogoutData
from app.schemas.admin_auth import AdminSessionContext
from app.schemas.admin_downloads import AdminDownloadStatsData
from app.schemas.admin_downloads import AdminDownloadStatsQuery
from app.schemas.admin_content import AdminAuditLogListData
from app.schemas.admin_content import AdminAuditLogListQuery
from app.schemas.admin_content import AdminTagCreateRequest
from app.schemas.admin_content import AdminTagData
from app.schemas.admin_content import AdminTagListData
from app.schemas.admin_content import AdminTagListQuery
from app.schemas.admin_content import AdminTagUpdateRequest
from app.schemas.admin_content import AdminWallpaperDetailData
from app.schemas.admin_content import AdminWallpaperListData
from app.schemas.admin_content import AdminWallpaperListQuery
from app.schemas.admin_content import AdminWallpaperTagBindingData
from app.schemas.admin_content import AdminWallpaperTagBindingRequest
from app.schemas.admin_content import AdminWallpaperStatusUpdateData
from app.schemas.admin_content import AdminWallpaperStatusUpdateRequest
from app.schemas.common import ErrorEnvelope
from app.schemas.common import SuccessEnvelope
from app.services.admin_collection import AdminCollectionService
from app.services.admin_auth import AdminAuthService
from app.services.admin_content import AdminContentService
from app.services.downloads import DownloadService
from app.services.resource_locator import ResourceLocator

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
        resource_locator=ResourceLocator.from_settings(settings),
    )


def get_admin_collection_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[AdminCollectionRepository]:
    repository = AdminCollectionRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


def get_admin_collection_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[AdminCollectionRepository, Depends(get_admin_collection_repository)],
) -> AdminCollectionService:
    return AdminCollectionService(
        repository,
        session_secret=settings.security_session_secret.get_secret_value(),
        settings=settings,
    )


def get_download_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[DownloadRepository]:
    repository = DownloadRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


def get_download_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[DownloadRepository, Depends(get_download_repository)],
) -> DownloadService:
    return DownloadService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
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
        "Admin wallpaper list served: content_status=%s image_status=%s market=%s keyword=%s page=%s",
        query.content_status,
        query.image_status,
        query.market_code,
        query.keyword,
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


@router.put(
    "/wallpapers/{wallpaper_id}/tags",
    response_model=SuccessEnvelope[AdminWallpaperTagBindingData],
    responses=ERROR_RESPONSES,
)
def update_admin_wallpaper_tags(
    wallpaper_id: int,
    payload: AdminWallpaperTagBindingRequest,
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data = service.update_wallpaper_tags(
        wallpaper_id=wallpaper_id,
        payload=payload,
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info(
        "Admin wallpaper tags updated: wallpaper_id=%s tag_count=%s",
        wallpaper_id,
        len(data.tags),
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


@router.get(
    "/tags",
    response_model=SuccessEnvelope[AdminTagListData],
    responses=ERROR_RESPONSES,
)
def list_admin_tags(
    request: Request,
    query: Annotated[AdminTagListQuery, Depends()],
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data = service.list_tags(query=query)
    logger.info(
        "Admin tags served: status=%s category=%s count=%s",
        query.status,
        query.tag_category,
        len(data.items),
    )
    return build_success_response(request=request, data=data.model_dump())


@router.post(
    "/tags",
    response_model=SuccessEnvelope[AdminTagData],
    responses=ERROR_RESPONSES,
)
def create_admin_tag(
    payload: AdminTagCreateRequest,
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data = service.create_tag(
        payload=payload,
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("Admin tag created: tag_id=%s tag_key=%s", data.tag.id, data.tag.tag_key)
    return build_success_response(request=request, data=data.model_dump())


@router.patch(
    "/tags/{tag_id}",
    response_model=SuccessEnvelope[AdminTagData],
    responses=ERROR_RESPONSES,
)
def update_admin_tag(
    tag_id: int,
    payload: AdminTagUpdateRequest,
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminContentService, Depends(get_admin_content_service)],
) -> dict[str, object]:
    data = service.update_tag(
        tag_id=tag_id,
        payload=payload,
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("Admin tag updated: tag_id=%s tag_key=%s", tag_id, data.tag.tag_key)
    return build_success_response(request=request, data=data.model_dump())


@router.post(
    "/collection-tasks",
    response_model=SuccessEnvelope[AdminCollectionTaskCreateData],
    responses=ERROR_RESPONSES,
)
def create_admin_collection_task(
    payload: AdminCollectionTaskCreateRequest,
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminCollectionService, Depends(get_admin_collection_service)],
) -> dict[str, object]:
    data = service.create_task(
        payload=payload,
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info(
        "Admin collection task created: task_id=%s source_type=%s market=%s",
        data.task_id,
        payload.source_type,
        payload.market_code,
    )
    return build_success_response(request=request, data=data.model_dump())


@router.get(
    "/collection-tasks",
    response_model=SuccessEnvelope[AdminCollectionTaskListData],
    responses=ERROR_RESPONSES,
)
def list_admin_collection_tasks(
    request: Request,
    query: Annotated[AdminCollectionTaskListQuery, Depends()],
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminCollectionService, Depends(get_admin_collection_service)],
) -> dict[str, object]:
    data, pagination = service.list_tasks(query=query)
    logger.info(
        "Admin collection task list served: task_status=%s trigger_type=%s source_type=%s page=%s",
        query.task_status,
        query.trigger_type,
        query.source_type,
        query.page,
    )
    return build_success_response(
        request=request,
        data=data.model_dump(),
        pagination=pagination.model_dump(),
    )


@router.get(
    "/collection-tasks/{task_id}",
    response_model=SuccessEnvelope[AdminCollectionTaskDetailData],
    responses=ERROR_RESPONSES,
)
def get_admin_collection_task_detail(
    task_id: int,
    request: Request,
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminCollectionService, Depends(get_admin_collection_service)],
) -> dict[str, object]:
    data = service.get_task_detail(task_id=task_id)
    logger.info("Admin collection task detail served: task_id=%s", task_id)
    return build_success_response(request=request, data=data.model_dump())


@router.post(
    "/collection-tasks/{task_id}/retry",
    response_model=SuccessEnvelope[AdminCollectionTaskRetryData],
    responses=ERROR_RESPONSES,
)
def retry_admin_collection_task(
    task_id: int,
    request: Request,
    session: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminCollectionService, Depends(get_admin_collection_service)],
) -> dict[str, object]:
    data = service.retry_task(
        task_id=task_id,
        session=session,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info(
        "Admin collection task retried: new_task_id=%s original_task_id=%s",
        data.task_id,
        data.retry_of_task_id,
    )
    return build_success_response(request=request, data=data.model_dump())


@router.get(
    "/logs",
    response_model=SuccessEnvelope[AdminCollectionLogListData],
    responses=ERROR_RESPONSES,
)
def list_admin_collection_logs(
    request: Request,
    query: Annotated[AdminCollectionLogListQuery, Depends()],
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[AdminCollectionService, Depends(get_admin_collection_service)],
) -> dict[str, object]:
    data, pagination = service.list_logs(query=query)
    logger.info(
        "Admin collection logs served: task_id=%s error_type=%s page=%s",
        query.task_id,
        query.error_type,
        query.page,
    )
    return build_success_response(
        request=request,
        data=data.model_dump(),
        pagination=pagination.model_dump(),
    )


@router.get(
    "/download-stats",
    response_model=SuccessEnvelope[AdminDownloadStatsData],
    responses=ERROR_RESPONSES,
)
def get_admin_download_stats(
    request: Request,
    query: Annotated[AdminDownloadStatsQuery, Depends()],
    _: Annotated[AdminSessionContext, Depends(require_admin_session)],
    service: Annotated[DownloadService, Depends(get_download_service)],
) -> dict[str, object]:
    data = service.get_admin_download_stats(query=query)
    logger.info(
        "Admin download stats served: days=%s top_limit=%s total_events=%s",
        query.days,
        query.top_limit,
        data.summary.total_events,
    )
    return build_success_response(request=request, data=data.model_dump())
