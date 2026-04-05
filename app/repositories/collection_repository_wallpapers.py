from __future__ import annotations

import sqlite3
from typing import cast

from app.repositories.collection_repository_models import WallpaperCreateInput
from app.repositories.collection_repository_models import WallpaperLocalizationUpsertInput


class CollectionRepositoryWallpaperMixin:
    connection: sqlite3.Connection

    def find_wallpaper_by_business_key(
        self,
        *,
        source_type: str,
        wallpaper_date: str,
        market_code: str,
    ) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM wallpapers
            WHERE source_type = ?
              AND wallpaper_date = ?
              AND market_code = ?;
            """,
            (source_type, wallpaper_date, market_code),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def find_wallpaper_by_canonical_key(
        self,
        *,
        source_type: str,
        canonical_key: str,
    ) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM wallpapers
            WHERE source_type = ?
              AND canonical_key = ?
            LIMIT 1;
            """,
            (source_type, canonical_key),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def get_wallpaper_localization(
        self,
        *,
        wallpaper_id: int,
        market_code: str,
    ) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM wallpaper_localizations
            WHERE wallpaper_id = ?
              AND market_code = ?
            LIMIT 1;
            """,
            (wallpaper_id, market_code),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def create_wallpaper(self, item: WallpaperCreateInput) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO wallpapers (
                source_type,
                source_key,
                canonical_key,
                market_code,
                wallpaper_date,
                title,
                subtitle,
                copyright_text,
                source_name,
                published_at_utc,
                location_text,
                description,
                is_public,
                is_downloadable,
                origin_page_url,
                origin_image_url,
                origin_width,
                origin_height,
                portrait_image_url,
                resource_status,
                raw_extra_json,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?);
            """,
            (
                item.source_type,
                item.source_key,
                item.canonical_key,
                item.market_code,
                item.wallpaper_date,
                item.title,
                item.subtitle,
                item.copyright_text,
                item.source_name,
                item.published_at_utc,
                item.location_text,
                item.description,
                int(item.is_downloadable),
                item.origin_page_url,
                item.origin_image_url,
                item.origin_width,
                item.origin_height,
                item.portrait_image_url,
                item.raw_extra_json,
                item.created_at_utc,
                item.created_at_utc,
            ),
        )
        self.connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            msg = "Failed to create wallpaper."
            raise RuntimeError(msg)
        return int(lastrowid)

    def update_wallpaper_origin_metadata(
        self,
        *,
        wallpaper_id: int,
        origin_image_url: str,
        origin_width: int | None,
        origin_height: int | None,
        updated_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE wallpapers
            SET origin_image_url = ?,
                origin_width = ?,
                origin_height = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (origin_image_url, origin_width, origin_height, updated_at_utc, wallpaper_id),
        )
        self.connection.commit()

    def update_wallpaper_metadata(
        self,
        *,
        wallpaper_id: int,
        item: WallpaperCreateInput,
        updated_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE wallpapers
            SET source_key = ?,
                canonical_key = ?,
                market_code = ?,
                wallpaper_date = ?,
                title = ?,
                subtitle = ?,
                description = ?,
                copyright_text = ?,
                source_name = ?,
                published_at_utc = ?,
                location_text = ?,
                is_downloadable = ?,
                origin_page_url = ?,
                origin_image_url = ?,
                origin_width = ?,
                origin_height = ?,
                portrait_image_url = ?,
                raw_extra_json = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (
                item.source_key,
                item.canonical_key,
                item.market_code,
                item.wallpaper_date,
                item.title,
                item.subtitle,
                item.description,
                item.copyright_text,
                item.source_name,
                item.published_at_utc,
                item.location_text,
                int(item.is_downloadable),
                item.origin_page_url,
                item.origin_image_url,
                item.origin_width,
                item.origin_height,
                item.portrait_image_url,
                item.raw_extra_json,
                updated_at_utc,
                wallpaper_id,
            ),
        )
        self.connection.commit()

    def upsert_wallpaper_localization(self, item: WallpaperLocalizationUpsertInput) -> None:
        existing_row = self.get_wallpaper_localization(
            wallpaper_id=item.wallpaper_id,
            market_code=item.market_code,
        )
        if existing_row is None:
            self.connection.execute(
                """
                INSERT INTO wallpaper_localizations (
                    wallpaper_id,
                    market_code,
                    source_key,
                    title,
                    subtitle,
                    description,
                    copyright_text,
                    published_at_utc,
                    location_text,
                    origin_page_url,
                    portrait_image_url,
                    raw_extra_json,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item.wallpaper_id,
                    item.market_code,
                    item.source_key,
                    item.title,
                    item.subtitle,
                    item.description,
                    item.copyright_text,
                    item.published_at_utc,
                    item.location_text,
                    item.origin_page_url,
                    item.portrait_image_url,
                    item.raw_extra_json,
                    item.created_at_utc,
                    item.created_at_utc,
                ),
            )
        else:
            self.connection.execute(
                """
                UPDATE wallpaper_localizations
                SET source_key = ?,
                    title = ?,
                    subtitle = ?,
                    description = ?,
                    copyright_text = ?,
                    published_at_utc = ?,
                    location_text = ?,
                    origin_page_url = ?,
                    portrait_image_url = ?,
                    raw_extra_json = ?,
                    updated_at_utc = ?
                WHERE wallpaper_id = ?
                  AND market_code = ?;
                """,
                (
                    item.source_key,
                    item.title,
                    item.subtitle,
                    item.description,
                    item.copyright_text,
                    item.published_at_utc,
                    item.location_text,
                    item.origin_page_url,
                    item.portrait_image_url,
                    item.raw_extra_json,
                    item.created_at_utc,
                    item.wallpaper_id,
                    item.market_code,
                ),
            )
        self.connection.commit()

    def reset_wallpaper_for_resource_rebuild(
        self,
        *,
        wallpaper_id: int,
        updated_at_utc: str,
    ) -> None:
        wallpaper_row = self.connection.execute(
            """
            SELECT content_status
            FROM wallpapers
            WHERE id = ?
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
        if wallpaper_row is None:
            msg = f"Wallpaper {wallpaper_id} not found."
            raise RuntimeError(msg)

        current_status = str(wallpaper_row["content_status"])
        next_status = "disabled" if current_status == "enabled" else current_status
        next_is_public = 1 if next_status == "enabled" else 0
        self.connection.execute(
            """
            UPDATE wallpapers
            SET content_status = ?,
                is_public = ?,
                resource_status = 'pending',
                default_resource_id = NULL,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (next_status, next_is_public, updated_at_utc, wallpaper_id),
        )
        self.connection.commit()
