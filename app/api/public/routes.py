from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request

from app.api.errors import build_success_response
from app.core.config import Settings
from app.core.config import get_settings
from app.repositories.public_repository import PublicRepository
from app.schemas.common import ErrorEnvelope
from app.schemas.common import SuccessEnvelope
from app.schemas.public import PublicDownloadEventData
from app.schemas.public import PublicDownloadEventRequest
from app.schemas.public import PublicSiteInfoData
from app.schemas.public import PublicTagListData
from app.schemas.public import PublicWallpaperDetailData
from app.schemas.public import PublicWallpaperFiltersData
from app.schemas.public import PublicWallpaperListData
from app.schemas.public import PublicWallpaperListQuery
from app.repositories.download_repository import DownloadRepository
from app.services.downloads import DownloadService
from app.services.public_catalog import PublicCatalogService
from app.services.resource_locator import ResourceLocator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}


def get_public_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[PublicRepository]:
    repository = PublicRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


def get_download_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[DownloadRepository]:
    repository = DownloadRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


@router.get(
    "/wallpapers",
    response_model=SuccessEnvelope[PublicWallpaperListData],
    responses=ERROR_RESPONSES,
)
def list_public_wallpapers(
    request: Request,
    query: Annotated[PublicWallpaperListQuery, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[PublicRepository, Depends(get_public_repository)],
) -> dict[str, object]:
    service = PublicCatalogService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
    )
    data, pagination = service.list_wallpapers(query=query)
    logger.info(
        "Public wallpaper list served: market=%s keyword=%s page=%s page_size=%s total=%s",
        query.market_code,
        query.keyword,
        query.page,
        query.page_size,
        pagination.total,
    )
    return build_success_response(
        request=request,
        data=data.model_dump(),
        pagination=pagination.model_dump(),
    )


@router.get(
    "/wallpapers/{wallpaper_id}",
    response_model=SuccessEnvelope[PublicWallpaperDetailData],
    responses=ERROR_RESPONSES,
)
def get_public_wallpaper_detail(
    wallpaper_id: int,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[PublicRepository, Depends(get_public_repository)],
) -> dict[str, object]:
    service = PublicCatalogService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
    )
    data = service.get_wallpaper_detail(wallpaper_id=wallpaper_id)
    logger.info("Public wallpaper detail served: wallpaper_id=%s", wallpaper_id)
    return build_success_response(request=request, data=data.model_dump())


@router.get(
    "/wallpaper-filters",
    response_model=SuccessEnvelope[PublicWallpaperFiltersData],
    responses=ERROR_RESPONSES,
)
def get_public_wallpaper_filters(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[PublicRepository, Depends(get_public_repository)],
) -> dict[str, object]:
    service = PublicCatalogService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
    )
    data = service.get_filters()
    logger.info("Public wallpaper filters served: market_count=%s", len(data.markets))
    return build_success_response(request=request, data=data.model_dump())


@router.get(
    "/tags",
    response_model=SuccessEnvelope[PublicTagListData],
    responses=ERROR_RESPONSES,
)
def list_public_tags(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[PublicRepository, Depends(get_public_repository)],
) -> dict[str, object]:
    service = PublicCatalogService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
    )
    data = service.list_tags()
    logger.info("Public tags served: count=%s", len(data.items))
    return build_success_response(request=request, data=data.model_dump())


@router.get(
    "/site-info",
    response_model=SuccessEnvelope[PublicSiteInfoData],
    responses=ERROR_RESPONSES,
)
def get_public_site_info(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[PublicRepository, Depends(get_public_repository)],
) -> dict[str, object]:
    service = PublicCatalogService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
    )
    data = service.get_site_info(
        site_name=settings.site_name,
        site_description=settings.site_description,
        default_market_code=settings.collect_bing_default_market,
    )
    logger.info("Public site info served.")
    return build_success_response(request=request, data=data.model_dump())


@router.post(
    "/download-events",
    response_model=SuccessEnvelope[PublicDownloadEventData],
    responses=ERROR_RESPONSES,
)
def create_public_download_event(
    payload: PublicDownloadEventRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[DownloadRepository, Depends(get_download_repository)],
) -> dict[str, object]:
    service = DownloadService(
        repository,
        resource_locator=ResourceLocator.from_settings(settings),
        session_secret=settings.security_session_secret.get_secret_value(),
    )
    data = service.register_public_download(
        payload=payload,
        trace_id=str(request.state.trace_id),
        client_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info(
        "Public download event served: wallpaper_id=%s recorded=%s result_status=%s",
        payload.wallpaper_id,
        data.recorded,
        data.result_status,
    )
    return build_success_response(request=request, data=data.model_dump())
