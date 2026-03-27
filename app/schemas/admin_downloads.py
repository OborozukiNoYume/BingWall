from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

AdminDownloadResultStatus = Literal["redirected", "blocked", "degraded"]


class AdminDownloadStatsQuery(BaseModel):
    days: int = Field(default=7, ge=1, le=90)
    top_limit: int = Field(default=5, ge=1, le=20)


class AdminDownloadStatsSummary(BaseModel):
    total_events: int
    redirected_events: int
    blocked_events: int
    degraded_events: int
    unique_wallpapers: int
    unique_markets: int
    latest_occurred_at_utc: str | None


class AdminTopDownloadedWallpaper(BaseModel):
    wallpaper_id: int
    title: str
    market_code: str
    wallpaper_date: str
    download_count: int


class AdminDownloadTrendPoint(BaseModel):
    trend_date: str
    total_events: int
    redirected_events: int
    blocked_events: int
    degraded_events: int


class AdminDownloadStatsData(BaseModel):
    summary: AdminDownloadStatsSummary
    top_wallpapers: list[AdminTopDownloadedWallpaper]
    daily_trends: list[AdminDownloadTrendPoint]
