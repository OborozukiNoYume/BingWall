import logging
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi import Response
from typing import Annotated

from app.core.config import Settings, get_settings
from app.repositories.health_repository import HealthRepository
from app.schemas.health import DeepHealthResponse
from app.schemas.health import LiveHealthResponse
from app.schemas.health import OperationsMetricsResponse
from app.schemas.health import ReadyHealthResponse
from app.services.health import HealthService

router = APIRouter(prefix="/api/health", tags=["health"])
logger = logging.getLogger(__name__)


def get_health_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[HealthRepository]:
    repository = HealthRepository(settings.database_path)
    try:
        yield repository
    finally:
        repository.close()


@router.get("/live", response_model=LiveHealthResponse)
def get_live_health(settings: Settings = Depends(get_settings)) -> LiveHealthResponse:
    return LiveHealthResponse(
        status="ok",
        service="bingwall-api",
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadyHealthResponse)
def get_ready_health(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[HealthRepository, Depends(get_health_repository)],
) -> ReadyHealthResponse:
    service = HealthService(settings, repository)
    health = service.build_ready_health()
    if health.status == "fail":
        response.status_code = 503
        logger.warning("Ready health check failed.")
    else:
        logger.info("Ready health check succeeded.")
    return health


@router.get("/deep", response_model=DeepHealthResponse)
def get_deep_health(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[HealthRepository, Depends(get_health_repository)],
) -> DeepHealthResponse:
    service = HealthService(settings, repository)
    health = service.build_deep_health()
    if health.status == "fail":
        response.status_code = 503
        logger.warning("Deep health check failed.")
    elif health.status == "degraded":
        logger.warning("Deep health check degraded.")
    else:
        logger.info("Deep health check succeeded.")
    return health


@router.get("/metrics", response_model=OperationsMetricsResponse)
def get_operations_metrics(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[HealthRepository, Depends(get_health_repository)],
) -> OperationsMetricsResponse:
    service = HealthService(settings, repository)
    metrics = service.build_operations_metrics()
    logger.info("Operations metrics requested.")
    return metrics
