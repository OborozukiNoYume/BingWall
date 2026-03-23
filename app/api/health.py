from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import LiveHealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live", response_model=LiveHealthResponse)
def get_live_health(settings: Settings = Depends(get_settings)) -> LiveHealthResponse:
    return LiveHealthResponse(
        status="ok",
        service="bingwall-api",
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )
