from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta
import logging
import sqlite3

from app.api.errors import ApiError
from app.core.security import summarize_client_value
from app.repositories.download_repository import DownloadRepository
from app.schemas.admin_downloads import AdminDownloadStatsData
from app.schemas.admin_downloads import AdminDownloadStatsQuery
from app.schemas.admin_downloads import AdminDownloadStatsSummary
from app.schemas.admin_downloads import AdminDownloadTrendPoint
from app.schemas.admin_downloads import AdminTopDownloadedWallpaper
from app.schemas.public import PublicDownloadEventData
from app.schemas.public import PublicDownloadEventRequest
from app.services.resource_locator import ResourceLocator

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(
        self,
        repository: DownloadRepository,
        *,
        resource_locator: ResourceLocator,
        session_secret: str,
    ) -> None:
        self.repository = repository
        self.resource_locator = resource_locator
        self.session_secret = session_secret

    def register_public_download(
        self,
        *,
        payload: PublicDownloadEventRequest,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> PublicDownloadEventData:
        target = self.repository.get_public_download_target(
            wallpaper_id=payload.wallpaper_id,
            resource_id=payload.resource_id,
            current_time_utc=utc_now_isoformat(),
        )
        if target is None:
            raise ApiError(
                status_code=404,
                error_code="PUBLIC_WALLPAPER_NOT_FOUND",
                message="壁纸不存在或不可公开访问",
            )

        resource_id = int(target["resource_id"])

        redirect_url = self.resource_locator.build_required_url(
            storage_backend=str(target["storage_backend"]) if target["storage_backend"] else None,
            relative_path=str(target["relative_path"]),
        )
        occurred_at_utc = utc_now_isoformat()

        if not bool(target["is_downloadable"]):
            self.repository.insert_download_event(
                wallpaper_id=payload.wallpaper_id,
                resource_id=resource_id,
                request_id=trace_id,
                market_code=_optional_text(target["market_code"]),
                download_channel=payload.download_channel,
                client_ip_hash=summarize_client_value(client_ip, secret=self.session_secret),
                user_agent=summarize_client_value(user_agent, secret=self.session_secret),
                result_status="blocked",
                redirect_url=None,
                occurred_at_utc=occurred_at_utc,
                created_at_utc=occurred_at_utc,
            )
            raise ApiError(
                status_code=409,
                error_code="PUBLIC_DOWNLOAD_NOT_ALLOWED",
                message="当前内容不可下载",
            )

        try:
            event_id = self.repository.insert_download_event(
                wallpaper_id=payload.wallpaper_id,
                resource_id=resource_id,
                request_id=trace_id,
                market_code=_optional_text(target["market_code"]),
                download_channel=payload.download_channel,
                client_ip_hash=summarize_client_value(client_ip, secret=self.session_secret),
                user_agent=summarize_client_value(user_agent, secret=self.session_secret),
                result_status="redirected",
                redirect_url=redirect_url,
                occurred_at_utc=occurred_at_utc,
                created_at_utc=occurred_at_utc,
            )
        except sqlite3.DatabaseError as exc:
            logger.warning(
                "Download event degraded to direct redirect: wallpaper_id=%s resource_id=%s error=%s",
                payload.wallpaper_id,
                resource_id,
                exc,
            )
            return PublicDownloadEventData(
                redirect_url=redirect_url,
                event_id=None,
                recorded=False,
                result_status="degraded",
            )

        logger.info(
            "Public download event recorded: wallpaper_id=%s resource_id=%s event_id=%s",
            payload.wallpaper_id,
            resource_id,
            event_id,
        )
        return PublicDownloadEventData(
            redirect_url=redirect_url,
            event_id=event_id,
            recorded=True,
            result_status="redirected",
        )

    def get_admin_download_stats(self, *, query: AdminDownloadStatsQuery) -> AdminDownloadStatsData:
        started_from_utc = self._build_started_from_utc(days=query.days)
        summary_row = self.repository.get_download_stats_summary(started_from_utc=started_from_utc)
        top_rows = self.repository.list_top_downloaded_wallpapers(
            started_from_utc=started_from_utc,
            limit=query.top_limit,
        )
        trend_rows = self.repository.list_download_trends(started_from_utc=started_from_utc)
        return AdminDownloadStatsData(
            summary=AdminDownloadStatsSummary(
                total_events=int(summary_row["total_events"]),
                redirected_events=int(summary_row["redirected_events"]),
                blocked_events=int(summary_row["blocked_events"]),
                degraded_events=int(summary_row["degraded_events"]),
                unique_wallpapers=int(summary_row["unique_wallpapers"]),
                unique_markets=int(summary_row["unique_markets"]),
                latest_occurred_at_utc=_optional_text(summary_row["latest_occurred_at_utc"]),
            ),
            top_wallpapers=[
                AdminTopDownloadedWallpaper(
                    wallpaper_id=int(row["wallpaper_id"]),
                    title=str(row["title"]),
                    market_code=str(row["market_code"]),
                    wallpaper_date=str(row["wallpaper_date"]),
                    download_count=int(row["download_count"]),
                )
                for row in top_rows
            ],
            daily_trends=self._build_daily_trends(
                days=query.days,
                trend_rows=trend_rows,
            ),
        )

    def _build_daily_trends(
        self,
        *,
        days: int,
        trend_rows: list[sqlite3.Row],
    ) -> list[AdminDownloadTrendPoint]:
        today = datetime.now(tz=UTC).date()
        trend_map = {
            str(row["trend_date"]): AdminDownloadTrendPoint(
                trend_date=str(row["trend_date"]),
                total_events=int(row["total_events"]),
                redirected_events=int(row["redirected_events"]),
                blocked_events=int(row["blocked_events"]),
                degraded_events=int(row["degraded_events"]),
            )
            for row in trend_rows
        }
        items: list[AdminDownloadTrendPoint] = []
        for offset in range(days - 1, -1, -1):
            trend_date = (today - timedelta(days=offset)).isoformat()
            items.append(
                trend_map.get(
                    trend_date,
                    AdminDownloadTrendPoint(
                        trend_date=trend_date,
                        total_events=0,
                        redirected_events=0,
                        blocked_events=0,
                        degraded_events=0,
                    ),
                )
            )
        return items

    def _build_started_from_utc(self, *, days: int) -> str:
        today = datetime.now(tz=UTC).date()
        started_from_date = today - timedelta(days=days - 1)
        started_from = datetime.combine(started_from_date, time.min, tzinfo=UTC)
        return started_from.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
