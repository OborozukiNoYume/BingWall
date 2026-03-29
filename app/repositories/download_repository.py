from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import cast

from app.domain.resource_variants import RESOURCE_TYPE_DOWNLOAD
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.repositories.sqlite import connect_sqlite


class DownloadRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def get_public_download_target(
        self,
        *,
        wallpaper_id: int,
        resource_id: int | None,
        current_time_utc: str,
    ) -> sqlite3.Row | None:
        base_parameters: tuple[str | int | None, ...] = (
            wallpaper_id,
            current_time_utc,
            current_time_utc,
        )
        if resource_id is not None:
            row = self.connection.execute(
                """
                SELECT
                    w.id,
                    w.title,
                    w.market_code,
                    w.wallpaper_date,
                    w.is_downloadable,
                    r.id AS resource_id,
                    r.relative_path,
                    r.storage_backend
                FROM wallpapers AS w
                INNER JOIN image_resources AS r
                    ON r.wallpaper_id = w.id
                   AND r.image_status = 'ready'
                WHERE w.id = ?
                  AND w.content_status = 'enabled'
                  AND w.is_public = 1
                  AND w.resource_status = 'ready'
                  AND (w.publish_start_at_utc IS NULL OR w.publish_start_at_utc <= ?)
                  AND (w.publish_end_at_utc IS NULL OR w.publish_end_at_utc >= ?)
                  AND r.id = ?
                  AND (r.resource_type = ? OR r.resource_type = ?)
                LIMIT 1;
                """,
                (
                    *base_parameters,
                    resource_id,
                    RESOURCE_TYPE_DOWNLOAD,
                    RESOURCE_TYPE_ORIGINAL,
                ),
            ).fetchone()
            return cast(sqlite3.Row | None, row)

        row = self.connection.execute(
            """
            SELECT
                w.id,
                w.title,
                w.market_code,
                w.wallpaper_date,
                w.is_downloadable,
                download_resource.id AS resource_id,
                download_resource.relative_path,
                download_resource.storage_backend
            FROM wallpapers AS w
            INNER JOIN image_resources AS download_resource
                ON download_resource.wallpaper_id = w.id
               AND download_resource.resource_type = ?
               AND download_resource.image_status = 'ready'
            WHERE w.id = ?
              AND w.content_status = 'enabled'
              AND w.is_public = 1
              AND w.resource_status = 'ready'
              AND (w.publish_start_at_utc IS NULL OR w.publish_start_at_utc <= ?)
              AND (w.publish_end_at_utc IS NULL OR w.publish_end_at_utc >= ?)
            ORDER BY COALESCE(download_resource.width, 0) * COALESCE(download_resource.height, 0) DESC,
                     download_resource.id ASC
            LIMIT 1;
            """,
            (
                RESOURCE_TYPE_DOWNLOAD,
                *base_parameters,
            ),
        ).fetchone()
        if row is not None:
            return cast(sqlite3.Row, row)

        legacy_row = self.connection.execute(
            """
            SELECT
                w.id,
                w.title,
                w.market_code,
                w.wallpaper_date,
                w.is_downloadable,
                original_resource.id AS resource_id,
                original_resource.relative_path,
                original_resource.storage_backend
            FROM wallpapers AS w
            INNER JOIN image_resources AS original_resource
                ON original_resource.wallpaper_id = w.id
               AND original_resource.resource_type = ?
               AND original_resource.image_status = 'ready'
            WHERE w.id = ?
              AND w.content_status = 'enabled'
              AND w.is_public = 1
              AND w.resource_status = 'ready'
              AND (w.publish_start_at_utc IS NULL OR w.publish_start_at_utc <= ?)
              AND (w.publish_end_at_utc IS NULL OR w.publish_end_at_utc >= ?)
            LIMIT 1;
            """,
            (
                RESOURCE_TYPE_ORIGINAL,
                *base_parameters,
            ),
        ).fetchone()
        return cast(sqlite3.Row | None, legacy_row)

    def insert_download_event(
        self,
        *,
        wallpaper_id: int,
        resource_id: int | None,
        request_id: str,
        market_code: str | None,
        download_channel: str,
        client_ip_hash: str | None,
        user_agent: str | None,
        result_status: str,
        redirect_url: str | None,
        occurred_at_utc: str,
        created_at_utc: str,
    ) -> int:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO download_events (
                    wallpaper_id,
                    resource_id,
                    request_id,
                    market_code,
                    download_channel,
                    client_ip_hash,
                    user_agent,
                    result_status,
                    redirect_url,
                    occurred_at_utc,
                    created_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    wallpaper_id,
                    resource_id,
                    request_id,
                    market_code,
                    download_channel,
                    client_ip_hash,
                    user_agent,
                    result_status,
                    redirect_url,
                    occurred_at_utc,
                    created_at_utc,
                ),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create download event record.")
        return int(cursor.lastrowid)

    def get_download_stats_summary(self, *, started_from_utc: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                COALESCE(SUM(CASE WHEN result_status = 'redirected' THEN 1 ELSE 0 END), 0)
                    AS redirected_events,
                COALESCE(SUM(CASE WHEN result_status = 'blocked' THEN 1 ELSE 0 END), 0)
                    AS blocked_events,
                COALESCE(SUM(CASE WHEN result_status = 'degraded' THEN 1 ELSE 0 END), 0)
                    AS degraded_events,
                COUNT(DISTINCT wallpaper_id) AS unique_wallpapers,
                COUNT(DISTINCT market_code) AS unique_markets,
                MAX(occurred_at_utc) AS latest_occurred_at_utc
            FROM download_events
            WHERE occurred_at_utc >= ?;
            """,
            (started_from_utc,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Download stats summary query returned no row.")
        return cast(sqlite3.Row, row)

    def list_top_downloaded_wallpapers(
        self,
        *,
        started_from_utc: str,
        limit: int,
    ) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                d.wallpaper_id,
                COALESCE(NULLIF(w.title, ''), NULLIF(w.copyright_text, ''), w.source_name)
                    AS title,
                w.market_code,
                w.wallpaper_date,
                COUNT(*) AS download_count
            FROM download_events AS d
            INNER JOIN wallpapers AS w ON w.id = d.wallpaper_id
            WHERE d.occurred_at_utc >= ?
              AND d.result_status = 'redirected'
            GROUP BY d.wallpaper_id, title, w.market_code, w.wallpaper_date
            ORDER BY download_count DESC, w.wallpaper_date DESC, d.wallpaper_id DESC
            LIMIT ?;
            """,
            (started_from_utc, limit),
        ).fetchall()
        return list(rows)

    def list_download_trends(self, *, started_from_utc: str) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                substr(occurred_at_utc, 1, 10) AS trend_date,
                COUNT(*) AS total_events,
                COALESCE(SUM(CASE WHEN result_status = 'redirected' THEN 1 ELSE 0 END), 0)
                    AS redirected_events,
                COALESCE(SUM(CASE WHEN result_status = 'blocked' THEN 1 ELSE 0 END), 0)
                    AS blocked_events,
                COALESCE(SUM(CASE WHEN result_status = 'degraded' THEN 1 ELSE 0 END), 0)
                    AS degraded_events
            FROM download_events
            WHERE occurred_at_utc >= ?
            GROUP BY substr(occurred_at_utc, 1, 10)
            ORDER BY trend_date ASC;
            """,
            (started_from_utc,),
        ).fetchall()
        return list(rows)
